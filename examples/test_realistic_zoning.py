"""
测试现实城市规划系统
"""
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.utils.vector import Vector2D


def create_test_network():
    """创建测试网络。"""
    network = RoadNetwork("test_city")
    
    # 创建3x3网格
    nodes = {}
    for i in range(3):
        for j in range(3):
            pos = Vector2D(j * 400, i * 400)
            node = Node(position=pos, name=f"node_{i}_{j}")
            network.add_node(node)
            nodes[(i, j)] = node
    
    # 连接节点
    for i in range(3):
        for j in range(3):
            current = nodes[(i, j)]
            if j + 1 < 3:
                right = nodes[(i, j + 1)]
                network.create_edge(current, right, num_lanes=2, bidirectional=True)
            if i + 1 < 3:
                down = nodes[(i + 1, j)]
                network.create_edge(current, down, num_lanes=2, bidirectional=True)
    
    return network


def test_realistic_zoning():
    """测试现实城市规划。"""
    print("=" * 60)
    print("现实城市规划系统测试")
    print("=" * 60)
    
    # 创建仿真环境
    network = create_test_network()
    env = SimulationEnvironment(network)
    
    # 创建规划智能体
    planner = PopulationCityPlanner(
        environment=env,
        use_llm=False,  # 测试时禁用LLM
        enable_zoning=True,
        zoning_interval=5.0,
        max_zones=20
    )
    env.add_agent(planner)
    
    print("\n[初始化] 创建3x3测试网络")
    print(f"[初始化] 节点数: {len(network.nodes)}")
    
    # 模拟几个规划周期
    print("\n[测试] 执行规划...")
    
    success_count = 0
    for i in range(5):
        decision = planner._plan_zoning()
        if decision:
            success = planner._execute_zoning(decision)
            if success:
                success_count += 1
                zone_type_name = decision['zone_type'].display_name if hasattr(decision['zone_type'], 'display_name') else decision['zone_type']
                print(f"\n  [成功] {decision['name']} ({zone_type_name})")
                print(f"         评分: {decision.get('score', 0):.2f}")
                print(f"         原因: {decision['reason']}")
    
    # 输出统计
    print("\n" + "=" * 60)
    print("规划统计")
    print("=" * 60)
    
    stats = planner.zone_manager.get_statistics()
    print(f"总区域数: {stats['total_zones']}")
    print(f"总人口: {stats['total_population']}")
    print(f"总面积: {stats['total_area']:.0f}m2")
    
    if stats['by_type']:
        print("\n各类型区域:")
        for zone_type, type_stats in stats['by_type'].items():
            print(f"  {zone_type}: {type_stats['count']}个, "
                  f"人口{type_stats['total_population']}, "
                  f"面积{type_stats['total_area']:.0f}m2")
    
    # 显示规划历史
    print("\n规划历史:")
    for i, history in enumerate(planner.zoning_history[-5:], 1):
        print(f"  {i}. {history['name']} - {history['zone_type']}")
        if history.get('score'):
            print(f"     评分: {history['score']:.2f}")
        if history.get('evaluation_summary', {}).get('advantages'):
            adv = history['evaluation_summary']['advantages'][0]
            print(f"     优点: {adv}")
    
    print("\n[测试完成]")


if __name__ == "__main__":
    test_realistic_zoning()
