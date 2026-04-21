"""
CITY 交通仿真后端 API 服务。
"""

import sys
import os
import json
import math
import random
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
from city.environment.initial_network import (
    create_cross_network,
    create_grid_network,
    create_radial_network,
)
from city.agents.vehicle import Vehicle, VehicleType
from city.agents.pedestrian import Pedestrian
from city.agents.traffic_manager import TrafficManager
from city.agents.traffic_light_agent import TrafficLightAgent
from city.agents.planning_agent import PlanningAgent
from city.agents.zoning_agent import ZoningAgent
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
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    allow_upgrades=False,
)

# 全局状态
simulation: SimulationEnvironment | None = None
simulation_thread: threading.Thread | None = None
is_running = False
lock = threading.Lock()

# LLM 决策队列
llm_decision_queue = queue.Queue()

def create_demo_simulation(agent_configs: dict | None = None) -> SimulationEnvironment:
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
    configs = {
        'vehicle': True,
        'traffic_light': True,
        'road_planning': True,
        'zoning': True,
    }
    if agent_configs:
        configs.update(agent_configs)
    env.agent_configs = configs
    
    # 4. 为所有交叉口添加智能红绿灯智能体
    for i in range(1, GRID_SIZE - 1):
        for j in range(1, GRID_SIZE - 1):
            intersection_node = nodes[(i, j)]
            if intersection_node.is_intersection:
                traffic_light_agent = TrafficLightAgent(
                    control_node=intersection_node,
                    environment=env,
                    use_llm=configs.get('traffic_light', True) and LLM_AVAILABLE,
                    enable_memory=bool(configs.get('traffic_light', True)),
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

def _get_memory_agent_kind(agent: Any) -> str:
    """将后端智能体映射为前端记忆面板使用的类型。"""
    if isinstance(agent, Vehicle):
        return "vehicle"
    if isinstance(agent, TrafficLightAgent):
        return "traffic_light"
    if isinstance(agent, ZoningAgent):
        return "zoning"
    if isinstance(agent, PlanningAgent):
        return "planning"
    if isinstance(agent, Pedestrian):
        return "pedestrian"
    return agent.agent_type.name.lower() if hasattr(agent.agent_type, "name") else type(agent).__name__.lower()


def _build_agent_memory_payload(env: SimulationEnvironment) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """构建前端记忆面板所需的数据。"""
    agent_memories_data: dict[str, Any] = {}
    agents_with_memory_list: list[dict[str, Any]] = []

    for agent in env.agents.values():
        if not hasattr(agent, 'has_memory') or not agent.has_memory():
            continue

        memory_count = 0
        memory_summary = "已启用，暂无记忆条目"

        try:
            memory = agent.get_memory()
            if hasattr(agent, 'has_memory_data') and agent.has_memory_data():
                memory_data = memory.to_dict()
                agent_memories_data[agent.agent_id] = memory_data
                memory_count = memory_data.get("statistics", {}).get("total_memories", 0)
                memory_summary = memory.generate_summary() or memory_summary
        except Exception as e:
            print(f"[记忆数据] 获取智能体 {agent.agent_id} 记忆失败: {e}")

        agents_with_memory_list.append({
            "id": agent.agent_id,
            "type": _get_memory_agent_kind(agent),
            "name": getattr(agent, 'name', agent.agent_id),
            "has_memory": True,
            "memory_count": memory_count,
            "memory_summary": memory_summary
        })

    return agent_memories_data, agents_with_memory_list

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
                    if planning_simulation:
                        agent_memories_data, agents_with_memory_list = _build_agent_memory_payload(planning_simulation)

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
            
            socketio.sleep(0.05)
            
        except Exception as e:
            print(f"[仿真循环错误] {e}")
            import traceback
            traceback.print_exc()
            socketio.sleep(0.1)
    
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
    agent_configs = data.get("agent_configs", {
        'vehicle': True,
        'traffic_light': True,
        'road_planning': True,
        'zoning': True,
    })
    agent_configs = data.get("agent_configs", {
        'vehicle': True,
        'traffic_light': True,
        'road_planning': True,
        'zoning': True,
    })
    
    print(f"[Control] 收到请求: {action}")
    
    if action == "start":
        with lock:
            if simulation is None:
                simulation = create_demo_simulation(agent_configs)
                print("[Control] 创建新仿真环境")
            
            if not is_running:
                is_running = True
                simulation.start()
                print("[Control] 仿真已启动")
                simulation_thread = threading.Thread(target=simulation_loop)
                simulation_thread.daemon = True
                simulation_thread.start()
                print("[Control] 仿真线程已启动")
        return jsonify({"status": "started", "agent_configs": agent_configs})
    
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
            simulation = create_demo_simulation(agent_configs)
        return jsonify({"status": "reset", "agent_configs": agent_configs})
    
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

def _build_default_planning_grid() -> RoadNetwork:
    """构建默认 2x2 初始路网。"""
    network = RoadNetwork("planning_grid")
    nodes: dict[tuple[int, int], Node] = {}
    grid_size = 2
    node_spacing = 300.0

    for i in range(grid_size):
        for j in range(grid_size):
            pos = Vector2D(j * node_spacing, i * node_spacing)
            node = Node(position=pos, name=f"node_{i}_{j}")
            network.add_node(node)
            nodes[(i, j)] = node

    for i in range(grid_size):
        for j in range(grid_size):
            current = nodes[(i, j)]
            if j + 1 < grid_size:
                right = nodes[(i, j + 1)]
                network.create_edge(current, right, num_lanes=2, bidirectional=True)
            if i + 1 < grid_size:
                down = nodes[(i + 1, j)]
                network.create_edge(current, down, num_lanes=2, bidirectional=True)

    return network

def _load_procedural_roadmap_conf() -> dict[str, Any] | None:
    """读取 procedural_city_generation 的 roadmap 配置。"""
    conf_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "procedural_city_generation-master",
        "procedural_city_generation",
        "inputs",
        "roadmap.conf",
    )
    if not os.path.exists(conf_path):
        return None

    try:
        with open(conf_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        parsed: dict[str, Any] = {}
        for key, value in raw.items():
            if isinstance(value, dict) and "value" in value:
                parsed[key] = value["value"]
            else:
                parsed[key] = value
        return parsed
    except Exception as e:
        print(f"[城市诞生] 读取 procedural 配置失败: {e}")
        return None

def _build_procedural_birth_network(configs: dict[str, Any]) -> RoadNetwork:
    """?? procedural ?????????????????"""
    conf = _load_procedural_roadmap_conf() or {}
    seed = int(configs.get("city_birth_seed", 42))
    rng = random.Random(seed)

    border_x = float(conf.get("border_x", 18))
    border_y = float(conf.get("border_y", 18))
    scale = float(configs.get("city_birth_scale", 120.0))
    target_nodes = max(8, min(40, int(configs.get("city_birth_nodes", 18))))

    min_distance = float(conf.get("min_distance", 0.6)) * scale
    grid_l = max(80.0, float(conf.get("gridlMin", 1.0)) * scale)
    organic_l = max(grid_l, float(conf.get("organiclMax", 1.6)) * scale)
    min_edge = float(configs.get("city_birth_min_edge", max(120.0, grid_l * 0.9)))
    max_edge = float(configs.get("city_birth_max_edge", max(420.0, organic_l * 1.35)))

    max_x = border_x * scale
    max_y = border_y * scale

    def normalize(vx: float, vy: float) -> tuple[float, float]:
        n = math.hypot(vx, vy)
        if n < 1e-6:
            return (1.0, 0.0)
        return (vx / n, vy / n)

    def rotate(vx: float, vy: float, deg: float) -> tuple[float, float]:
        rad = math.radians(deg)
        c = math.cos(rad)
        s = math.sin(rad)
        return (vx * c - vy * s, vx * s + vy * c)

    points: list[tuple[float, float]] = [(0.0, 0.0)]
    growth_edges: set[tuple[int, int]] = set()
    fronts: list[tuple[int, int, str]] = []

    axiom = conf.get("axiom") or [[2, 0], [3, 0], [0, 2], [0, 3], [-2, 0], [-3, 0], [0, -2], [0, -3]]
    max_seed_spokes = max(4, min(8, int(configs.get("city_birth_seed_spokes", 6))))
    seed_added = 0
    for idx, item in enumerate(axiom):
        if seed_added >= max_seed_spokes:
            break
        try:
            x = float(item[0]) * scale
            y = float(item[1]) * scale
        except Exception:
            continue
        if abs(x) > max_x or abs(y) > max_y:
            continue
        points.append((x, y))
        pid = len(points) - 1
        growth_edges.add((0, pid) if 0 < pid else (pid, 0))
        seed_added += 1
        if idx % 3 == 0:
            fronts.append((0, pid, "grid"))
        elif idx % 3 == 1:
            fronts.append((0, pid, "organic"))
        else:
            fronts.append((0, pid, "radial"))

    if len(points) < 3:
        points.extend([(grid_l, 0.0), (0.0, grid_l)])
        growth_edges.add((0, 1))
        growth_edges.add((0, 2))
        fronts.append((0, 1, "grid"))
        fronts.append((0, 2, "grid"))

    def too_close(nx: float, ny: float) -> bool:
        for px, py in points:
            if math.hypot(nx - px, ny - py) < min_distance:
                return True
        return False

    attempts = 0
    max_attempts = target_nodes * 160
    while len(points) < target_nodes and fronts and attempts < max_attempts:
        attempts += 1
        fi = rng.randrange(len(fronts))
        prev_idx, curr_idx, rule = fronts[fi]
        px, py = points[prev_idx]
        cx, cy = points[curr_idx]
        vx, vy = normalize(cx - px, cy - py)

        candidates: list[tuple[float, float, str]] = []
        if rule == "grid":
            step = rng.uniform(grid_l * 0.95, grid_l * 1.08)
            candidates.append((cx + vx * step, cy + vy * step, "grid"))
            if rng.random() < float(conf.get("gridpTurn", 9.0)) / 100.0:
                tx, ty = rotate(vx, vy, rng.choice([90.0, -90.0]))
                candidates.append((cx + tx * step, cy + ty * step, "organic"))
        elif rule == "organic":
            step = rng.uniform(grid_l * 0.9, organic_l)
            fx, fy = rotate(vx, vy, rng.uniform(-30.0, 30.0))
            candidates.append((cx + fx * step, cy + fy * step, "organic"))
            if rng.random() < float(conf.get("organicpTurn", 7.0)) / 100.0:
                tx, ty = rotate(vx, vy, rng.choice([rng.uniform(60, 120), rng.uniform(-120, -60)]))
                candidates.append((cx + tx * step, cy + ty * step, "grid"))
        else:
            ox, oy = normalize(cx, cy)
            step = rng.uniform(grid_l * 0.9, organic_l * 0.95)
            rx, ry = rotate(ox, oy, rng.uniform(-25.0, 25.0))
            candidates.append((cx + rx * step, cy + ry * step, "radial"))

        added_any = False
        for nx, ny, nrule in candidates:
            if abs(nx) > max_x or abs(ny) > max_y:
                continue
            if too_close(nx, ny):
                continue
            points.append((nx, ny))
            nid = len(points) - 1
            a, b = (curr_idx, nid) if curr_idx < nid else (nid, curr_idx)
            growth_edges.add((a, b))
            fronts.append((curr_idx, nid, nrule))
            added_any = True
            if len(points) >= target_nodes:
                break

        if not added_any and rng.random() < 0.55:
            fronts.pop(fi)

    margin = 180.0
    min_px = min(p[0] for p in points)
    min_py = min(p[1] for p in points)
    points = [(x - min_px + margin, y - min_py + margin) for x, y in points]

    network = RoadNetwork("planning_procedural_birth")
    nodes: list[Node] = []
    for idx, (x, y) in enumerate(points):
        node = Node(position=Vector2D(x, y), name=f"birth_node_{idx}")
        network.add_node(node)
        nodes.append(node)

    added_pairs: set[tuple[int, int]] = set()
    degree: dict[int, int] = {i: 0 for i in range(len(nodes))}

    def orientation(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    def on_segment(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
        return min(ax, bx) - 1e-6 <= cx <= max(ax, bx) + 1e-6 and min(ay, by) - 1e-6 <= cy <= max(ay, by) + 1e-6

    def segments_intersect(a1, a2, b1, b2) -> bool:
        o1 = orientation(a1[0], a1[1], a2[0], a2[1], b1[0], b1[1])
        o2 = orientation(a1[0], a1[1], a2[0], a2[1], b2[0], b2[1])
        o3 = orientation(b1[0], b1[1], b2[0], b2[1], a1[0], a1[1])
        o4 = orientation(b1[0], b1[1], b2[0], b2[1], a2[0], a2[1])

        if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
            return True
        if abs(o1) <= 1e-6 and on_segment(a1[0], a1[1], a2[0], a2[1], b1[0], b1[1]):
            return True
        if abs(o2) <= 1e-6 and on_segment(a1[0], a1[1], a2[0], a2[1], b2[0], b2[1]):
            return True
        if abs(o3) <= 1e-6 and on_segment(b1[0], b1[1], b2[0], b2[1], a1[0], a1[1]):
            return True
        if abs(o4) <= 1e-6 and on_segment(b1[0], b1[1], b2[0], b2[1], a2[0], a2[1]):
            return True
        return False

    def would_cross_existing(i: int, j: int) -> bool:
        p1 = (nodes[i].position.x, nodes[i].position.y)
        p2 = (nodes[j].position.x, nodes[j].position.y)
        for a, b in added_pairs:
            if len({i, j, a, b}) < 4:
                continue
            q1 = (nodes[a].position.x, nodes[a].position.y)
            q2 = (nodes[b].position.x, nodes[b].position.y)
            if segments_intersect(p1, p2, q1, q2):
                return True
        return False

    def add_undirected(i: int, j: int, strict_degree: bool = True, allow_cross: bool = False) -> bool:
        if i == j:
            return False
        a, b = (i, j) if i < j else (j, i)
        if (a, b) in added_pairs:
            return False
        dist = nodes[a].position.distance_to(nodes[b].position)
        if dist < min_edge or dist > max_edge:
            return False
        if strict_degree and (degree[a] >= 4 or degree[b] >= 4):
            return False
        if not allow_cross and would_cross_existing(a, b):
            return False

        network.create_edge(nodes[a], nodes[b], num_lanes=2, bidirectional=True)
        added_pairs.add((a, b))
        degree[a] += 1
        degree[b] += 1
        return True

    for a, b in sorted(growth_edges, key=lambda e: nodes[e[0]].position.distance_to(nodes[e[1]].position)):
        add_undirected(a, b, strict_degree=True, allow_cross=False)

    loop_budget = max(2, int(target_nodes * 0.35))
    added_loops = 0
    for i in range(len(nodes)):
        if added_loops >= loop_budget:
            break
        dists: list[tuple[float, int]] = []
        for j in range(len(nodes)):
            if i == j:
                continue
            d = nodes[i].position.distance_to(nodes[j].position)
            if min_edge <= d <= max_edge:
                dists.append((d, j))
        dists.sort(key=lambda x: x[0])
        for _, j in dists[:4]:
            if added_loops >= loop_budget:
                break
            if rng.random() < 0.35 and add_undirected(i, j, strict_degree=True, allow_cross=False):
                added_loops += 1

    def get_components() -> list[set[int]]:
        adj: dict[int, set[int]] = {i: set() for i in range(len(nodes))}
        for a, b in added_pairs:
            adj[a].add(b)
            adj[b].add(a)
        comps: list[set[int]] = []
        visited: set[int] = set()
        for i in range(len(nodes)):
            if i in visited:
                continue
            stack = [i]
            visited.add(i)
            comp: set[int] = set()
            while stack:
                cur = stack.pop()
                comp.add(cur)
                for nxt in adj[cur]:
                    if nxt not in visited:
                        visited.add(nxt)
                        stack.append(nxt)
            comps.append(comp)
        return comps

    def try_connect_node_to_targets(
        source: int,
        targets: list[int],
        max_dist_scale: float = 1.0,
    ) -> bool:
        candidate_pairs: list[tuple[float, int]] = []
        for target in targets:
            if target == source:
                continue
            dist = nodes[source].position.distance_to(nodes[target].position)
            if dist <= max_edge * max_dist_scale:
                candidate_pairs.append((dist, target))
        candidate_pairs.sort(key=lambda item: item[0])

        for _, target in candidate_pairs:
            if add_undirected(source, target, strict_degree=False, allow_cross=False):
                return True
        for _, target in candidate_pairs:
            if add_undirected(source, target, strict_degree=False, allow_cross=True):
                return True
        return False

    def enforce_isolated_node_connections() -> None:
        for idx in range(len(nodes)):
            if degree[idx] > 0:
                continue
            preferred_targets = sorted(
                (j for j in range(len(nodes)) if j != idx and degree[j] > 0),
                key=lambda j: nodes[idx].position.distance_to(nodes[j].position),
            )
            if try_connect_node_to_targets(idx, preferred_targets[:8], max_dist_scale=1.35):
                continue

            fallback_targets = sorted(
                (j for j in range(len(nodes)) if j != idx),
                key=lambda j: nodes[idx].position.distance_to(nodes[j].position),
            )
            try_connect_node_to_targets(idx, fallback_targets[:10], max_dist_scale=1.8)

    enforce_isolated_node_connections()

    guard = 0
    while guard < len(nodes) * 10:
        guard += 1
        comps = get_components()
        if len(comps) <= 1:
            break

        comps.sort(key=len)
        current = comps[0]
        remaining = set().union(*comps[1:])
        candidate_pairs: list[tuple[float, int, int]] = []
        for i in current:
            for j in remaining:
                d = nodes[i].position.distance_to(nodes[j].position)
                candidate_pairs.append((d, i, j))
        candidate_pairs.sort(key=lambda item: item[0])

        linked = False
        for dist, i, j in candidate_pairs:
            if dist > max_edge * 1.5:
                break
            if add_undirected(i, j, strict_degree=False, allow_cross=False):
                linked = True
                break
        if not linked:
            for dist, i, j in candidate_pairs[:12]:
                if dist > max_edge * 2.2:
                    break
                if add_undirected(i, j, strict_degree=False, allow_cross=True):
                    linked = True
                    break
        if not linked:
            break

    enforce_isolated_node_connections()

    return network


def _build_birth_network(configs: dict[str, Any]) -> RoadNetwork:
    """根据配置构建城市诞生路网，失败时回退到默认网格。"""
    def _network_is_connected(network: RoadNetwork) -> bool:
        if not network.nodes:
            return False
        node_ids = list(network.nodes.keys())
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
        for edge in network.edges.values():
            adjacency[edge.from_node.node_id].add(edge.to_node.node_id)
            adjacency[edge.to_node.node_id].add(edge.from_node.node_id)
        if any(not neighbors for neighbors in adjacency.values()):
            return False

        visited = {node_ids[0]}
        stack = [node_ids[0]]
        while stack:
            current = stack.pop()
            for nxt in adjacency[current]:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        return len(visited) == len(node_ids)

    if not bool(configs.get("city_birth", True)):
        return _build_default_planning_grid()
    
    # 获取网络类型
    network_type = configs.get("city_birth_network_type", "procedural")
    
    # 规整网络模式（十字、网格、放射）
    if network_type in ("cross", "grid", "radial"):
        try:
            if network_type == "cross":
                network = create_cross_network(env=None, center=Vector2D(0, 0), arm_length=400.0, add_ring=False)
                print(f"[城市诞生] 十字形初始路网: {len(network.nodes)} 节点, {len(network.edges)} 边")
            elif network_type == "grid":
                # 根据节点数计算网格大小
                target_nodes = configs.get("city_birth_nodes", 18)
                if target_nodes <= 9:
                    grid_size = 2  # 2x2 = 4节点
                elif target_nodes <= 16:
                    grid_size = 3  # 3x3 = 9节点
                elif target_nodes <= 25:
                    grid_size = 4  # 4x4 = 16节点
                else:
                    grid_size = 5  # 5x5 = 25节点
                spacing = configs.get("city_birth_scale", 120.0) * 2.5
                network = create_grid_network(env=None, center=Vector2D(0, 0), grid_size=grid_size, spacing=spacing)
                print(f"[城市诞生] 网格初始路网 ({grid_size}x{grid_size}): {len(network.nodes)} 节点, {len(network.edges)} 边")
            else:  # radial
                # 根据节点数计算放射臂数
                target_nodes = configs.get("city_birth_nodes", 18)
                if target_nodes <= 12:
                    num_arms = 4
                    num_rings = 1
                elif target_nodes <= 20:
                    num_arms = 6
                    num_rings = 1
                else:
                    num_arms = 6
                    num_rings = 2
                arm_length = configs.get("city_birth_scale", 120.0) * 4.0
                network = create_radial_network(env=None, center=Vector2D(0, 0), num_arms=num_arms, num_rings=num_rings, arm_length=arm_length)
                print(f"[城市诞生] 放射状初始路网 ({num_arms}臂{num_rings}环): {len(network.nodes)} 节点, {len(network.edges)} 边")
            
            # 规整网络模式直接返回，不需要检查连通性（它们天生就是连通的）
            return network
        except Exception as e:
            print(f"[城市诞生] {network_type} 初始路网生成失败，回退procedural: {e}")
            import traceback
            traceback.print_exc()
    
    # Procedural 模式（默认）
    try:
        network = _build_procedural_birth_network(configs)
        if len(network.nodes) >= 6 and len(network.edges) >= 10 and _network_is_connected(network):
            print(f"[城市诞生] procedural 初始路网生成成功: {len(network.nodes)} 节点, {len(network.edges)} 边")
            return network
        print("[城市诞生] procedural 路网拓扑异常，回退2x2初始网格")
    except Exception as e:
        print(f"[城市诞生] procedural 初始路网生成失败，回退2x2: {e}")
    return _build_default_planning_grid()

def _compute_network_bounds(network: RoadNetwork) -> tuple[float, float, float, float]:
    """计算路网边界。"""
    if not network.nodes:
        return (0.0, 0.0, 600.0, 600.0)
    xs = [n.position.x for n in network.nodes.values()]
    ys = [n.position.y for n in network.nodes.values()]
    return (min(xs), min(ys), max(xs), max(ys))

def _build_initial_zones_for_birth(network: RoadNetwork) -> list[tuple[Any, Vector2D, float, float, str]]:
    """根据路网边界生成初始功能区。"""
    from city.urban_planning.zone import ZoneType

    min_x, min_y, max_x, max_y = _compute_network_bounds(network)
    width = max(300.0, max_x - min_x)
    height = max(300.0, max_y - min_y)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    dx = width * 0.28
    dy = height * 0.28
    zone_w = max(70.0, min(140.0, width * 0.18))
    zone_h = max(60.0, min(120.0, height * 0.16))

    return [
        (ZoneType.RESIDENTIAL, Vector2D(center_x - dx, center_y - dy), zone_w + 20, zone_h + 10, "阳光小区"),
        (ZoneType.COMMERCIAL, Vector2D(center_x + dx, center_y - dy), zone_w, zone_h, "中心商业街"),
        (ZoneType.SCHOOL, Vector2D(center_x - dx, center_y + dy), zone_w + 10, zone_h, "希望小学"),
        (ZoneType.PARK, Vector2D(center_x + dx, center_y + dy), zone_w + 20, zone_h + 20, "市民公园"),
    ]

def create_planning_simulation(agent_configs: dict | None = None) -> SimulationEnvironment:
    """创建路网规划模式的仿真环境（支持城市诞生融合）。
    
    Args:
        agent_configs: 智能体LLM配置，格式为 {'vehicle': True, 'traffic_light': True, 'planning': True}
    """
    from city.agents.planning_agent import PlanningAgent
    from city.agents.zoning_agent import ZoningAgent
    
    # 默认配置
    configs = {
        'vehicle': True,
        'traffic_light': True,
        'planning': True,
        'city_birth': True,
        'city_birth_seed': 42,
        'city_birth_nodes': 18,
        'city_birth_seed_spokes': 6
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
    # 城市诞生融合：使用 procedural 风格初始路网覆盖默认网格
    network = _build_birth_network(configs)
    config = SimulationConfig()
    env = SimulationEnvironment(network, config)
    
    # 添加人口驱动的路网规划智能体（专注于路网扩展）
    # 兼容旧版配置 'planning'，新版使用 'road_planning'
    road_planning_use_llm = configs.get('road_planning', configs.get('planning', True)) and LLM_AVAILABLE
    road_planning_memory_enabled = bool(configs.get('road_planning', configs.get('planning', True)))
    planning_agent = PlanningAgent(
        environment=env,
        use_llm=road_planning_use_llm,
        enable_memory=road_planning_memory_enabled,
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
    zoning_memory_enabled = bool(configs.get('zoning', configs.get('planning', True)))
    zoning_agent = ZoningAgent(
        environment=env,
        use_llm=zoning_use_llm,
        enable_memory=zoning_memory_enabled,
        planning_interval=15.0,      # 每15秒尝试规划
        max_zones=30
    )
    zoning_agent.planning_interval = 15.0
    zoning_agent.max_zones = 40
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
    
    # 城市诞生融合：按初始路网边界动态放置初始功能区
    initial_zones = _build_initial_zones_for_birth(network)
    for zone_type, center, width, height, name in initial_zones:
        placed = False
        candidate_centers = [
            center,
            Vector2D(center.x + 40, center.y),
            Vector2D(center.x - 40, center.y),
            Vector2D(center.x, center.y + 40),
            Vector2D(center.x, center.y - 40),
            Vector2D(center.x + 60, center.y + 60),
            Vector2D(center.x - 60, center.y - 60),
        ]

        for candidate_center in candidate_centers:
            if not zoning_agent._is_zone_layout_valid(candidate_center, width, height, zone_type, name):
                continue

            zone = Zone(
                zone_type=zone_type,
                center=candidate_center,
                width=width,
                height=height,
                name=name
            )
            zone.planning_time = 0.0
            zone.planning_reason = "初始规划"
            zone.population = int(zone.max_population * 0.3)  # 初始30%人口
            zoning_agent.zone_manager.add_zone(zone)
            placed = True
            break

        if not placed:
            print(f"[城市规划] 跳过初始区域 {name}，原因：与道路或既有区域冲突")
    
    print(f"[城市规划] 创建 {len(initial_zones)} 个初始功能区域")
    
    print(f"[系统] 共添加 {len(env.agents)} 个智能体")
    
    # 调试：打印所有智能体及其记忆状态
    try:
        for agent_id, agent in env.agents.items():
            has_mem = hasattr(agent, 'has_memory') and agent.has_memory()
            print(f"[调试] 智能体 {agent_id}: type={type(agent).__name__}, has_memory={has_mem}")
    except Exception as e:
        print(f"[调试] 打印智能体信息失败: {e}")
    
    # 存储智能体LLM配置到环境，供生成车辆时使用
    env.agent_configs = configs
    
    # 为所有交叉口添加红绿灯
    traffic_light_use_llm = configs.get('traffic_light', True) and LLM_AVAILABLE
    traffic_light_memory_enabled = bool(configs.get('traffic_light', True))
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
                use_llm=traffic_light_use_llm,
                enable_memory=traffic_light_memory_enabled
            )
            tl_agent.activate()
            env.add_agent(tl_agent)
            print(f"[路网规划] 添加红绿灯智能体 {tl_agent.agent_id} (LLM={'启用' if traffic_light_use_llm else '禁用'})")
    
    print(f"[路网规划] 初始城市诞生完成: {len(network.nodes)} 节点, {len(network.edges)} 边")
    print(f"[系统] 最终智能体数量: {len(env.agents)} 个")
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
                    
                    # 获取智能体记忆数据
                    agent_memories_data = {}
                    agents_with_memory_list = []
                    if planning_simulation:
                        for agent in planning_simulation.agents.values():
                            if hasattr(agent, 'has_memory_data') and agent.has_memory_data():
                                try:
                                    memory = agent.get_memory()
                                    memory_data = memory.to_dict()
                                    agent_memories_data[agent.agent_id] = memory_data
                                    agents_with_memory_list.append({
                                        "id": agent.agent_id,
                                        "type": _get_memory_agent_kind(agent),
                                        "name": getattr(agent, 'name', agent.agent_id),
                                        "has_memory": True,
                                        "memory_count": memory_data.get("statistics", {}).get("total_memories", 0),
                                        "memory_summary": memory.generate_summary()
                                    })
                                except Exception as e:
                                    print(f"[记忆数据] 获取智能体 {agent.agent_id} 记忆失败: {e}")
                    
                    # 获取增强的统计数据
                    stats = get_enhanced_statistics(planning_simulation) if planning_simulation else {"active_vehicles": vehicles_count}
                    
                    data = {
                        "time": current_time,
                        "is_running": is_planning_running,
                        "agents": agents_data,
                        "traffic_lights": traffic_lights_data,
                        "network": network_data,
                        "zones": zones_data,
                        "planning_agent": planning_agent_status,
                        "zoning_agent": zoning_agent_status,
                        "llm_decisions": get_planning_llm_decisions(planning_simulation) if planning_simulation else [],
                        "expansion_history": planning_simulation.get_expansion_history() if planning_simulation else [],
                        "statistics": stats,
                        "agent_memories": agent_memories_data,
                        "agents_with_memory": agents_with_memory_list
                    }
                    if planning_simulation:
                        data["agent_memories"], data["agents_with_memory"] = _build_agent_memory_payload(planning_simulation)
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
            
            socketio.sleep(0.05)
            
        except Exception as e:
            print(f"[路网规划循环错误] {e}", flush=True)
            import traceback
            traceback.print_exc()
            socketio.sleep(0.1)
    
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
        agent_memories_data, agents_with_memory_list = _build_agent_memory_payload(planning_simulation)
        
        return jsonify({
            "time": planning_simulation.current_time,
            "is_running": is_planning_running,
            "agents": simple_agents,
            "traffic_lights": [],
            "network": get_network_data(planning_simulation),
            "expansion_history": planning_simulation.get_expansion_history(),
            "planning_agent": planning_agent_status,
            "zoning_agent": zoning_agent_status,
            "llm_decisions": get_planning_llm_decisions(planning_simulation),
            "zones": zones_data,
            "statistics": get_enhanced_statistics(planning_simulation),
            "agent_memories": agent_memories_data,
            "agents_with_memory": agents_with_memory_list
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
        'planning': True,
        'city_birth': True,
        'city_birth_seed': 42,
        'city_birth_nodes': 18,
        'city_birth_seed_spokes': 6
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

def create_zoning_simulation(agent_configs: dict | None = None) -> SimulationEnvironment:
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
    configs = {
        'vehicle': True,
        'traffic_light': True,
        'road_planning': True,
        'zoning': True,
    }
    if agent_configs:
        configs.update(agent_configs)
    env.agent_configs = configs
    
    # 添加路网规划Agent
    planning_agent = PlanningAgent(
        environment=env,
        use_llm=configs.get('road_planning', True) and LLM_AVAILABLE,
        enable_memory=bool(configs.get('road_planning', True)),
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
        use_llm=configs.get('zoning', True) and LLM_AVAILABLE,
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
                use_llm=configs.get('traffic_light', True) and LLM_AVAILABLE,
                enable_memory=bool(configs.get('traffic_light', True))
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

def get_planning_llm_decisions(env: SimulationEnvironment) -> list[dict[str, Any]]:
    """收集规划模式下各智能体的大模型决策归档。"""
    records: list[dict[str, Any]] = []
    for agent in env.agents.values():
        archive = getattr(agent, "llm_decision_archive", None)
        if isinstance(archive, list):
            records.extend(item for item in archive if isinstance(item, dict))

    records.sort(key=lambda item: float(item.get("timestamp", 0.0)), reverse=True)
    return records[:200]

def get_zoning_agent_status(env: SimulationEnvironment) -> dict | None:
    """获取城市规划智能体状态。"""
    from city.agents.zoning_agent import ZoningAgent
    
    for agent in env.agents.values():
        if isinstance(agent, ZoningAgent):
            return agent.get_status()
    return None

def get_enhanced_statistics(env: SimulationEnvironment) -> dict[str, Any]:
    """获取增强的统计数据，包含人口信息。"""
    stats = env.get_statistics()
    
    # 从ZoningAgent获取人口数据
    from city.agents.zoning_agent import ZoningAgent
    for agent in env.agents.values():
        if isinstance(agent, ZoningAgent):
            zone_stats = agent.zone_manager.get_statistics()
            total_pop = zone_stats.get('total_population', 0)
            total_zones = zone_stats.get('total_zones', 0)
            
            # 计算人口容量和压力
            total_capacity = sum(
                zone.max_population 
                for zone in agent.zone_manager.zones.values()
            )
            population_pressure = total_pop / total_capacity if total_capacity > 0 else 0
            
            stats['total_population'] = total_pop
            stats['total_zones'] = total_zones
            stats['total_capacity'] = total_capacity
            stats['population_pressure'] = round(population_pressure, 2)
            
            # 调试输出
            print(f"[统计] 区域数: {total_zones}, 总人口: {total_pop}/{total_capacity}, 压力: {population_pressure:.1%}")
            break
    
    return stats

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
            
            socketio.sleep(0.05)
            
        except Exception as e:
            print(f"[城市规划循环错误] {e}")
            import traceback
            traceback.print_exc()
            socketio.sleep(0.1)
    
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
            "statistics": get_enhanced_statistics(zoning_simulation)
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
                zoning_simulation = create_zoning_simulation(agent_configs)
                print("[Zoning Control] 创建新城市规划环境")
            
            if not is_zoning_running:
                is_zoning_running = True
                zoning_simulation.start()
                print("[Zoning Control] 城市规划仿真已启动")
                zoning_thread = threading.Thread(target=zoning_simulation_loop)
                zoning_thread.daemon = True
                zoning_thread.start()
                print("[Zoning Control] 城市规划线程已启动")
        return jsonify({"status": "started", "agent_configs": agent_configs})
    
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
            zoning_simulation = create_zoning_simulation(agent_configs)
        return jsonify({"status": "reset", "agent_configs": agent_configs})
    
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
