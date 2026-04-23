"""
SiliconFlow API 集成演示。

使用 Qwen/Qwen3-14B 等大模型进行交通决策。
"""

import sys
import os
sys.path.insert(0, '..')

from city.llm.llm_client import LLMClient, LLMConfig, LLMProvider
from city.llm.agent_llm_interface import set_global_llm_client, AgentLLMInterface
from city.agents.vehicle import Vehicle, VehicleType
from city.agents.traffic_manager import TrafficManager
from city.simulation.environment import SimulationEnvironment
from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.utils.vector import Vector2D


def create_test_environment():
    """创建测试环境。"""
    network = RoadNetwork("test")
    
    n1 = Node(Vector2D(0, 0), "start")
    n2 = Node(Vector2D(200, 0), "intersection", is_intersection=True)
    n3 = Node(Vector2D(400, 0), "end")
    
    for n in [n1, n2, n3]:
        network.add_node(n)
    
    network.create_edge(n1, n2, num_lanes=2)
    network.create_edge(n2, n3, num_lanes=2)
    if network.needs_traffic_light(n2):
        network.register_traffic_light(n2, TrafficLight(n2, cycle_time=60, green_duration=30))
    
    env = SimulationEnvironment(network)
    return env, [n1, n2, n3]


def demo_siliconflow_vehicle():
    """使用 SiliconFlow 进行车辆决策。"""
    print("=" * 70)
    print("SiliconFlow API - 车辆智能决策演示")
    print("=" * 70)
    
    # 检查环境变量
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-14B")
    
    if not api_key:
        print("\n错误: 未设置 SILICONFLOW_API_KEY 环境变量")
        print("请先设置环境变量:")
        print('  $env:SILICONFLOW_API_KEY="your-api-key"')
        print('  $env:SILICONFLOW_BASE_URL="https://api.siliconflow.cn/v1"')
        print('  $env:SILICONFLOW_MODEL="Qwen/Qwen3-14B"')
        return
    
    print(f"\n配置信息:")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  API Key: {api_key[:10]}...{api_key[-4:]}")
    
    # 创建 LLM 客户端 (SiliconFlow)
    config = LLMConfig(
        provider=LLMProvider.SILICONFLOW,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.7,
        max_tokens=500
    )
    
    llm_client = LLMClient(config)
    
    if not llm_client.is_available():
        print("\n错误: LLM 客户端初始化失败")
        return
    
    set_global_llm_client(llm_client)
    print("\n✓ LLM 客户端初始化成功")
    
    # 创建测试环境
    env, nodes = create_test_environment()
    
    # 创建使用 LLM 的车辆
    vehicle = Vehicle(
        vehicle_type=VehicleType.CAR,
        environment=env,
        use_llm=True
    )
    
    print(f"\n车辆信息:")
    print(f"  ID: {vehicle.agent_id}")
    print(f"  类型: {vehicle.vehicle_type.name}")
    print(f"  最大速度: {vehicle.max_speed:.2f} m/s")
    
    # 测试场景
    scenarios = [
        {
            "name": "场景1: 畅通道路",
            "perception": {
                "current_speed": 8.0,
                "max_speed": 13.89,
                "front_vehicle": None,
                "traffic_light": "GREEN",
                "road_condition": "clear"
            }
        },
        {
            "name": "场景2: 前方有车",
            "perception": {
                "current_speed": 10.0,
                "max_speed": 13.89,
                "front_vehicle": {
                    "distance": 25.0,
                    "speed": 5.0
                },
                "traffic_light": "GREEN",
                "road_condition": "busy"
            }
        },
        {
            "name": "场景3: 红灯停车",
            "perception": {
                "current_speed": 12.0,
                "max_speed": 13.89,
                "front_vehicle": None,
                "traffic_light": "RED",
                "distance_to_intersection": 40.0,
                "road_condition": "clear"
            }
        },
        {
            "name": "场景4: 复杂决策",
            "perception": {
                "current_speed": 6.0,
                "max_speed": 13.89,
                "front_vehicle": {
                    "distance": 15.0,
                    "speed": 3.0
                },
                "traffic_light": "YELLOW",
                "distance_to_intersection": 35.0,
                "road_condition": "congested"
            }
        }
    ]
    
    print("\n" + "-" * 70)
    print("开始决策测试...")
    print("-" * 70)
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"感知: {scenario['perception']}")
        
        try:
            # 获取 LLM 决策
            llm_interface = AgentLLMInterface(vehicle, llm_client, use_llm=True)
            decision = llm_interface.get_llm_decision(scenario['perception'])
            
            print(f"LLM决策:")
            if isinstance(decision, dict):
                for key, value in decision.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  {decision}")
                
        except Exception as e:
            print(f"决策失败: {e}")
    
    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)


def demo_siliconflow_chat():
    """简单的对话测试。"""
    print("=" * 70)
    print("SiliconFlow API - 对话测试")
    print("=" * 70)
    
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-14B")
    
    if not api_key:
        print("\n错误: 未设置 SILICONFLOW_API_KEY")
        return
    
    config = LLMConfig(
        provider=LLMProvider.SILICONFLOW,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.7,
        max_tokens=200
    )
    
    client = LLMClient(config)
    
    print(f"\n测试模型: {model}")
    print("发送测试消息: '你好，请简单介绍一下自己'")
    
    try:
        response = client.chat(
            "你好，请简单介绍一下自己",
            system_prompt="你是一个智能交通助手，请用中文回复。"
        )
        print(f"\n回复:\n{response}")
    except Exception as e:
        print(f"请求失败: {e}")


def demo_siliconflow_manager():
    """使用 SiliconFlow 进行交通管理决策。"""
    print("=" * 70)
    print("SiliconFlow API - 交通管理者决策演示")
    print("=" * 70)
    
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-14B")
    
    if not api_key:
        print("\n错误: 未设置 SILICONFLOW_API_KEY")
        return
    
    config = LLMConfig(
        provider=LLMProvider.SILICONFLOW,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.5,
        max_tokens=500
    )
    
    llm_client = LLMClient(config)
    set_global_llm_client(llm_client)
    
    # 创建环境和管理者
    env, nodes = create_test_environment()
    manager = TrafficManager(environment=env, use_llm=True)
    if nodes[1].traffic_light:
        manager.add_control_node(nodes[1])
    
    print(f"\n交通管理者信息:")
    print(f"  ID: {manager.agent_id}")
    print(f"  控制节点: {len(manager.control_area)}")
    
    # 模拟拥堵场景
    print("\n模拟场景: 早高峰拥堵")
    perception = {
        "time": "08:30",
        "node_metrics": {
            "intersection": {
                "avg_speed": 3.5,
                "density": 0.85,
                "congestion_level": 0.75
            }
        },
        "active_incidents": [],
        "system_status": "congested"
    }
    
    print(f"感知信息: {perception}")
    
    try:
        llm_interface = AgentLLMInterface(manager, llm_client, use_llm=True)
        decision = llm_interface.get_llm_decision(perception)
        
        print(f"\nLLM管理决策:")
        if isinstance(decision, dict):
            for key, value in decision.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {decision}")
    except Exception as e:
        print(f"决策失败: {e}")


def main():
    """主函数。"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SiliconFlow API 演示')
    parser.add_argument(
        '--mode',
        choices=['chat', 'vehicle', 'manager', 'all'],
        default='all',
        help='演示模式'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'chat' or args.mode == 'all':
        demo_siliconflow_chat()
        print("\n")
    
    if args.mode == 'vehicle' or args.mode == 'all':
        demo_siliconflow_vehicle()
        print("\n")
    
    if args.mode == 'manager' or args.mode == 'all':
        demo_siliconflow_manager()


if __name__ == "__main__":
    main()
