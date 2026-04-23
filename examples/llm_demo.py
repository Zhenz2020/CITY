"""
LLM集成演示。

演示如何使用大语言模型增强智能体决策。
"""

import sys
sys.path.insert(0, '..')

from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.agents.vehicle import Vehicle, VehicleType
from city.agents.traffic_manager import TrafficManager
from city.llm.llm_client import LLMClient, LLMConfig, LLMProvider, MockLLMClient
from city.llm.agent_llm_interface import set_global_llm_client
from city.utils.vector import Vector2D


def create_simple_network():
    """创建简单网络。"""
    network = RoadNetwork("llm_demo")

    n1 = Node(Vector2D(0, 0), "start")
    n2 = Node(Vector2D(200, 0), "middle", is_intersection=True)
    n3 = Node(Vector2D(400, 0), "end")

    for n in [n1, n2, n3]:
        network.add_node(n)

    network.create_edge(n1, n2, num_lanes=2)
    network.create_edge(n2, n3, num_lanes=2)

    if network.needs_traffic_light(n2):
        network.register_traffic_light(n2, TrafficLight(n2, cycle_time=60, green_duration=30))

    return network, [n1, n2, n3]


def demo_mock_llm():
    """使用Mock LLM演示（无需API密钥）。"""
    print("=" * 60)
    print("LLM智能决策演示 (Mock模式)")
    print("=" * 60)

    # 创建Mock LLM客户端
    mock_responses = {
        "加速": '{"action": "accelerate", "reason": "前方道路畅通"}',
        "红灯": '{"action": "stop", "reason": "前方红灯"}',
        "default": '{"action": "maintain", "reason": "保持当前状态"}'
    }

    mock_client = MockLLMClient(mock_responses)
    set_global_llm_client(mock_client)

    print("\n已设置Mock LLM客户端")

    # 创建环境
    network, nodes = create_simple_network()
    env = SimulationEnvironment(network)

    # 创建使用LLM的车辆
    vehicle = Vehicle(
        vehicle_type=VehicleType.CAR,
        environment=env,
        use_llm=True  # 启用LLM决策
    )

    # 测试LLM决策
    perception = {
        "speed": 10.0,
        "front_vehicle_distance": 100.0,
        "traffic_light": "GREEN"
    }

    print(f"\n车辆: {vehicle.agent_id}")
    print(f"感知信息: {perception}")

    llm_decision = vehicle.llm_decide(perception)
    print(f"\nLLM决策: {llm_decision}")

    print("\n演示完成!")


def demo_real_llm():
    """
    使用真实LLM演示。
    需要设置API密钥环境变量。
    """
    print("=" * 60)
    print("LLM智能决策演示 (真实API)")
    print("=" * 60)

    # 创建LLM客户端（从环境变量读取API密钥）
    llm_client = LLMClient()

    if not llm_client.is_available():
        print("\nLLM服务不可用。请设置以下环境变量之一:")
        print("  - OPENAI_API_KEY (OpenAI)")
        print("  - AZURE_OPENAI_API_KEY (Azure)")
        print("\n跳过真实LLM演示，使用Mock模式...")
        demo_mock_llm()
        return

    set_global_llm_client(llm_client)
    print(f"\nLLM客户端已初始化")
    print(f"  - Provider: {llm_client.config.provider.name}")
    print(f"  - Model: {llm_client.config.model}")

    # 创建环境
    network, nodes = create_simple_network()
    env = SimulationEnvironment(network)

    # 创建使用LLM的车辆
    vehicle = Vehicle(
        vehicle_type=VehicleType.CAR,
        environment=env,
        use_llm=True
    )

    # 测试几种场景
    test_scenarios = [
        {
            "name": "畅通路段",
            "perception": {
                "speed": 8.0,
                "max_speed": 13.89,
                "front_vehicle": None,
                "traffic_light": "GREEN"
            }
        },
        {
            "name": "前方拥堵",
            "perception": {
                "speed": 5.0,
                "max_speed": 13.89,
                "front_vehicle": {"distance": 20.0, "speed": 3.0},
                "traffic_light": "GREEN"
            }
        },
        {
            "name": "红灯停车",
            "perception": {
                "speed": 10.0,
                "max_speed": 13.89,
                "front_vehicle": None,
                "traffic_light": "RED",
                "distance_to_intersection": 30.0
            }
        }
    ]

    print(f"\n车辆: {vehicle.agent_id}")

    for scenario in test_scenarios:
        print(f"\n场景: {scenario['name']}")
        print(f"感知: {scenario['perception']}")

        try:
            decision = vehicle.llm_decide(scenario['perception'])
            print(f"LLM决策: {decision}")
        except Exception as e:
            print(f"决策失败: {e}")

    print("\n演示完成!")


def demo_llm_traffic_manager():
    """演示LLM增强的交通管理者。"""
    print("=" * 60)
    print("LLM交通管理演示")
    print("=" * 60)

    # 使用Mock LLM
    mock_responses = {
        "拥堵": '{"action": "adjust_signal", "target": "center", "parameters": {"green_extension": 10}, "reason": "缓解拥堵"}'
    }
    set_global_llm_client(MockLLMClient(mock_responses))

    # 创建环境
    network, nodes = create_simple_network()
    env = SimulationEnvironment(network)

    # 创建使用LLM的交通管理者
    manager = TrafficManager(environment=env, use_llm=True)
    if nodes[1].traffic_light:
        manager.add_control_node(nodes[1])
    env.add_agent(manager)

    # 模拟拥堵场景
    perception = manager.perceive()
    print(f"\n交通管理状态: {len(manager.control_area)} 个控制节点")
    print(f"感知信息: {perception}")

    # 获取LLM决策
    llm_decision = manager.llm_decide(perception)
    print(f"\nLLM管理决策: {llm_decision}")

    print("\n演示完成!")


def main():
    """主函数。"""
    import argparse

    parser = argparse.ArgumentParser(description='LLM集成演示')
    parser.add_argument(
        '--mode',
        choices=['mock', 'real', 'manager'],
        default='mock',
        help='演示模式'
    )

    args = parser.parse_args()

    if args.mode == 'mock':
        demo_mock_llm()
    elif args.mode == 'real':
        demo_real_llm()
    elif args.mode == 'manager':
        demo_llm_traffic_manager()


if __name__ == "__main__":
    main()
