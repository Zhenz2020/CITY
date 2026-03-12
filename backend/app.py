"""
CITY 交通仿真后端 API 服务。
"""

import sys
import os
import json
import threading
import time
import queue
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.agents.vehicle import Vehicle, VehicleType
from city.agents.pedestrian import Pedestrian
from city.agents.traffic_manager import TrafficManager
from city.agents.traffic_light_agent import TrafficLightAgent
from city.utils.vector import Vector2D

# 加载 LLM 配置 - 支持多API Key
try:
    from city.llm.llm_client import load_llm_from_config
    from city.llm.agent_llm_interface import set_global_llm_client
    from city.llm.llm_pool import init_llm_pool_from_env, get_llm_pool
    
    # 初始化LLM客户端池（支持多API Key）
    llm_pool = init_llm_pool_from_env()
    
    # 同时也设置一个全局默认client（向后兼容）
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'siliconflow_config.json')
    if os.path.exists(config_path):
        llm_client = load_llm_from_config(config_path)
        set_global_llm_client(llm_client)
        print(f"[LLM] 已加载配置: {config_path}")
        
        # 如果池中没有客户端，添加主client
        if not llm_pool.is_available():
            llm_pool.add_client(llm_client)
    
    LLM_AVAILABLE = llm_pool.is_available()
    if LLM_AVAILABLE:
        stats = llm_pool.get_stats()
        print(f"[LLM] 客户端池就绪: {stats['total_clients']} 个API Key可用")
    else:
        print("[LLM] 警告: 没有可用的LLM客户端")
        
except Exception as e:
    print(f"[LLM] 加载配置失败: {e}")
    import traceback
    traceback.print_exc()
    LLM_AVAILABLE = False

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局状态
simulation: SimulationEnvironment | None = None
simulation_thread: threading.Thread | None = None
is_running = False
lock = threading.Lock()

# LLM 决策队列
llm_decision_queue = queue.Queue()

def create_demo_simulation() -> SimulationEnvironment:
    """创建演示仿真环境 - 修复版：更大网络、更多红绿灯、正确车道显示。"""
    network = RoadNetwork("demo_grid_large")
    nodes: dict[tuple[int, int], Node] = {}
    
    # 1. 扩大网络到 5x5，让车辆跑更远的OD
    GRID_SIZE = 5
    NODE_SPACING = 250  # 节点间距增加到250米，总网络范围1000x1000米
    
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            # 所有内部节点都是交叉口
            is_intersection = (0 < i < GRID_SIZE - 1) and (0 < j < GRID_SIZE - 1)
            node = Node(
                position=Vector2D(i * NODE_SPACING, j * NODE_SPACING),
                name=f"node_{i}_{j}",
                is_intersection=is_intersection
            )
            nodes[(i, j)] = node
            network.add_node(node)
    
    # 2. 创建双向道路，每个方向2车道
    # 垂直方向道路 (南北向)
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE - 1):
            # 南→北 方向，2车道
            network.create_edge(nodes[(i, j)], nodes[(i, j + 1)], num_lanes=2)
            # 北→南 方向，2车道
            network.create_edge(nodes[(i, j + 1)], nodes[(i, j)], num_lanes=2)
    
    # 水平方向道路 (东西向)
    for i in range(GRID_SIZE - 1):
        for j in range(GRID_SIZE):
            # 西→东 方向，2车道
            network.create_edge(nodes[(i, j)], nodes[(i + 1, j)], num_lanes=2)
            # 东→西 方向，2车道
            network.create_edge(nodes[(i + 1, j)], nodes[(i, j)], num_lanes=2)
    
    # 3. 在所有交叉口设置红绿灯
    traffic_light_agents = []
    for i in range(1, GRID_SIZE - 1):
        for j in range(1, GRID_SIZE - 1):
            intersection_node = nodes[(i, j)]
            intersection_node.traffic_light = TrafficLight(
                intersection_node, 
                cycle_time=60, 
                green_duration=25, 
                yellow_duration=5
            )
    
    config = SimulationConfig(time_step=0.2, max_simulation_time=3600.0, real_time_factor=1.0)
    env = SimulationEnvironment(network, config)
    
    # 4. 为所有交叉口添加智能红绿灯智能体
    for i in range(1, GRID_SIZE - 1):
        for j in range(1, GRID_SIZE - 1):
            intersection_node = nodes[(i, j)]
            if intersection_node.is_intersection:
                traffic_light_agent = TrafficLightAgent(
                    control_node=intersection_node,
                    environment=env,
                    use_llm=LLM_AVAILABLE,
                    name=f"红绿灯_{i}_{j}"
                )
                traffic_light_agent.activate()
                env.add_agent(traffic_light_agent)
                traffic_light_agents.append(traffic_light_agent)
    
    print(f"[网络初始化] {GRID_SIZE}x{GRID_SIZE} 网格, {len(traffic_light_agents)} 个红绿灯")
    
    # 5. 生成更多车辆，起点终点距离更远
    import random
    all_nodes_list = list(nodes.values())
    
    # 生成8辆车，确保OD距离较远（至少跨越3个节点）
    for i in range(8):
        # 选择距离较远的起点和终点
        start = random.choice(all_nodes_list)
        
        # 找距离较远的终点（欧氏距离大于500米，确保至少隔2-3个路口）
        far_ends = [
            n for n in all_nodes_list 
            if n != start and 
            ((n.position.x - start.position.x) ** 2 + 
             (n.position.y - start.position.y) ** 2) ** 0.5 > 500
        ]
        
        # 如果没有足够远的节点，降低标准到350米
        if not far_ends:
            far_ends = [
                n for n in all_nodes_list 
                if n != start and 
                ((n.position.x - start.position.x) ** 2 + 
                 (n.position.y - start.position.y) ** 2) ** 0.5 > 350
            ]
        
        # 如果还是没有，再降低标准
        if not far_ends:
            far_ends = [n for n in all_nodes_list if n != start]
        
        end = random.choice(far_ends)
        vtype = random.choice([VehicleType.CAR, VehicleType.BUS, VehicleType.TRUCK])
        vehicle = env.spawn_vehicle(start, end, vtype)
        
        if vehicle:
            vehicle.use_llm = LLM_AVAILABLE
            distance = ((end.position.x - start.position.x) ** 2 + 
                       (end.position.y - start.position.y) ** 2) ** 0.5
            print(f"[初始车辆] {vehicle.agent_id}: {start.name} -> {end.name} (距离{distance:.0f}m, LLM={'启用' if LLM_AVAILABLE else '禁用'})")
    
    return env

def get_network_data(env: SimulationEnvironment) -> dict:
    network = env.road_network
    nodes_data = []
    for node in network.nodes.values():
        nodes_data.append({
            "id": node.node_id,
            "name": node.name,
            "x": node.position.x,
            "y": node.position.y,
            "is_intersection": node.is_intersection,
            "has_traffic_light": node.traffic_light is not None
        })
    edges_data = []
    for edge in network.edges.values():
        edges_data.append({
            "id": edge.edge_id,
            "from_node": edge.from_node.node_id,
            "to_node": edge.to_node.node_id,
            "length": edge.length,
            "num_lanes": len(edge.lanes)
        })
    print(f"[get_network_data] 返回 {len(nodes_data)} 个节点, {len(edges_data)} 条边")
    return {"nodes": nodes_data, "edges": edges_data}

def get_agents_data(env: SimulationEnvironment) -> dict:
    vehicles_data = []
    for vehicle in env.vehicles.values():
        vehicle_data = {
            "id": vehicle.agent_id,
            "type": "vehicle",
            "vehicle_type": vehicle.vehicle_type.name,
            "x": vehicle.position.x,
            "y": vehicle.position.y,
            "velocity": vehicle.velocity,
            "direction": vehicle.direction.angle() if vehicle.direction else 0,
            "state": vehicle.state.name,
            "length": vehicle.length,
            "width": vehicle.width,
        }
        
        # 添加车道索引（用于前端多车道渲染）
        if hasattr(vehicle, 'current_lane') and vehicle.current_lane:
            if hasattr(vehicle, 'current_edge') and vehicle.current_edge:
                try:
                    lane_index = vehicle.current_edge.lanes.index(vehicle.current_lane)
                    vehicle_data["lane_index"] = lane_index
                except ValueError:
                    vehicle_data["lane_index"] = 0
            else:
                vehicle_data["lane_index"] = 0
        else:
            vehicle_data["lane_index"] = 0
            
        if hasattr(vehicle, 'vehicle_state'):
            vehicle_data["vehicle_state"] = vehicle.vehicle_state.name
        vehicles_data.append(vehicle_data)
    
    pedestrians_data = []
    for ped in env.pedestrians.values():
        pedestrians_data.append({
            "id": ped.agent_id,
            "type": "pedestrian",
            "x": ped.position.x,
            "y": ped.position.y,
            "velocity": ped.velocity,
            "state": ped.pedestrian_state.name
        })
    
    return {"vehicles": vehicles_data, "pedestrians": pedestrians_data}

def get_traffic_lights_data(env: SimulationEnvironment) -> list:
    lights_data = []
    
    # 首先收集所有红绿灯智能体的相位信息
    tl_agent_phases = {}
    for agent in env.agents.values():
        if isinstance(agent, TrafficLightAgent):
            phase_name = agent.current_phase.name
            # 解析相位，确定各方向状态
            ns_green = 'NS_GREEN' in phase_name
            ew_green = 'EW_GREEN' in phase_name
            ns_yellow = 'NS_YELLOW' in phase_name
            ew_yellow = 'EW_YELLOW' in phase_name
            all_red = 'ALL_RED' in phase_name
            
            tl_agent_phases[agent.control_node.node_id] = {
                'phase': phase_name,
                'ns_state': 'GREEN' if ns_green else ('YELLOW' if ns_yellow else 'RED'),
                'ew_state': 'GREEN' if ew_green else ('YELLOW' if ew_yellow else 'RED'),
                'all_red': all_red,
            }
    
    for node in env.road_network.nodes.values():
        if node.traffic_light:
            tl = node.traffic_light
            phase_info = tl_agent_phases.get(node.node_id, {})
            
            lights_data.append({
                "node_id": node.node_id,
                "state": tl.state.name,
                "x": node.position.x,
                "y": node.position.y,
                "timer": tl.timer,
                # 双相位系统信息
                "phase": phase_info.get('phase', 'UNKNOWN'),
                "ns_state": phase_info.get('ns_state', 'RED'),
                "ew_state": phase_info.get('ew_state', 'RED'),
                "all_red": phase_info.get('all_red', False),
            })
    return lights_data

def get_traffic_light_agents_data(env: SimulationEnvironment) -> list:
    """获取红绿灯智能体数据。"""
    agents_data = []
    for agent in env.agents.values():
        if isinstance(agent, TrafficLightAgent):
            agents_data.append({
                "id": agent.agent_id,
                "type": "traffic_light_agent",
                "name": agent.name,
                "node_id": agent.control_node.node_id,
                "current_phase": agent.current_phase.name,
                "phase_timer": round(agent.phase_timer, 1),
                "light_state": agent.traffic_light.state.name if agent.traffic_light else 'UNKNOWN',
                "use_llm": agent.use_llm,
            })
    return agents_data

def safe_emit(event, data):
    """线程安全的 WebSocket 发送（简化版）。"""
    try:
        socketio.emit(event, data)
    except Exception as e:
        print(f"[safe_emit] 发送失败: {e}")

def llm_worker():
    """后台 LLM 决策线程。"""
    while True:
        try:
            vehicle_id, perception = llm_decision_queue.get(timeout=1)
            # 这里可以调用 LLM，但暂时简化处理
            safe_emit("agent_decision", {
                "agent_id": vehicle_id,
                "decision": {"action": "proceed", "reason": "LLM决策示例"},
                "timestamp": time.time()
            })
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[LLM Worker] 错误: {e}")

# 启动 LLM 工作线程
llm_thread = threading.Thread(target=llm_worker, daemon=True)
llm_thread.start()

def simulation_loop():
    """仿真主循环。"""
    global is_running
    decision_counter = 0
    
    print("[仿真循环] 启动")
    
    while True:
        with lock:
            if not is_running or simulation is None:
                print("[仿真循环] 停止")
                break
        
        try:
            # 更新红绿灯智能体
            
            with lock:
                if simulation is None:
                    break
                step_result = simulation.step()
            
            if not step_result:
                with lock:
                    is_running = False
                safe_emit("simulation_ended", {})
                break
            
            with lock:
                current_time = simulation.current_time
                should_update = int(current_time * 10) % 5 == 0
            
            if should_update:
                with lock:
                    data = {
                        "time": simulation.current_time,
                        "agents": get_agents_data(simulation),
                        "traffic_lights": get_traffic_lights_data(simulation),
                        "traffic_light_agents": get_traffic_light_agents_data(simulation),
                        "statistics": simulation.get_statistics()
                    }
                safe_emit("simulation_update", data)
            
            # 触发 LLM 决策（放入队列，不阻塞）
            decision_counter += 1
            if decision_counter % 100 == 0:  # 降低频率
                with lock:
                    if simulation and simulation.vehicles:
                        import random
                        vehicles = list(simulation.vehicles.values())
                        vehicle = random.choice(vehicles)
                        if vehicle.use_llm:
                            try:
                                llm_decision_queue.put((vehicle.agent_id, None))
                            except:
                                pass
            
            time.sleep(0.05)
            
        except Exception as e:
            print(f"[仿真循环错误] {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)
    
    print("[仿真循环] 结束")

@app.route("/api/network", methods=["GET"])
def get_network():
    with lock:
        if simulation is None:
            return jsonify({"error": "仿真未初始化"}), 400
        return jsonify(get_network_data(simulation))

@app.route("/api/state", methods=["GET"])
def get_state():
    with lock:
        if simulation is None:
            return jsonify({"error": "仿真未初始化"}), 400
        
        return jsonify({
            "time": simulation.current_time,
            "is_running": is_running,
            "agents": get_agents_data(simulation),
            "traffic_lights": get_traffic_lights_data(simulation),
            "traffic_light_agents": get_traffic_light_agents_data(simulation),
            "statistics": simulation.get_statistics()
        })

@app.route("/api/control", methods=["POST"])
def control_simulation():
    global simulation, is_running, simulation_thread
    
    data = request.json or {}
    action = data.get("action")
    
    print(f"[Control] 收到请求: {action}")
    
    if action == "start":
        with lock:
            if simulation is None:
                simulation = create_demo_simulation()
                print("[Control] 创建新仿真环境")
            
            if not is_running:
                is_running = True
                simulation.start()
                print("[Control] 仿真已启动")
                simulation_thread = threading.Thread(target=simulation_loop)
                simulation_thread.daemon = True
                simulation_thread.start()
                print("[Control] 仿真线程已启动")
        return jsonify({"status": "started"})
    
    elif action == "pause":
        with lock:
            is_running = False
            if simulation:
                simulation.pause()
        return jsonify({"status": "paused"})
    
    elif action == "reset":
        with lock:
            is_running = False
            if simulation:
                simulation.reset()
            simulation = create_demo_simulation()
        return jsonify({"status": "reset"})
    
    return jsonify({"error": "未知操作"}), 400

@app.route("/api/agent/<agent_id>/decision", methods=["POST"])
def get_agent_decision(agent_id: str):
    """获取智能体决策（触发LLM决策）。"""
    with lock:
        if simulation is None:
            return jsonify({"error": "仿真未初始化"}), 400
        
        agent = simulation.agents.get(agent_id)
        if not agent:
            return jsonify({"error": "智能体未找到"}), 404
        
        # 获取感知信息
        perception = {}
        if hasattr(agent, "perceive"):
            perception = agent.perceive()
        
        # 尝试获取LLM决策
        decision_result = {"action": "proceed", "reason": "规则决策", "confidence": 0.5}
        
        if hasattr(agent, 'use_llm') and agent.use_llm and LLM_AVAILABLE:
            try:
                # 触发LLM决策
                if hasattr(agent, 'llm_decide'):
                    llm_result = agent.llm_decide(perception)
                    if llm_result and isinstance(llm_result, dict):
                        decision_result = llm_result
                        print(f"[API决策] {agent_id}: {decision_result}")
            except Exception as e:
                print(f"[API决策] LLM失败: {e}")
        
        return jsonify({
            "agent_id": agent_id,
            "perception": perception,
            "decision": decision_result,
            "timestamp": simulation.current_time if simulation else 0
        })

@app.route("/api/traffic-light/<agent_id>/status", methods=["GET"])
def get_traffic_light_status(agent_id: str):
    """获取红绿灯智能体详细状态。"""
    with lock:
        if simulation is None:
            return jsonify({"error": "仿真未初始化"}), 400
        
        agent = simulation.agents.get(agent_id)
        if not agent or not isinstance(agent, TrafficLightAgent):
            return jsonify({"error": "红绿灯智能体未找到"}), 404
        
        # 获取详细状态
        status = agent.get_status()
        perception = agent.perceive()
        
        return jsonify({
            "agent_id": agent_id,
            "status": status,
            "perception": perception,
            "history": agent.history[-5:] if hasattr(agent, 'history') else []
        })

@socketio.on("connect")
def handle_connect():
    print(f"[WebSocket] 客户端已连接: {request.sid}")
    emit("connected", {"message": "连接成功"})

@socketio.on("disconnect")
def handle_disconnect():
    print(f"[WebSocket] 客户端已断开: {request.sid}")

@socketio.on("get_network")
def handle_get_network():
    with lock:
        if simulation:
            emit("network_data", get_network_data(simulation))

@socketio.on("spawn_vehicle")
def handle_spawn_vehicle(data):
    with lock:
        if simulation is None:
            emit("error", {"message": "仿真未运行"})
            return
        
        import random
        all_nodes = list(simulation.road_network.nodes.values())
        if len(all_nodes) < 2:
            emit("error", {"message": "节点不足"})
            return
        
        start = random.choice(all_nodes)
        available_ends = [n for n in all_nodes if n != start]
        end = random.choice(available_ends)
        
        vtype_name = data.get("vehicle_type", "CAR")
        vtype = VehicleType[vtype_name]
        
        vehicle = simulation.spawn_vehicle(start, end, vtype)
        
        if vehicle:
            vehicle.use_llm = LLM_AVAILABLE
            print(f"[生成车辆] {vehicle.agent_id} (LLM={'启用' if LLM_AVAILABLE else '禁用'})")
            emit("vehicle_spawned", {
                "vehicle_id": vehicle.agent_id,
                "start": start.name,
                "end": end.name,
                "route_length": len(vehicle.route)
            })
        else:
            emit("error", {"message": "生成车辆失败"})

# ========== 路网规划模式 (Road Planning Mode) ==========

# 路网规划模式全局状态
planning_simulation: SimulationEnvironment | None = None
planning_thread: threading.Thread | None = None
is_planning_running = False
planning_lock = threading.Lock()

def create_planning_simulation(agent_configs: dict | None = None) -> SimulationEnvironment:
    """创建路网规划模式的仿真环境 - 从2x2网格开始。
    
    Args:
        agent_configs: 智能体LLM配置，格式为 {'vehicle': True, 'traffic_light': True, 'planning': True}
    """
    from city.agents.planning_agent import PlanningAgent
    from city.agents.zoning_agent import ZoningAgent
    
    # 默认配置
    configs = {
        'vehicle': True,
        'traffic_light': True,
        'planning': True
    }
    if agent_configs:
        configs.update(agent_configs)
    
    print(f"[路网规划] 智能体LLM配置: {configs}")
    
    network = RoadNetwork("planning_grid")
    nodes: dict[tuple[int, int], Node] = {}
    
    # 从2x2网格开始
    GRID_SIZE = 2
    NODE_SPACING = 300  # 300米间距
    
    # 创建节点
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            pos = Vector2D(j * NODE_SPACING, i * NODE_SPACING)
            node = Node(position=pos, name=f"node_{i}_{j}")
            network.add_node(node)
            nodes[(i, j)] = node
    
    # 创建基础网格边
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            current = nodes[(i, j)]
            # 向右连接
            if j + 1 < GRID_SIZE:
                right = nodes[(i, j + 1)]
                network.create_edge(current, right, num_lanes=2, bidirectional=True)
            # 向下连接
            if i + 1 < GRID_SIZE:
                down = nodes[(i + 1, j)]
                network.create_edge(current, down, num_lanes=2, bidirectional=True)
    
    # 创建仿真环境
    config = SimulationConfig()
    env = SimulationEnvironment(network, config)
    
    # 添加人口驱动的路网规划智能体（专注于路网扩展）
    # 兼容旧版配置 'planning'，新版使用 'road_planning'
    road_planning_use_llm = configs.get('road_planning', configs.get('planning', True)) and LLM_AVAILABLE
    planning_agent = PlanningAgent(
        environment=env,
        use_llm=road_planning_use_llm,
        population_per_node=5,       # 每个节点5辆车（人口）- 增加初始容量
        expansion_threshold=0.5,     # 50%容量时扩张 - 降低阈值便于快速扩张
        spawn_interval=2.0,          # 每2秒尝试生成新车 - 加快生成
        max_nodes=20,
        min_edge_length=200.0,
        max_edge_length=500.0
    )
    env.add_agent(planning_agent)
    planning_agent.activate()
    print(f"[路网规划] 添加路网规划智能体 {planning_agent.agent_id} (LLM={'启用' if road_planning_use_llm else '禁用'})")
    
    # 添加城市规划智能体（专注于功能区域规划）
    # 兼容旧版配置 'planning'，新版使用 'zoning'
    zoning_use_llm = configs.get('zoning', configs.get('planning', True)) and LLM_AVAILABLE
    zoning_agent = ZoningAgent(
        environment=env,
        use_llm=zoning_use_llm,
        planning_interval=15.0,      # 每15秒尝试规划
        max_zones=30
    )
    env.add_agent(zoning_agent)
    zoning_agent.activate()
    print(f"[城市规划] 添加城市规划智能体 {zoning_agent.agent_id} (LLM={'启用' if zoning_use_llm else '禁用'})")
    
    # 创建初始功能区域（让页面打开时就有内容显示）
    from city.urban_planning.zone import Zone, ZoneType
    initial_zones = [
        (ZoneType.RESIDENTIAL, Vector2D(150, 150), 100, 80, "阳光小区"),
        (ZoneType.COMMERCIAL, Vector2D(450, 150), 80, 60, "中心商业街"),
        (ZoneType.SCHOOL, Vector2D(150, 450), 90, 70, "希望小学"),
        (ZoneType.PARK, Vector2D(450, 450), 100, 100, "市民公园"),
    ]
    
    for zone_type, center, width, height, name in initial_zones:
        zone = Zone(
            zone_type=zone_type,
            center=center,
            width=width,
            height=height,
            name=name
        )
        zone.planning_time = 0.0
        zone.planning_reason = "初始规划"
        zone.population = int(zone.max_population * 0.3)  # 初始30%人口
        zoning_agent.zone_manager.add_zone(zone)
    
    print(f"[城市规划] 创建 {len(initial_zones)} 个初始功能区域")
    
    print(f"[系统] 共添加 {len(env.agents)} 个智能体")
    
    # 存储智能体LLM配置到环境，供生成车辆时使用
    env.agent_configs = configs
    
    # 为所有交叉口添加红绿灯
    traffic_light_use_llm = configs.get('traffic_light', True) and LLM_AVAILABLE
    for node in network.nodes.values():
        # 计算节点的总边数（入边 + 出边）
        total_edges = len(node.incoming_edges) + len(node.outgoing_edges)
        if total_edges > 2:  # 交叉口
            tl = TrafficLight(node=node, cycle_time=60.0)
            node.traffic_light = tl
            
            # 添加红绿灯智能体
            tl_agent = TrafficLightAgent(
                control_node=node,
                name=f"TL_{node.name}",
                environment=env,
                use_llm=traffic_light_use_llm
            )
            tl_agent.activate()
            env.add_agent(tl_agent)
            print(f"[路网规划] 添加红绿灯智能体 {tl_agent.agent_id} (LLM={'启用' if traffic_light_use_llm else '禁用'})")
    
    print(f"[路网规划] 创建2x2初始网格，节点间距{NODE_SPACING}m")
    return env

def planning_simulation_loop():
    """路网规划仿真循环。"""
    global is_planning_running
    
    print("[路网规划循环] 启动", flush=True)
    step_count = 0
    last_log_time = time.time()
    
    while True:
        try:
            # 检查是否应该停止
            with planning_lock:
                should_stop = not is_planning_running or planning_simulation is None
            
            if should_stop:
                print("[路网规划循环] 停止", flush=True)
                break
            
            # 执行仿真步（在锁内）
            with planning_lock:
                step_result = planning_simulation.step()
                step_count += 1
                current_time = planning_simulation.current_time
                vehicles_count = len(planning_simulation.vehicles)
            
            # 打印每一步（用于调试）
            if step_count % 20 == 0:  # 每20步打印一次
                print(f"[仿真步] step={step_count}, time={current_time:.1f}s, vehicles={vehicles_count}", flush=True)
            
            if not step_result:
                print(f"[路网规划循环] step() 返回 False，停止", flush=True)
                with planning_lock:
                    is_planning_running = False
                safe_emit("planning_ended", {})
                break
            
            # 每10步发送一次更新
            if step_count % 10 == 0:
                try:
                    with planning_lock:
                        # 获取网络数据
                        network_data = get_network_data(planning_simulation) if planning_simulation else {"nodes": [], "edges": []}
                        # 获取车辆数据
                        agents_data = get_agents_data(planning_simulation) if planning_simulation else {"vehicles": [], "pedestrians": []}
                        # 获取交通灯数据
                        traffic_lights_data = get_traffic_lights_data(planning_simulation) if planning_simulation else []
                        # 获取区域数据
                        zones_data = get_zoning_data(planning_simulation) if planning_simulation else []
                        # 获取智能体状态
                        from city.agents.planning_agent import PlanningAgent
                        from city.agents.zoning_agent import ZoningAgent
                        planning_agent_status = None
                        zoning_agent_status = None
                        for agent in planning_simulation.agents.values():
                            if isinstance(agent, PlanningAgent):
                                planning_agent_status = agent.get_status()
                            elif isinstance(agent, ZoningAgent):
                                zoning_agent_status = agent.get_status()
                    
                    data = {
                        "time": current_time,
                        "is_running": is_planning_running,
                        "agents": agents_data,
                        "traffic_lights": traffic_lights_data,
                        "network": network_data,
                        "zones": zones_data,
                        "planning_agent": planning_agent_status,
                        "zoning_agent": zoning_agent_status,
                        "expansion_history": [],
                        "statistics": {"active_vehicles": vehicles_count}
                    }
                    safe_emit("planning_update", data)
                    
                    # 每50步打印发送详情（包含zones数量）
                    if step_count % 50 == 0:
                        print(f"[WebSocket] 发送更新: time={current_time:.1f}s, nodes={len(network_data.get('nodes', []))}, zones={len(zones_data)}, vehicles={len(agents_data.get('vehicles', []))}", flush=True)
                        
                except Exception as e:
                    print(f"[WebSocket] 发送失败: {e}", flush=True)
            
            # 每秒打印一次状态
            if time.time() - last_log_time >= 1.0:
                print(f"[状态] time={current_time:.1f}s, step={step_count}, vehicles={vehicles_count}", flush=True)
                last_log_time = time.time()
            
            time.sleep(0.05)
            
        except Exception as e:
            print(f"[路网规划循环错误] {e}", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(0.1)
    
    print(f"[路网规划循环] 结束，共运行 {step_count} 步", flush=True)

# 路网规划模式API端点
@app.route("/api/planning/network", methods=["GET"])
def get_planning_network():
    """获取路网规划模式的网络状态。"""
    with planning_lock:
        if planning_simulation is None:
            return jsonify({"error": "路网规划仿真未初始化"}), 400
        return jsonify(get_network_data(planning_simulation))

@app.route("/api/planning/state", methods=["GET"])
def get_planning_state():
    """获取路网规划模式的完整状态（快速响应版）。"""
    with planning_lock:
        if planning_simulation is None:
            return jsonify({"error": "路网规划仿真未初始化"}), 400
        
        # 只收集基本数据，避免复杂计算
        from city.agents.planning_agent import PlanningAgent
        from city.agents.zoning_agent import ZoningAgent
        
        planning_agent_status = None
        zoning_agent_status = None
        for agent in planning_simulation.agents.values():
            if isinstance(agent, PlanningAgent):
                planning_agent_status = agent.get_status()
            elif isinstance(agent, ZoningAgent):
                zoning_agent_status = agent.get_status()
        
        # 简化的agents数据
        simple_agents = {
            "vehicles": [{"id": v.agent_id, "type": "vehicle"} for v in planning_simulation.vehicles.values()],
            "pedestrians": []
        }
        
        # 获取区域数据
        zones_data = get_zoning_data(planning_simulation)
        
        return jsonify({
            "time": planning_simulation.current_time,
            "is_running": is_planning_running,
            "agents": simple_agents,
            "traffic_lights": [],
            "network": {"nodes": [], "edges": []},
            "expansion_history": [],
            "planning_agent": planning_agent_status,
            "zoning_agent": zoning_agent_status,
            "zones": zones_data,
            "statistics": {"active_vehicles": len(planning_simulation.vehicles)}
        })

@app.route("/api/planning/control", methods=["POST"])
def control_planning_simulation():
    """控制路网规划仿真。"""
    global planning_simulation, is_planning_running, planning_thread
    
    data = request.json or {}
    action = data.get("action")
    agent_configs = data.get("agent_configs", {
        'vehicle': True,
        'traffic_light': True,
        'planning': True
    })
    
    print(f"[Planning Control] 收到请求: action={action}", flush=True)
    
    if action == "start":
        with planning_lock:
            print(f"[Planning Control] 当前状态: planning_simulation={planning_simulation is not None}, is_planning_running={is_planning_running}", flush=True)
            
            if planning_simulation is None:
                print("[Planning Control] 创建新仿真环境...", flush=True)
                planning_simulation = create_planning_simulation(agent_configs)
                print("[Planning Control] 仿真环境创建完成", flush=True)
            
            if not is_planning_running:
                is_planning_running = True
                planning_simulation.start()
                print("[Planning Control] 仿真已启动", flush=True)
                
                # 检查线程是否已在运行
                if planning_thread is None or not planning_thread.is_alive():
                    print("[Planning Control] 启动仿真线程...", flush=True)
                    planning_thread = threading.Thread(target=planning_simulation_loop)
                    planning_thread.daemon = True
                    planning_thread.start()
                    print("[Planning Control] 仿真线程已启动", flush=True)
                else:
                    print("[Planning Control] 仿真线程已在运行", flush=True)
            else:
                print("[Planning Control] 仿真已在运行中", flush=True)
                
        return jsonify({"status": "started", "agent_configs": agent_configs})
    
    elif action == "pause":
        print("[Planning Control] 暂停仿真", flush=True)
        with planning_lock:
            is_planning_running = False
            if planning_simulation:
                planning_simulation.pause()
        return jsonify({"status": "paused"})
    
    elif action == "reset":
        print("[Planning Control] 重置仿真", flush=True)
        with planning_lock:
            is_planning_running = False
            if planning_simulation:
                planning_simulation.reset()
            planning_simulation = create_planning_simulation(agent_configs)
        return jsonify({"status": "reset", "agent_configs": agent_configs})
    
    print(f"[Planning Control] 未知操作: {action}", flush=True)
    return jsonify({"error": "未知操作"}), 400

@app.route("/api/planning/spawn", methods=["POST"])
def spawn_planning_vehicle():
    """在路网规划模式中生成车辆。"""
    with planning_lock:
        if planning_simulation is None:
            return jsonify({"error": "路网规划仿真未初始化"}), 400
        
        data = request.json or {}
        
        import random
        all_nodes = list(planning_simulation.road_network.nodes.values())
        if len(all_nodes) < 2:
            return jsonify({"error": "节点不足"}), 400
        
        start = random.choice(all_nodes)
        available_ends = [n for n in all_nodes if n != start]
        end = random.choice(available_ends)
        
        vtype_name = data.get("vehicle_type", "CAR")
        vtype = VehicleType[vtype_name]
        
        vehicle = planning_simulation.spawn_vehicle(start, end, vtype)
        
        if vehicle:
            vehicle.use_llm = LLM_AVAILABLE
            print(f"[路网规划-生成车辆] {vehicle.agent_id}")
            return jsonify({
                "vehicle_id": vehicle.agent_id,
                "start": start.name,
                "end": end.name,
                "route_length": len(vehicle.route)
            })
        else:
            return jsonify({"error": "生成车辆失败"}), 500

@app.route("/api/planning/expansion", methods=["GET"])
def get_expansion_history():
    """获取路网扩展历史。"""
    with planning_lock:
        if planning_simulation is None:
            return jsonify({"error": "路网规划仿真未初始化"}), 400
        
        return jsonify({
            "expansion_history": planning_simulation.get_expansion_history(),
            "current_time": planning_simulation.current_time
        })

@app.route("/api/planning/debug", methods=["GET"])
def get_planning_debug():
    """获取路网规划调试信息。"""
    with planning_lock:
        if planning_simulation is None:
            return jsonify({"error": "路网规划仿真未初始化"}), 400
        
        network = planning_simulation.road_network
        
        # 收集节点连接信息
        nodes_info = []
        for node in network.nodes.values():
            connections = [e.to_node.node_id for e in node.outgoing_edges]
            nodes_info.append({
                "id": node.node_id,
                "name": node.name,
                "x": node.position.x,
                "y": node.position.y,
                "outgoing_edges": connections,
                "outgoing_count": len(node.outgoing_edges),
                "incoming_count": len(node.incoming_edges)
            })
        
        # 收集边信息
        edges_info = []
        for edge in network.edges.values():
            edges_info.append({
                "id": edge.edge_id,
                "from": edge.from_node.node_id,
                "to": edge.to_node.node_id,
                "length": edge.length
            })
        
        return jsonify({
            "nodes": nodes_info,
            "edges": edges_info,
            "total_nodes": len(network.nodes),
            "total_edges": len(network.edges)
        })

# WebSocket事件处理
@socketio.on("planning_connect")
def handle_planning_connect():
    """客户端连接路网规划模式。"""
    print(f"[WebSocket] 路网规划客户端已连接: {request.sid}")
    emit("planning_connected", {"message": "路网规划模式连接成功"})

@socketio.on("get_planning_network")
def handle_get_planning_network():
    """获取路网规划网络数据。"""
    with planning_lock:
        if planning_simulation:
            emit("planning_network_data", get_network_data(planning_simulation))

@socketio.on("planning_spawn_vehicle")
def handle_planning_spawn_vehicle(data):
    """在路网规划模式中生成车辆。"""
    with planning_lock:
        if planning_simulation is None:
            emit("error", {"message": "路网规划仿真未运行"})
            return
        
        import random
        all_nodes = list(planning_simulation.road_network.nodes.values())
        if len(all_nodes) < 2:
            emit("error", {"message": "节点不足"})
            return
        
        start = random.choice(all_nodes)
        available_ends = [n for n in all_nodes if n != start]
        end = random.choice(available_ends)
        
        vtype_name = data.get("vehicle_type", "CAR")
        vtype = VehicleType[vtype_name]
        
        vehicle = planning_simulation.spawn_vehicle(start, end, vtype)
        
        if vehicle:
            vehicle.use_llm = LLM_AVAILABLE
            print(f"[路网规划-生成车辆] {vehicle.agent_id}")
            emit("planning_vehicle_spawned", {
                "vehicle_id": vehicle.agent_id,
                "start": start.name,
                "end": end.name,
                "route_length": len(vehicle.route)
            })
        else:
            emit("error", {"message": "生成车辆失败"})

# ========== 城市规划模式 (Urban Planning Mode) ==========

# 城市规划模式全局状态
zoning_simulation: SimulationEnvironment | None = None
zoning_thread: threading.Thread | None = None
is_zoning_running = False
zoning_lock = threading.Lock()

def create_zoning_simulation() -> SimulationEnvironment:
    """创建城市规划模式的仿真环境。"""
    from city.agents.planning_agent import PlanningAgent
    from city.urban_planning.zoning_agent import ZoningAgent
    
    network = RoadNetwork("zoning_city")
    nodes: dict[tuple[int, int], Node] = {}
    
    # 创建3x3网格作为基础
    GRID_SIZE = 3
    NODE_SPACING = 400
    
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            pos = Vector2D(j * NODE_SPACING, i * NODE_SPACING)
            node = Node(position=pos, name=f"node_{i}_{j}")
            network.add_node(node)
            nodes[(i, j)] = node
    
    # 创建基础网格边
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            current = nodes[(i, j)]
            if j + 1 < GRID_SIZE:
                right = nodes[(i, j + 1)]
                network.create_edge(current, right, num_lanes=2, bidirectional=True)
            if i + 1 < GRID_SIZE:
                down = nodes[(i + 1, j)]
                network.create_edge(current, down, num_lanes=2, bidirectional=True)
    
    # 创建仿真环境
    config = SimulationConfig()
    env = SimulationEnvironment(network, config)
    
    # 添加路网规划Agent
    planning_agent = PlanningAgent(
        environment=env,
        use_llm=LLM_AVAILABLE,
        population_per_node=3,
        expansion_threshold=0.7,
        spawn_interval=4.0,
        max_nodes=16,
        min_edge_length=200.0,
        max_edge_length=500.0
    )
    env.add_agent(planning_agent)
    planning_agent.activate()
    
    # 添加城市规划Agent
    zoning_agent = ZoningAgent(
        environment=env,
        use_llm=LLM_AVAILABLE,
        planning_interval=20.0,
        max_zones=25,
        min_zone_size=60.0,
        max_zone_size=150.0,
        buffer_distance=20.0
    )
    env.add_agent(zoning_agent)
    
    # 添加红绿灯
    for node in network.nodes.values():
        total_edges = len(node.incoming_edges) + len(node.outgoing_edges)
        if total_edges > 2:
            tl = TrafficLight(node=node, cycle_time=60.0)
            node.traffic_light = tl
            tl_agent = TrafficLightAgent(
                control_node=node,
                name=f"TL_{node.name}",
                environment=env,
                use_llm=LLM_AVAILABLE
            )
            tl_agent.activate()
            env.add_agent(tl_agent)
    
    print(f"[城市规划] 创建3x3初始网格，添加了路网规划和城市规划Agent")
    return env

def get_zoning_data(env: SimulationEnvironment) -> list:
    """获取城市功能区域数据。"""
    from city.agents.zoning_agent import ZoningAgent
    
    zones_data = []
    for agent in env.agents.values():
        # 从独立的城市规划智能体获取区域数据
        if isinstance(agent, ZoningAgent):
            for zone in agent.zone_manager.zones.values():
                # 确保所有数据都是可JSON序列化的
                bounds = zone.bounds
                if bounds:
                    bounds = [float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])]
                
                zones_data.append({
                    'zone_id': zone.zone_id,
                    'zone_type': zone.zone_type.name,
                    'zone_type_display': zone.zone_type.display_name,
                    'name': zone.name,
                    'center_x': float(zone.center.x),
                    'center_y': float(zone.center.y),
                    'width': float(zone.width),
                    'height': float(zone.height),
                    'area': float(zone.area),
                    'color': zone.zone_type.color,
                    'border_color': zone.zone_type.border_color,
                    'population': int(zone.population),
                    'max_population': int(zone.max_population),
                    'development_level': float(zone.development_level),
                    'bounds': bounds,
                    'planning_time': zone.planning_time,
                    'planning_reason': zone.planning_reason
                })
            break
    return zones_data

def get_zoning_agent_status(env: SimulationEnvironment) -> dict | None:
    """获取城市规划智能体状态。"""
    from city.agents.zoning_agent import ZoningAgent
    
    for agent in env.agents.values():
        if isinstance(agent, ZoningAgent):
            return agent.get_status()
    return None

def get_zoning_agent_status(env: SimulationEnvironment) -> dict | None:
    """获取城市规划Agent状态。"""
    from city.urban_planning.zoning_agent import ZoningAgent
    
    for agent in env.agents.values():
        if isinstance(agent, ZoningAgent):
            return agent.get_status()
    return None

def zoning_simulation_loop():
    """城市规划仿真循环。"""
    global is_zoning_running
    
    print("[城市规划循环] 启动")
    
    while True:
        with zoning_lock:
            if not is_zoning_running or zoning_simulation is None:
                print("[城市规划循环] 停止")
                break
        
        try:
            with zoning_lock:
                if zoning_simulation is None:
                    break
                step_result = zoning_simulation.step()
            
            if not step_result:
                with zoning_lock:
                    is_zoning_running = False
                safe_emit("zoning_ended", {})
                break
            
            # 定期发送更新
            with zoning_lock:
                current_time = zoning_simulation.current_time
                should_update = int(current_time * 10) % 3 == 0
            
            if should_update:
                with zoning_lock:
                    data = {
                        "time": zoning_simulation.current_time,
                        "agents": get_agents_data(zoning_simulation),
                        "traffic_lights": get_traffic_lights_data(zoning_simulation),
                        "network": get_network_data(zoning_simulation),
                        "zones": get_zoning_data(zoning_simulation),
                        "zoning_agent": get_zoning_agent_status(zoning_simulation),
                        "statistics": zoning_simulation.get_statistics()
                    }
                safe_emit("zoning_update", data)
            
            time.sleep(0.05)
            
        except Exception as e:
            print(f"[城市规划循环错误] {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)
    
    print("[城市规划循环] 结束")

# 城市规划模式API端点
@app.route("/api/zoning/network", methods=["GET"])
def get_zoning_network():
    """获取城市规划模式的网络状态。"""
    with zoning_lock:
        if zoning_simulation is None:
            return jsonify({"error": "城市规划仿真未初始化"}), 400
        return jsonify(get_network_data(zoning_simulation))

@app.route("/api/zoning/zones", methods=["GET"])
def get_zoning_zones():
    """获取所有功能区域。"""
    with zoning_lock:
        if zoning_simulation is None:
            return jsonify({"error": "城市规划仿真未初始化"}), 400
        return jsonify({"zones": get_zoning_data(zoning_simulation)})

@app.route("/api/zoning/state", methods=["GET"])
def get_zoning_state():
    """获取城市规划模式的完整状态。"""
    with zoning_lock:
        if zoning_simulation is None:
            return jsonify({"error": "城市规划仿真未初始化"}), 400
        
        return jsonify({
            "time": zoning_simulation.current_time,
            "is_running": is_zoning_running,
            "agents": get_agents_data(zoning_simulation),
            "traffic_lights": get_traffic_lights_data(zoning_simulation),
            "network": get_network_data(zoning_simulation),
            "zones": get_zoning_data(zoning_simulation),
            "zoning_agent": get_zoning_agent_status(zoning_simulation),
            "statistics": zoning_simulation.get_statistics()
        })

@app.route("/api/zoning/control", methods=["POST"])
def control_zoning_simulation():
    """控制城市规划仿真。"""
    global zoning_simulation, is_zoning_running, zoning_thread
    
    data = request.json or {}
    action = data.get("action")
    
    print(f"[Zoning Control] 收到请求: {action}")
    
    if action == "start":
        with zoning_lock:
            if zoning_simulation is None:
                zoning_simulation = create_zoning_simulation()
                print("[Zoning Control] 创建新城市规划环境")
            
            if not is_zoning_running:
                is_zoning_running = True
                zoning_simulation.start()
                print("[Zoning Control] 城市规划仿真已启动")
                zoning_thread = threading.Thread(target=zoning_simulation_loop)
                zoning_thread.daemon = True
                zoning_thread.start()
                print("[Zoning Control] 城市规划线程已启动")
        return jsonify({"status": "started"})
    
    elif action == "pause":
        with zoning_lock:
            is_zoning_running = False
            if zoning_simulation:
                zoning_simulation.pause()
        return jsonify({"status": "paused"})
    
    elif action == "reset":
        with zoning_lock:
            is_zoning_running = False
            if zoning_simulation:
                zoning_simulation.reset()
            zoning_simulation = create_zoning_simulation()
        return jsonify({"status": "reset"})
    
    return jsonify({"error": "未知操作"}), 400

@app.route("/api/zoning/spawn", methods=["POST"])
def spawn_zoning_vehicle():
    """在城市规划模式中生成车辆。"""
    with zoning_lock:
        if zoning_simulation is None:
            return jsonify({"error": "城市规划仿真未初始化"}), 400
        
        data = request.json or {}
        
        import random
        all_nodes = list(zoning_simulation.road_network.nodes.values())
        if len(all_nodes) < 2:
            return jsonify({"error": "节点不足"}), 400
        
        start = random.choice(all_nodes)
        available_ends = [n for n in all_nodes if n != start]
        end = random.choice(available_ends)
        
        vtype_name = data.get("vehicle_type", "CAR")
        vtype = VehicleType[vtype_name]
        
        vehicle = zoning_simulation.spawn_vehicle(start, end, vtype)
        
        if vehicle:
            vehicle.use_llm = LLM_AVAILABLE
            print(f"[城市规划-生成车辆] {vehicle.agent_id}")
            return jsonify({
                "vehicle_id": vehicle.agent_id,
                "start": start.name,
                "end": end.name,
                "route_length": len(vehicle.route)
            })
        else:
            return jsonify({"error": "生成车辆失败"}), 500

# WebSocket事件处理
@socketio.on("zoning_connect")
def handle_zoning_connect():
    """客户端连接城市规划模式。"""
    print(f"[WebSocket] 城市规划客户端已连接: {request.sid}")
    emit("zoning_connected", {"message": "城市规划模式连接成功"})

@socketio.on("get_zoning_network")
def handle_get_zoning_network():
    """获取城市规划网络数据。"""
    with zoning_lock:
        if zoning_simulation:
            emit("zoning_network_data", get_network_data(zoning_simulation))

@socketio.on("get_zoning_zones")
def handle_get_zoning_zones():
    """获取功能区域数据。"""
    with zoning_lock:
        if zoning_simulation:
            emit("zoning_zones_data", get_zoning_data(zoning_simulation))

@socketio.on("zoning_spawn_vehicle")
def handle_zoning_spawn_vehicle(data):
    """在城市规划模式中生成车辆。"""
    with zoning_lock:
        if zoning_simulation is None:
            emit("error", {"message": "城市规划仿真未运行"})
            return
        
        import random
        all_nodes = list(zoning_simulation.road_network.nodes.values())
        if len(all_nodes) < 2:
            emit("error", {"message": "节点不足"})
            return
        
        start = random.choice(all_nodes)
        available_ends = [n for n in all_nodes if n != start]
        end = random.choice(available_ends)
        
        vtype_name = data.get("vehicle_type", "CAR")
        vtype = VehicleType[vtype_name]
        
        vehicle = zoning_simulation.spawn_vehicle(start, end, vtype)
        
        if vehicle:
            vehicle.use_llm = LLM_AVAILABLE
            print(f"[城市规划-生成车辆] {vehicle.agent_id}")
            emit("zoning_vehicle_spawned", {
                "vehicle_id": vehicle.agent_id,
                "start": start.name,
                "end": end.name,
                "route_length": len(vehicle.route)
            })
        else:
            emit("error", {"message": "生成车辆失败"})

# ========== 主入口 ==========

if __name__ == "__main__":
    simulation = create_demo_simulation()
    print("仿真环境已初始化")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
