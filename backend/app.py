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
    """线程安全的 WebSocket 发送。"""
    try:
        with app.app_context():
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

if __name__ == "__main__":
    simulation = create_demo_simulation()
    print("仿真环境已初始化")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
