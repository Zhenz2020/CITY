"""
可视化仿 procedural_city_generation 的路网生成结果。

生成对比图像：
1. 传统 2x2 网格
2. 十字形初始路网
3. Grid 生长路网
4. Organic 生长路网
5. Radial 生长路网
"""

import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.environment.procedural_network import (
    GrowthRule,
    create_procedural_network
)
from city.environment.dynamic_network import create_procedural_initial_network
from city.utils.vector import Vector2D


def save_network_image(network: RoadNetwork, filename: str, title: str = ""):
    """保存路网图像到文件。"""
    try:
        import matplotlib
        matplotlib.use('Agg')  # 使用非交互式后端
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # 收集所有边
        drawn_edges = set()
        for edge in network.edges.values():
            # 避免重复绘制（双向边）
            key = tuple(sorted([id(edge.from_node), id(edge.to_node)]))
            if key in drawn_edges:
                continue
            drawn_edges.add(key)
            
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y
            
            # 绘制边
            ax.plot([x1, x2], [y1, y2], 'k-', linewidth=1.5, alpha=0.6)
        
        # 绘制节点
        for node in network.nodes.values():
            if node.is_intersection:
                color = 'red'
                size = 100
            else:
                color = 'blue'
                size = 50
            
            ax.scatter(node.position.x, node.position.y, 
                      c=color, s=size, zorder=5, alpha=0.8)
        
        ax.set_aspect('equal')
        ax.set_title(title or filename, fontsize=14)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # 添加统计信息
        stats_text = f"Nodes: {len(network.nodes)} | Edges: {len(network.edges)} | " \
                    f"Intersections: {sum(1 for n in network.nodes.values() if n.is_intersection)}"
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"已保存: {filename}")
        return True
        
    except ImportError:
        print("matplotlib 未安装，跳过图像生成")
        return False


def create_traditional_grid():
    """创建传统 2x2 网格。"""
    network = RoadNetwork("traditional_grid")
    nodes = {}
    spacing = 300
    
    for i in range(2):
        for j in range(2):
            n = Node(
                Vector2D(i * spacing, j * spacing),
                name=f"n{i}_{j}",
                is_intersection=False
            )
            nodes[(i, j)] = n
            network.add_node(n)
    
    for j in range(2):
        network.create_edge(nodes[(0, j)], nodes[(1, j)], num_lanes=2, bidirectional=True)
    for i in range(2):
        network.create_edge(nodes[(i, 0)], nodes[(i, 1)], num_lanes=2, bidirectional=True)
    
    return network


def create_cross_network():
    """创建十字形初始路网。"""
    class MockEnv:
        def __init__(self):
            self.agents = []
        def add_agent(self, agent):
            self.agents.append(agent)
    
    return create_procedural_initial_network(
        env=MockEnv(),
        center=Vector2D(0, 0),
        initial_radius=400.0,
        num_arms=4
    )


def main():
    """生成所有路网图像。"""
    print("=" * 60)
    print("生成路网可视化图像")
    print("=" * 60)
    
    # 1. 传统网格
    print("\n1. 生成传统 2x2 网格...")
    grid = create_traditional_grid()
    save_network_image(grid, "network_traditional_grid.png", "Traditional 2x2 Grid")
    
    # 2. 十字形初始
    print("\n2. 生成十字形初始路网...")
    cross = create_cross_network()
    save_network_image(cross, "network_cross_initial.png", "Procedural Cross Initial")
    
    # 3. Grid 生长
    print("\n3. 生成 Grid 生长路网...")
    grid_proc = create_procedural_network(
        city_center=Vector2D(0, 0),
        boundary_size=600.0,
        iterations=20,
        rule=GrowthRule.GRID
    )
    save_network_image(grid_proc, "network_grid_growth.png", "Grid Growth")
    
    # 4. Organic 生长
    print("\n4. 生成 Organic 生长路网...")
    organic = create_procedural_network(
        city_center=Vector2D(0, 0),
        boundary_size=600.0,
        iterations=20,
        rule=GrowthRule.ORGANIC
    )
    save_network_image(organic, "network_organic_growth.png", "Organic Growth")
    
    # 5. Radial 生长
    print("\n5. 生成 Radial 生长路网...")
    radial = create_procedural_network(
        city_center=Vector2D(0, 0),
        boundary_size=600.0,
        iterations=20,
        rule=GrowthRule.RADIAL
    )
    save_network_image(radial, "network_radial_growth.png", "Radial Growth")
    
    print("\n" + "=" * 60)
    print("所有图像生成完成!")
    print("=" * 60)
    print("\n生成的文件:")
    print("  - network_traditional_grid.png")
    print("  - network_cross_initial.png")
    print("  - network_grid_growth.png")
    print("  - network_organic_growth.png")
    print("  - network_radial_growth.png")


if __name__ == "__main__":
    main()
