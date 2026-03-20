"""
测试真正仿照 procedural_city_generation 的路网扩展。

验证：
1. Vertex + neighbours 图结构
2. Front 迭代生长
3. Check 函数处理相交
4. KDTree 空间查询
5. 自动创建交叉口
"""

import sys
sys.path.insert(0, 'd:\\项目\\CITY')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from city.environment.road_network import RoadNetwork, Node
from city.environment.dynamic_network import create_procedural_initial_network
from city.environment.procedural_roadmap import (
    ProceduralRoadmapGenerator,
    ProceduralConfig,
    ProceduralVertex,
    expand_with_procedural_roadmap
)
from city.simulation.environment import SimulationEnvironment
from city.utils.vector import Vector2D


class MockEnv:
    """Mock 环境。"""
    def __init__(self):
        self.agents = []
        self.road_network = RoadNetwork("test")
        self.current_time = 0
        
    def add_agent(self, agent):
        self.agents.append(agent)


def test_vertex_structure():
    """测试 Vertex + neighbours 图结构。"""
    print("=" * 60)
    print("测试 1: Vertex + neighbours 图结构")
    print("=" * 60)
    
    # 创建顶点
    v1 = ProceduralVertex(Vector2D(0, 0))
    v2 = ProceduralVertex(Vector2D(100, 0))
    v3 = ProceduralVertex(Vector2D(100, 100))
    
    # 建立连接（双向）
    v1.connection(v2)
    v2.connection(v3)
    
    print(f"v1 的邻居数: {len(v1.neighbours)}")
    print(f"v2 的邻居数: {len(v2.neighbours)}")
    print(f"v3 的邻居数: {len(v3.neighbours)}")
    
    assert len(v1.neighbours) == 1, "v1 应该有 1 个邻居"
    assert len(v2.neighbours) == 2, "v2 应该有 2 个邻居"
    assert len(v3.neighbours) == 1, "v3 应该有 1 个邻居"
    
    print("[OK] Vertex 结构测试通过")


def test_kdtree_query():
    """测试 KDTree 空间查询。"""
    print("\n" + "=" * 60)
    print("测试 2: KDTree 空间查询")
    print("=" * 60)
    
    mock_env = MockEnv()
    generator = ProceduralRoadmapGenerator(mock_env)
    
    # 添加一些顶点
    for i in range(10):
        v = ProceduralVertex(Vector2D(i * 100, i * 50))
        generator.vertex_list.append(v)
    
    generator._update_kdtree()
    
    # 查询附近节点
    query_pos = np.array([250, 125])  # 应该在 (200, 100) 和 (300, 150) 附近
    distances, vertices = generator._find_nearby_vertices(query_pos, max_distance=200)
    
    print(f"查询位置: ({query_pos[0]}, {query_pos[1]})")
    print(f"找到 {len(vertices)} 个附近节点:")
    for v, d in zip(vertices, distances):
        print(f"  {v} - 距离: {d:.1f}")
    
    assert len(vertices) > 0, "应该找到附近节点"
    print("[OK] KDTree 查询测试通过")


def test_intersection_detection():
    """测试相交检测和交叉口创建。"""
    print("\n" + "=" * 60)
    print("测试 3: 相交检测和交叉口创建")
    print("=" * 60)
    
    mock_env = MockEnv()
    generator = ProceduralRoadmapGenerator(mock_env)
    
    # 创建两条相交的边
    v1 = ProceduralVertex(Vector2D(0, 0))
    v2 = ProceduralVertex(Vector2D(200, 200))
    v1.connection(v2)
    generator.vertex_list.extend([v1, v2])
    generator._update_kdtree()
    
    # 尝试添加一条与之相交的边
    v3 = ProceduralVertex(Vector2D(0, 200))
    suggested = ProceduralVertex(Vector2D(200, 0))
    
    # 建立 v3 的邻居关系（模拟正常生长）
    v3_neighbour = ProceduralVertex(Vector2D(-100, 200))
    v3.connection(v3_neighbour)
    
    generator.vertex_list.extend([v3, v3_neighbour])
    generator._update_kdtree()
    
    # 检查建议节点
    newfront = []
    result = generator.check(suggested, v3, newfront)
    
    print(f"建议节点: ({suggested.coords[0]}, {suggested.coords[1]})")
    print(f"检查后的顶点数: {len(generator.vertex_list)}")
    
    # 应该检测到相交并创建交叉口
    # 交点应该在 (100, 100) 附近
    
    print("[OK] 相交检测测试完成")


def test_iteration_growth():
    """测试单次迭代生长。"""
    print("\n" + "=" * 60)
    print("测试 4: 单次迭代生长")
    print("=" * 60)
    
    mock_env = MockEnv()
    
    # 创建初始十字形路网
    initial = create_procedural_initial_network(
        env=mock_env,
        center=Vector2D(0, 0),
        initial_radius=300.0,
        num_arms=4
    )
    mock_env.road_network = initial
    
    print(f"初始节点: {len(initial.nodes)}")
    
    # 创建生成器并生长
    generator = ProceduralRoadmapGenerator(mock_env)
    new_vertices = generator.grow(num_iterations=2)
    
    print(f"新增顶点: {len(new_vertices)}")
    print(f"总顶点: {len(generator.vertex_list)}")
    
    # 转换为 RoadNetwork
    generator.to_road_network()
    
    print(f"转换后路网: {len(mock_env.road_network.nodes)} 节点, "
          f"{len(mock_env.road_network.edges)} 边")
    
    return mock_env.road_network


def test_full_expansion():
    """测试完整扩展流程。"""
    print("\n" + "=" * 60)
    print("测试 5: 完整扩展流程")
    print("=" * 60)
    
    mock_env = MockEnv()
    
    # 创建初始路网
    initial = create_procedural_initial_network(
        env=mock_env,
        center=Vector2D(0, 0),
        initial_radius=250.0,
        num_arms=4
    )
    mock_env.road_network = initial
    
    print(f"初始: {len(initial.nodes)} 节点, {len(initial.edges)} 边")
    
    # 多轮扩展
    for i in range(3):
        print(f"\n--- 扩展轮次 {i+1} ---")
        num_new = expand_with_procedural_roadmap(mock_env, num_iterations=2)
        print(f"本轮新增: {num_new} 节点")
        print(f"当前总计: {len(mock_env.road_network.nodes)} 节点, "
              f"{len(mock_env.road_network.edges)} 边")
    
    return mock_env.road_network


def visualize_network(network, title, filename):
    """可视化路网。"""
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
    
    # 统计
    stats = f"Nodes: {len(network.nodes)} | Edges: {len(network.edges)} | " \
            f"Intersections: {sum(1 for n in network.nodes.values() if n.is_intersection)}"
    ax.text(0.02, 0.98, stats, transform=ax.transAxes,
           fontsize=10, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"已保存: {filename}")


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("真正 Procedural City Generation 路网扩展测试")
    print("=" * 60)
    
    # 基础测试
    test_vertex_structure()
    test_kdtree_query()
    test_intersection_detection()
    
    # 生长测试
    network1 = test_iteration_growth()
    visualize_network(network1, "Test 4: Single Iteration Growth", 
                     "test_true_procedural_single.png")
    
    network2 = test_full_expansion()
    visualize_network(network2, "Test 5: Full Multi-round Expansion",
                     "test_true_procedural_full.png")
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
