"""
测试生长式城市扩展。

验证多分支、自然生长的路网扩展效果。
"""

import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.environment.dynamic_network import create_procedural_initial_network
from city.environment.growth_expansion import (
    ProceduralGrowthExpansion, 
    GrowthConfig,
    expand_city_procedurally
)
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.utils.vector import Vector2D


class MockEnv:
    """Mock 环境用于测试。"""
    def __init__(self):
        self.agents = []
        self.road_network = RoadNetwork("test")
        self.current_time = 0
        self.is_running = False
        
    def add_agent(self, agent):
        self.agents.append(agent)
    
    def add_node_dynamically(self, position, name=None):
        node = Node(position, name=name or f"node_{len(self.road_network.nodes)}")
        self.road_network.add_node(node)
        return node
    
    def add_edge_dynamically(self, from_node, to_node, num_lanes=2, bidirectional=True):
        return self.road_network.create_edge(
            from_node, to_node, num_lanes=num_lanes, bidirectional=bidirectional
        )
    
    def can_connect_nodes(self, n1, n2, max_distance=1000):
        return n1.position.distance_to(n2.position) <= max_distance


def test_growth_expansion_basic():
    """测试基本生长扩展。"""
    print("=" * 60)
    print("测试 1: 基本生长扩展")
    print("=" * 60)
    
    # 创建初始路网（十字形）
    mock_env = MockEnv()
    initial_network = create_procedural_initial_network(
        env=mock_env,
        center=Vector2D(0, 0),
        initial_radius=300.0,
        num_arms=4
    )
    mock_env.road_network = initial_network
    
    print(f"初始路网: {len(initial_network.nodes)} 节点, {len(initial_network.edges)} 边")
    
    # 执行生长扩展
    config = GrowthConfig(
        iterations_per_expansion=2,
        max_front_size=4,
        branch_prob=0.4
    )
    
    expander = ProceduralGrowthExpansion(mock_env, config)
    new_nodes = expander.grow()
    
    print(f"扩展后: {len(initial_network.nodes)} 节点, {len(initial_network.edges)} 边")
    print(f"新增节点: {len(new_nodes)}")
    
    # 显示节点连接
    print("\n节点连接详情:")
    for node in new_nodes[:5]:  # 只显示前5个
        connections = len(node.incoming_edges) + len(node.outgoing_edges)
        print(f"  {node.name} @ ({node.position.x:.0f}, {node.position.y:.0f}) - {connections} 连接")
    
    return initial_network


def test_expand_city_procedurally():
    """测试便捷函数。"""
    print("\n" + "=" * 60)
    print("测试 2: 使用便捷函数扩展")
    print("=" * 60)
    
    # 创建初始路网
    mock_env = MockEnv()
    initial_network = create_procedural_initial_network(
        env=mock_env,
        center=Vector2D(0, 0),
        initial_radius=250.0,
        num_arms=4
    )
    mock_env.road_network = initial_network
    
    print(f"初始: {len(initial_network.nodes)} 节点, {len(initial_network.edges)} 边")
    
    # 小规模扩展
    new_nodes_small = expand_city_procedurally(mock_env, "small")
    print(f"小规模扩展后: {len(initial_network.nodes)} 节点 (+{len(new_nodes_small)})")
    
    # 中规模扩展
    new_nodes_medium = expand_city_procedurally(mock_env, "medium")
    print(f"中规模扩展后: {len(initial_network.nodes)} 节点 (+{len(new_nodes_medium)})")
    
    return initial_network


def test_integration_with_planner():
    """测试与 PlanningAgent 集成。"""
    print("\n" + "=" * 60)
    print("测试 3: 与 PlanningAgent 集成")
    print("=" * 60)
    
    # 创建仿真环境
    network = RoadNetwork("test_integration")
    env = SimulationEnvironment(network)
    
    # 创建初始十字形路网
    mock_env = MockEnv()
    initial_network = create_procedural_initial_network(
        env=mock_env,
        center=Vector2D(0, 0),
        initial_radius=300.0,
        num_arms=4
    )
    env.road_network = initial_network
    
    # 创建 PlanningAgent
    planner = PopulationCityPlanner(
        environment=env,
        use_llm=False,
        population_per_node=2,
        expansion_threshold=0.5,
        max_nodes=30
    )
    env.add_agent(planner)
    
    print(f"初始状态: {len(env.road_network.nodes)} 节点")
    
    # 模拟人口增长触发扩展
    for i in range(3):
        print(f"\n--- 扩展轮次 {i+1} ---")
        
        # 手动触发扩展
        success = planner._expand_with_growth("medium")
        
        if success:
            print(f"扩展后: {len(env.road_network.nodes)} 节点, {len(env.road_network.edges)} 边")
        else:
            print("扩展未成功")
            break
    
    return env.road_network


def visualize_network(network, title="Network"):
    """可视化路网。"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # 绘制边
        drawn = set()
        for edge in network.edges.values():
            key = tuple(sorted([id(edge.from_node), id(edge.to_node)]))
            if key in drawn:
                continue
            drawn.add(key)
            
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y
            ax.plot([x1, x2], [y1, y2], 'k-', linewidth=1.5, alpha=0.6)
        
        # 绘制节点
        for node in network.nodes.values():
            if node.is_intersection:
                color = 'red'
                size = 100
            else:
                color = 'blue'
                size = 50
            ax.scatter(node.position.x, node.position.y, c=color, s=size, zorder=5)
        
        ax.set_aspect('equal')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        # 添加统计
        stats = f"Nodes: {len(network.nodes)} | Edges: {len(network.edges)} | " \
                f"Intersections: {sum(1 for n in network.nodes.values() if n.is_intersection)}"
        ax.text(0.02, 0.98, stats, transform=ax.transAxes,
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        return fig
    except ImportError:
        return None


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("生长式城市扩展测试")
    print("=" * 60)
    
    # 测试 1
    network1 = test_growth_expansion_basic()
    fig1 = visualize_network(network1, "Test 1: Basic Growth Expansion")
    if fig1:
        fig1.savefig("test_growth_basic.png", dpi=150, bbox_inches='tight')
        print("\n已保存: test_growth_basic.png")
    
    # 测试 2
    network2 = test_expand_city_procedurally()
    fig2 = visualize_network(network2, "Test 2: Multi-stage Expansion")
    if fig2:
        fig2.savefig("test_growth_multi.png", dpi=150, bbox_inches='tight')
        print("已保存: test_growth_multi.png")
    
    # 测试 3
    network3 = test_integration_with_planner()
    fig3 = visualize_network(network3, "Test 3: Integration with Planner")
    if fig3:
        fig3.savefig("test_growth_integration.png", dpi=150, bbox_inches='tight')
        print("已保存: test_growth_integration.png")
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
