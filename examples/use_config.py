"""
使用配置文件运行 LLM 演示。

不需要设置环境变量，直接在 config/siliconflow_config.json 中配置 API Key。
"""

import sys
import os
sys.path.insert(0, '..')

from city.llm.llm_client import (
    load_llm_from_config, 
    load_siliconflow_config,
    LLMClient
)
from city.llm.agent_llm_interface import set_global_llm_client, AgentLLMInterface
from city.agents.vehicle import Vehicle, VehicleType
from city.agents.traffic_manager import TrafficManager
from city.simulation.environment import SimulationEnvironment
from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.utils.vector import Vector2D


def create_test_env():
    """创建测试环境。"""
    network = RoadNetwork("test")
    n1 = Node(Vector2D(0, 0), "start")
    n2 = Node(Vector2D(200, 0), "mid", is_intersection=True)
    n3 = Node(Vector2D(400, 0), "end")
    for n in [n1, n2, n3]:
        network.add_node(n)
    network.create_edge(n1, n2, num_lanes=2)
    network.create_edge(n2, n3, num_lanes=2)
    n2.traffic_light = TrafficLight(n2)
    return SimulationEnvironment(network)


def main():
    """主函数。"""
    print("=" * 70)
    print("使用配置文件运行 LLM 演示")
    print("=" * 70)
    
    # 方式1: 自动查找配置文件
    try:
        print("\n[方式1] 自动查找 SiliconFlow 配置...")
        llm_client = load_siliconflow_config()
        print("✓ 配置文件加载成功!")
    except FileNotFoundError as e:
        print(f"✗ {e}")
        print("\n[方式2] 使用指定配置文件路径...")
        
        # 方式2: 指定配置文件路径
        config_path = input("请输入配置文件路径 (默认: ../config/siliconflow_config.json): ").strip()
        if not config_path:
            config_path = "../config/siliconflow_config.json"
        
        if not os.path.exists(config_path):
            print(f"✗ 文件不存在: {config_path}")
            print("\n请确保配置文件存在，或手动创建:")
            print('''
{
  "provider": "SILICONFLOW",
  "api_key": "sk-your-real-api-key",
  "base_url": "https://api.siliconflow.cn/v1",
  "model": "Qwen/Qwen3-14B"
}
            ''')
            return
        
        llm_client = load_llm_from_config(config_path)
        print("✓ 配置文件加载成功!")
    
    # 显示配置信息
    print(f"\n配置信息:")
    print(f"  Provider: {llm_client.config.provider.name}")
    print(f"  Model: {llm_client.config.model}")
    print(f"  Base URL: {llm_client.config.base_url}")
    print(f"  API Key: {llm_client.config.api_key[:15]}..." if llm_client.config.api_key else "  API Key: None")
    
    # 检查可用性
    if not llm_client.is_available():
        print("\n✗ LLM 客户端不可用!")
        print("  可能原因:")
        print("  1. API Key 未配置或无效")
        print("  2. openai 包未安装 (pip install openai)")
        return
    
    print("\n✓ LLM 客户端可用!")
    
    # 设置全局客户端
    set_global_llm_client(llm_client)
    
    # 测试对话
    print("\n" + "-" * 70)
    print("测试对话...")
    print("-" * 70)
    
    try:
        response = llm_client.chat(
            "你好！请用一句话介绍自己",
            system_prompt="你是一个智能交通助手"
        )
        print(f"\nLLM 回复: {response}")
    except Exception as e:
        print(f"\n✗ 对话失败: {e}")
        return
    
    # 测试车辆决策
    print("\n" + "-" * 70)
    print("测试车辆智能决策...")
    print("-" * 70)
    
    env = create_test_env()
    vehicle = Vehicle(
        vehicle_type=VehicleType.CAR,
        environment=env,
        use_llm=True
    )
    
    perception = {
        "current_speed": 8.0,
        "max_speed": 13.89,
        "front_vehicle": None,
        "traffic_light": "GREEN",
        "road_condition": "clear"
    }
    
    print(f"\n感知信息: {perception}")
    
    try:
        llm_interface = AgentLLMInterface(vehicle, llm_client, use_llm=True)
        decision = llm_interface.get_llm_decision(perception)
        print(f"\nLLM 决策:")
        for key, value in decision.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"\n✗ 决策失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
