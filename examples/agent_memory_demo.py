"""
智能体记忆模块演示。

展示如何为智能体添加、查询和使用记忆。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from city.agents.base import BaseAgent, AgentType
from city.agents.memory import AgentMemory, MemoryEntry
from city.simulation.environment import SimulationEnvironment
from city.environment.road_network import RoadNetwork


def demo_basic_memory():
    """演示基本记忆功能。"""
    print("=" * 60)
    print("智能体记忆模块演示")
    print("=" * 60)
    
    # 创建仿真环境
    network = RoadNetwork("demo")
    env = SimulationEnvironment(network)
    
    # 创建一个测试智能体
    class TestAgent(BaseAgent):
        def __init__(self):
            super().__init__(
                AgentType.TRAFFIC_MANAGER,
                environment=env,
                use_llm=False,
                enable_memory=True,  # 启用记忆
                memory_capacity=20   # 短期记忆容量
            )
        
        def perceive(self):
            return {"status": "active", "time": env.current_time}
        
        def decide(self):
            return "continue"
        
        def act(self, action):
            pass
        
        def update(self, dt):
            pass
    
    agent = TestAgent()
    agent.activate()
    
    print(f"\n1. 创建智能体: {agent.agent_id}")
    print(f"   记忆启用: {agent.has_memory()}")
    
    # 模拟一些感知和决策
    print("\n2. 模拟感知和决策...")
    for i in range(5):
        env.current_time = i * 10.0
        
        # 感知
        perception = {
            "location": f"intersection_{i}",
            "traffic_level": "high" if i % 2 == 0 else "low",
            "weather": "sunny"
        }
        agent.record_perception(perception, importance=3.0)
        
        # 决策
        decision = {
            "action": "extend_green" if i % 2 == 0 else "maintain",
            "duration": 30
        }
        agent.record_decision(decision, {"reason": "peak hour"}, importance=5.0)
        
        # 随机事件
        if i == 3:
            agent.record_event("检测到拥堵", {"location": "main_st", "severity": "high"}, importance=8.0)
    
    print("   添加了 5 次感知、5 次决策、1 次事件")
    
    # 查询记忆
    memory = agent.get_memory()
    print(f"\n3. 记忆统计:")
    print(f"   短期记忆: {len(memory.short_term)} 条")
    print(f"   长期记忆: {len(memory.long_term)} 条")
    
    # 获取最近记忆
    print("\n4. 最近3条记忆:")
    for entry in memory.get_recent(count=3):
        print(f"   [{entry.memory_type}] {entry.content}")
    
    # 获取重要记忆
    print("\n5. 重要记忆 (importance >= 7):")
    for entry in memory.get_important(min_importance=7.0):
        print(f"   [{entry.memory_type}] {entry.content}")
    
    # 按类型查询
    print("\n6. 感知记忆:")
    for entry in memory.get_by_type("perception"):
        loc = entry.content.get("location", "unknown")
        print(f"   [{entry.timestamp:.0f}s] 位置: {loc}")
    
    # 生成摘要
    print(f"\n7. 记忆摘要:")
    summary = memory.generate_summary()
    print(f"   {summary}")
    
    # LLM 上下文格式
    print(f"\n8. LLM上下文格式:")
    context = memory.get_context_for_llm(max_entries=5)
    print(context)
    
    # 保存到文件
    print(f"\n9. 保存记忆到文件...")
    memory.save_to_file("demo_memory.json")
    print("   已保存到 demo_memory.json")
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


def demo_memory_types():
    """演示不同类型的记忆。"""
    print("\n" + "=" * 60)
    print("记忆类型演示")
    print("=" * 60)
    
    network = RoadNetwork("demo2")
    env = SimulationEnvironment(network)
    
    class VehicleAgent(BaseAgent):
        def __init__(self):
            super().__init__(
                AgentType.VEHICLE,
                environment=env,
                enable_memory=True
            )
        
        def perceive(self):
            return {}
        
        def decide(self):
            return "drive"
        
        def act(self, action):
            pass
        
        def update(self, dt):
            pass
    
    agent = VehicleAgent()
    agent.activate()
    env.current_time = 0.0
    
    # 添加各种类型的记忆
    print("\n添加不同类型的记忆...")
    
    # 1. 感知记忆
    agent.record_perception({
        "front_vehicle_distance": 15.5,
        "traffic_light": "green",
        "speed": 45
    }, importance=3.0)
    
    # 2. 决策记忆
    agent.record_decision({
        "action": "accelerate",
        "target_speed": 50
    }, {"reason": "clear road ahead"}, importance=4.0)
    
    # 3. 行动记忆
    agent.record_action("change_lane", {"from": "left", "to": "right"}, importance=4.0)
    
    # 4. 事件记忆
    agent.record_event("接近路口", {"distance": 30, "light": "yellow"}, importance=6.0)
    
    # 5. 交互记忆
    agent.get_memory().add_interaction("traffic_light_01", "signal_request", {
        "request": "green_light",
        "wait_time": 5.0
    }, importance=5.0)
    
    memory = agent.get_memory()
    print(f"\n记忆总数: {len(memory)}")
    
    # 按类型统计
    type_counts = {}
    for entry in memory.short_term:
        type_counts[entry.memory_type] = type_counts.get(entry.memory_type, 0) + 1
    
    print("\n记忆类型分布:")
    for mtype, count in type_counts.items():
        print(f"   {mtype}: {count}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_basic_memory()
    demo_memory_types()
