"""
车辆感知与决策优化测试脚本。

测试优化后的车辆代理功能：
1. 增强感知能力（多方向车辆检测）
2. 智能决策（LLM + 规则fallback）
3. 死锁检测与恢复
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.agents.vehicle import Vehicle, VehicleType, VehicleState
from city.utils.vector import Vector2D
from city.llm.llm_client import MockLLMClient
from city.llm.agent_llm_interface import set_global_llm_client


def create_test_network():
    """创建测试网络。"""
    network = RoadNetwork("test")
    
    # 创建3个节点形成一条路
    n1 = Node(position=Vector2D(0, 0), name="start")
    n2 = Node(position=Vector2D(100, 0), name="middle")
    n3 = Node(position=Vector2D(200, 0), name="end")
    
    network.add_node(n1)
    network.add_node(n2)
    network.add_node(n3)
    
    # 创建路段（2车道）
    network.create_edge(n1, n2, num_lanes=2)
    network.create_edge(n2, n3, num_lanes=2)
    
    # 在中间节点添加信号灯
    n2.is_intersection = True
    n2.traffic_light = TrafficLight(n2, cycle_time=30, green_duration=12, yellow_duration=3)
    
    return network, [n1, n2, n3]


def test_enhanced_perception():
    """测试增强感知功能。"""
    print("\n" + "="*50)
    print("测试 1: 增强感知功能")
    print("="*50)
    
    network, nodes = create_test_network()
    config = SimulationConfig(time_step=0.1)
    env = SimulationEnvironment(network, config)
    
    # 创建两辆车
    v1 = env.spawn_vehicle(nodes[0], nodes[2], VehicleType.CAR)
    v2 = env.spawn_vehicle(nodes[0], nodes[2], VehicleType.CAR)
    
    if v1 and v2:
        # 设置第二辆车在第一辆车后面
        v2.distance_on_edge = 0
        v1.distance_on_edge = 30  # 前方30米
        
        # 获取感知数据
        perception = v2.perceive()
        
        print(f"车辆 {v2.agent_id} 感知结果:")
        print(f"  - 自身速度: {perception['self']['velocity']:.2f} m/s")
        print(f"  - 前方车辆: {'有' if perception['front_vehicle'] else '无'}")
        
        if perception['front_vehicle']:
            fv = perception['front_vehicle']
            print(f"    - 前车ID: {fv['id']}")
            print(f"    - 距离: {fv['distance']:.2f} 米")
            print(f"    - 前车速度: {fv['velocity']:.2f} m/s")
            print(f"    - 碰撞时间(TTC): {fv['time_to_collision']:.2f} 秒")
        
        print(f"  - 交通信号灯: {perception['traffic_light']}")
        print(f"  - 路口排队: {perception['intersection_queue']}")
        print(f"  - 周边环境车辆数: {len(perception['surroundings'])}")
        
        print("\n✓ 感知功能测试通过")
    else:
        print("✗ 车辆生成失败")


def test_rule_based_decision():
    """测试规则决策。"""
    print("\n" + "="*50)
    print("测试 2: 规则决策逻辑")
    print("="*50)
    
    network, nodes = create_test_network()
    config = SimulationConfig(time_step=0.1)
    env = SimulationEnvironment(network, config)
    
    # 创建车辆
    v1 = env.spawn_vehicle(nodes[0], nodes[2], VehicleType.CAR)
    
    if v1:
        # 测试不同场景
        scenarios = [
            ("正常行驶", lambda: None),
            ("前方有车辆（近距离）", lambda: setattr(v1, 'front_vehicle_distance', 10)),
            ("前方有车辆（远距离）", lambda: setattr(v1, 'front_vehicle_distance', 50)),
        ]
        
        for name, setup in scenarios:
            setup()
            action = v1.decide()
            print(f"  {name}: {action.name}")
        
        print("\n✓ 规则决策测试通过")


def test_deadlock_detection():
    """测试死锁检测与恢复。"""
    print("\n" + "="*50)
    print("测试 3: 死锁检测与恢复")
    print("="*50)
    
    network, nodes = create_test_network()
    config = SimulationConfig(time_step=0.1)
    env = SimulationEnvironment(network, config)
    
    # 创建车辆
    v1 = env.spawn_vehicle(nodes[0], nodes[2], VehicleType.CAR)
    
    if v1:
        # 模拟死锁状态
        v1.velocity = 0
        v1.vehicle_state = VehicleState.STOPPED
        
        # 填充位置历史（模拟长时间未移动）
        for _ in range(v1.history_max_size):
            v1.position_history.append((v1.position.x, v1.position.y))
        
        v1.stop_timer = 6.0  # 停止超过5秒
        
        # 检测死锁
        is_deadlock = v1._check_deadlock()
        print(f"  死锁检测结果: {is_deadlock}")
        
        if is_deadlock:
            # 测试恢复
            recovery_action = v1._deadlock_recovery()
            print(f"  恢复策略: {recovery_action.name}")
        
        print("\n✓ 死锁检测测试通过")


def test_llm_interface():
    """测试LLM接口。"""
    print("\n" + "="*50)
    print("测试 4: LLM决策接口")
    print("="*50)
    
    # 使用Mock LLM
    mock_llm = MockLLMClient({
        "拥堵": '{"action": "decelerate", "reason": "前方拥堵", "confidence": 0.9}',
        "红灯": '{"action": "stop", "reason": "红灯停车", "confidence": 0.95}',
        "畅通": '{"action": "accelerate", "reason": "道路畅通", "confidence": 0.8}',
    })
    set_global_llm_client(mock_llm)
    
    network, nodes = create_test_network()
    config = SimulationConfig(time_step=0.1)
    env = SimulationEnvironment(network, config)
    
    # 创建启用LLM的车辆
    v1 = env.spawn_vehicle(nodes[0], nodes[2], VehicleType.CAR)
    
    if v1:
        v1.use_llm = True
        
        # 获取感知和决策
        perception = v1.perceive()
        print(f"  感知数据包含字段: {list(perception.keys())}")
        
        # 测试决策
        action = v1.decide()
        print(f"  LLM决策结果: {action.name}")
        
        # 检查LLM接口的决策历史
        if v1.llm_interface:
            print(f"  决策历史条数: {len(v1.llm_interface.decision_history)}")
        
        print("\n✓ LLM接口测试通过")


def test_enhanced_statistics():
    """测试增强的统计信息。"""
    print("\n" + "="*50)
    print("测试 5: 增强统计信息")
    print("="*50)
    
    network, nodes = create_test_network()
    config = SimulationConfig(time_step=0.1)
    env = SimulationEnvironment(network, config)
    
    # 生成几辆车
    for i in range(3):
        env.spawn_vehicle(nodes[0], nodes[2], VehicleType.CAR)
    
    # 运行几步
    for _ in range(10):
        env.step()
    
    # 获取统计
    stats = env.get_statistics()
    print("  统计信息:")
    for key, value in stats.items():
        print(f"    - {key}: {value}")
    
    print("\n✓ 统计信息测试通过")


if __name__ == "__main__":
    print("\n" + "="*50)
    print("CITY 车辆感知与决策优化测试")
    print("="*50)
    
    try:
        test_enhanced_perception()
        test_rule_based_decision()
        test_deadlock_detection()
        test_llm_interface()
        test_enhanced_statistics()
        
        print("\n" + "="*50)
        print("所有测试通过！")
        print("="*50)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
