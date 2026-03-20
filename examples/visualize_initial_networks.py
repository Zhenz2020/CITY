"""
可视化不同的初始路网类型。
"""

import sys
sys.path.insert(0, 'd:\\项目\\CITY')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from city.environment.initial_network import (
    create_cross_network,
    create_grid_network,
    create_radial_network
)
from city.environment.road_network import RoadNetwork
from city.simulation.environment import SimulationEnvironment
from city.utils.vector import Vector2D


def visualize_network(network, title, filename):
    """可视化路网。"""
    fig, ax = plt.subplots(figsize=(10, 10))
    
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
        if node.traffic_light:
            color = 'red'  # 有红绿灯的交叉口
            size = 100
        elif node.is_intersection:
            color = 'orange'  # 交叉口但没有红绿灯
            size = 80
        else:
            color = 'blue'  # 普通节点
            size = 50
        ax.scatter(node.position.x, node.position.y, c=color, s=size, zorder=5)
    
    ax.set_aspect('equal')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    
    # 统计
    stats = (f"Nodes: {len(network.nodes)} | Edges: {len(network.edges)} | "
             f"TL: {sum(1 for n in network.nodes.values() if n.traffic_light)}")
    ax.text(0.02, 0.98, stats, transform=ax.transAxes,
           fontsize=10, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")


def main():
    """生成所有路网类型的可视化。"""
    print("Generating initial network visualizations...")
    
    # 1. 十字形（基础）
    print("\n1. Cross Network (Basic)")
    network = RoadNetwork('test')
    env = SimulationEnvironment(network)
    net = create_cross_network(env, add_ring=False)
    visualize_network(net, "Cross Network (Basic)", "initial_cross_basic.png")
    
    # 2. 十字形（带环路）
    print("2. Cross Network (With Ring)")
    network = RoadNetwork('test')
    env = SimulationEnvironment(network)
    net = create_cross_network(env, add_ring=True)
    visualize_network(net, "Cross Network (With Ring)", "initial_cross_ring.png")
    
    # 3. 2x2网格
    print("3. Grid 2x2")
    network = RoadNetwork('test')
    env = SimulationEnvironment(network)
    net = create_grid_network(env, grid_size=2)
    visualize_network(net, "Grid Network 2x2", "initial_grid_2x2.png")
    
    # 4. 3x3网格
    print("4. Grid 3x3")
    network = RoadNetwork('test')
    env = SimulationEnvironment(network)
    net = create_grid_network(env, grid_size=3)
    visualize_network(net, "Grid Network 3x3", "initial_grid_3x3.png")
    
    # 5. 放射状（4臂）
    print("5. Radial (4 arms, 2 rings)")
    network = RoadNetwork('test')
    env = SimulationEnvironment(network)
    net = create_radial_network(env, num_arms=4, num_rings=2)
    visualize_network(net, "Radial Network (4 arms, 2 rings)", "initial_radial_4.png")
    
    # 6. 放射状（6臂）
    print("6. Radial (6 arms, 2 rings)")
    network = RoadNetwork('test')
    env = SimulationEnvironment(network)
    net = create_radial_network(env, num_arms=6, num_rings=2)
    visualize_network(net, "Radial Network (6 arms, 2 rings)", "initial_radial_6.png")
    
    print("\nAll visualizations generated!")


if __name__ == "__main__":
    main()
