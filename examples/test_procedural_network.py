"""
测试仿 procedural_city_generation 的路网生成器。

比较：
1. 传统的 2x2 网格路网
2. 新的十字形种子 + 生长规则路网
"""

import sys
sys.path.insert(0, 'd:\\项目\\CITY')

import math
from city.environment.road_network import RoadNetwork, Node
from city.environment.procedural_network import (
    ProceduralRoadGenerator, 
    RoadGrowthConfig,
    GrowthRule,
    create_procedural_network
)
from city.environment.dynamic_network import create_procedural_initial_network
from city.utils.vector import Vector2D


def test_traditional_grid():
    """测试传统 2x2 网格路网。"""
    print("=" * 60)
    print("【传统 2x2 网格路网】")
    print("=" * 60)
    
    network = RoadNetwork("traditional_grid")
    nodes = {}
    spacing = 300
    
    # 创建 2x2 节点
    for i in range(2):
        for j in range(2):
            node = Node(
                position=Vector2D(i * spacing, j * spacing),
                name=f"node_{i}_{j}",
                is_intersection=False
            )
            nodes[(i, j)] = node
            network.add_node(node)
    
    # 水平连接
    for j in range(2):
        network.create_edge(nodes[(0, j)], nodes[(1, j)], num_lanes=2, bidirectional=True)
    
    # 垂直连接
    for i in range(2):
        network.create_edge(nodes[(i, 0)], nodes[(i, 1)], num_lanes=2, bidirectional=True)
    
    _print_network_stats(network)
    return network


def test_procedural_cross():
    """测试新的十字形初始路网。"""
    print("\n" + "=" * 60)
    print("【仿 Procedural 十字形路网】")
    print("=" * 60)
    
    # 使用新的生成函数
    network = create_procedural_initial_network(
        env=MockEnv(),
        center=Vector2D(0, 0),
        initial_radius=400.0,
        num_arms=4
    )
    
    _print_network_stats(network)
    return network


def test_procedural_growth():
    """测试生长算法生成的路网。"""
    print("\n" + "=" * 60)
    print("【生长算法路网 (Grid规则)】")
    print("=" * 60)
    
    config = RoadGrowthConfig(
        grid_forward_prob=0.95,
        grid_turn_prob=0.25,
        grid_length_min=200.0,
        grid_length_max=280.0,
        min_node_distance=100.0,
        max_iterations=30,
        snap_threshold=70.0
    )
    
    generator = ProceduralRoadGenerator(
        config=config,
        default_rule=GrowthRule.GRID,
        city_center=Vector2D(0, 0),
        boundary=(-600, -600, 600, 600)
    )
    
    network = generator.generate(num_seed_points=4, iterations=30)
    
    _print_network_stats(network)
    return network


def test_procedural_organic():
    """测试 Organic 规则生成的路网。"""
    print("\n" + "=" * 60)
    print("【生长算法路网 (Organic规则)】")
    print("=" * 60)
    
    network = create_procedural_network(
        city_center=Vector2D(0, 0),
        boundary_size=800.0,
        iterations=25,
        rule=GrowthRule.ORGANIC
    )
    
    _print_network_stats(network)
    return network


def test_procedural_radial():
    """测试 Radial 规则生成的路网。"""
    print("\n" + "=" * 60)
    print("【生长算法路网 (Radial规则)】")
    print("=" * 60)
    
    network = create_procedural_network(
        city_center=Vector2D(0, 0),
        boundary_size=800.0,
        iterations=25,
        rule=GrowthRule.RADIAL
    )
    
    _print_network_stats(network)
    return network


def _print_network_stats(network: RoadNetwork) -> None:
    """打印路网统计信息。"""
    num_nodes = len(network.nodes)
    num_edges = len(network.edges)
    
    # 统计交叉口
    intersections = [n for n in network.nodes.values() if n.is_intersection]
    
    # 计算平均连接度
    total_degree = sum(
        len(n.incoming_edges) + len(n.outgoing_edges) 
        for n in network.nodes.values()
    )
    avg_degree = total_degree / num_nodes if num_nodes > 0 else 0
    
    # 计算网络范围
    if network.nodes:
        xs = [n.position.x for n in network.nodes.values()]
        ys = [n.position.y for n in network.nodes.values()]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
    else:
        width = height = 0
    
    print(f"节点数: {num_nodes}")
    print(f"边数: {num_edges}")
    print(f"交叉口数: {len(intersections)}")
    print(f"平均连接度: {avg_degree:.1f}")
    print(f"网络范围: {width:.0f} x {height:.0f}")
    
    # 打印节点详情
    print("\n节点详情:")
    for node in network.nodes.values():
        degree = len(node.incoming_edges) + len(node.outgoing_edges)
        conn_type = "交叉口" if node.is_intersection else "普通节点"
        print(f"  {node.name:15s} @ ({node.position.x:6.0f}, {node.position.y:6.0f}) "
              f"- {degree} 连接 ({conn_type})")


class MockEnv:
    """Mock 环境用于测试。"""
    def __init__(self):
        self.agents = []
    def add_agent(self, agent):
        self.agents.append(agent)


def visualize_network(network: RoadNetwork, title: str = "Network"):
    """可视化路网（如果 matplotlib 可用）。"""
    try:
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # 绘制边
        for edge in network.edges.values():
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y
            ax.plot([x1, x2], [y1, y2], 'k-', linewidth=1.5, alpha=0.6)
        
        # 绘制节点
        for node in network.nodes.values():
            color = 'red' if node.is_intersection else 'blue'
            size = 80 if node.is_intersection else 40
            ax.scatter(node.position.x, node.position.y, c=color, s=size, zorder=5)
            ax.annotate(node.name, (node.position.x, node.position.y),
                       xytext=(5, 5), textcoords='offset points', fontsize=7)
        
        ax.set_aspect('equal')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        return fig, ax
    except ImportError:
        print("(matplotlib 不可用，跳过可视化)")
        return None, None


def main():
    """主测试函数。"""
    print("\n" + "=" * 60)
    print("路网生成器对比测试")
    print("=" * 60)
    
    networks = {}
    
    # 1. 传统网格
    networks['grid'] = test_traditional_grid()
    
    # 2. 十字形初始
    networks['cross'] = test_procedural_cross()
    
    # 3. Grid 生长
    networks['growth_grid'] = test_procedural_growth()
    
    # 4. Organic 生长
    networks['growth_organic'] = test_procedural_organic()
    
    # 5. Radial 生长
    networks['growth_radial'] = test_procedural_radial()
    
    # 总结
    print("\n" + "=" * 60)
    print("【总结对比】")
    print("=" * 60)
    print(f"{'类型':<20} {'节点':>6} {'边':>6} {'交叉口':>8}")
    print("-" * 60)
    
    summary = [
        ("传统 2x2 网格", networks['grid']),
        ("十字形初始", networks['cross']),
        ("Grid 生长", networks['growth_grid']),
        ("Organic 生长", networks['growth_organic']),
        ("Radial 生长", networks['growth_radial']),
    ]
    
    for name, net in summary:
        nodes = len(net.nodes)
        edges = len(net.edges)
        inter = len([n for n in net.nodes.values() if n.is_intersection])
        print(f"{name:<20} {nodes:>6} {edges:>6} {inter:>8}")
    
    # 尝试可视化
    print("\n正在生成可视化...")
    figures = []
    for name, net in networks.items():
        fig, ax = visualize_network(net, name)
        if fig:
            figures.append((name, fig))
    
    if figures:
        import matplotlib.pyplot as plt
        plt.show()


if __name__ == "__main__":
    main()
