"""
使用仿 procedural_city_generation 的路网生成器示例。

展示如何创建自然城市风格的路网。
"""

import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.environment.procedural_network import (
    ProceduralRoadGenerator,
    RoadGrowthConfig,
    GrowthRule,
    create_procedural_network
)
from city.environment.dynamic_network import create_procedural_initial_network
from city.simulation.environment import SimulationEnvironment
from city.utils.vector import Vector2D


def example_1_basic_usage():
    """示例 1: 基本用法 - 使用默认参数生成路网。"""
    print("=" * 60)
    print("示例 1: 基本用法")
    print("=" * 60)
    
    # 使用默认参数生成 Grid 风格路网
    network = create_procedural_network(
        city_center=Vector2D(0, 0),
        boundary_size=600.0,
        iterations=20,
        rule=GrowthRule.GRID
    )
    
    print(f"生成完成: {len(network.nodes)} 个节点, {len(network.edges)} 条边")
    
    # 检查连通性
    nodes = list(network.nodes.values())
    if len(nodes) >= 2:
        path = network.find_shortest_path(nodes[0], nodes[-1])
        print(f"连通性检查: 从 {nodes[0].name} 到 {nodes[-1].name}")
        print(f"  路径存在: {path is not None}")
        if path:
            print(f"  路径长度: {len(path)} 个节点")


def example_2_custom_config():
    """示例 2: 自定义配置。"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义配置")
    print("=" * 60)
    
    # 创建自定义配置
    config = RoadGrowthConfig(
        # Grid 参数 - 更长的道路，更少的转弯
        grid_forward_prob=0.98,       # 98% 概率直行
        grid_turn_prob=0.15,          # 15% 概率转弯
        grid_length_min=250.0,        # 最小 250m
        grid_length_max=350.0,        # 最大 350m
        
        # Organic 参数
        organic_forward_prob=0.85,
        organic_turn_prob=0.30,
        organic_length_min=200.0,
        organic_length_max=400.0,
        organic_angle_variation=45.0,  # 更大的角度变化
        
        # 通用参数
        min_node_distance=120.0,      # 节点最小间距
        max_iterations=25,
        snap_threshold=80.0
    )
    
    # 使用自定义配置
    generator = ProceduralRoadGenerator(
        config=config,
        default_rule=GrowthRule.GRID,
        city_center=Vector2D(500, 500),  # 自定义城市中心
        boundary=(0, 0, 1000, 1000)       # 自定义边界
    )
    
    network = generator.generate(num_seed_points=4, iterations=25)
    print(f"生成完成: {len(network.nodes)} 个节点, {len(network.edges)} 条边")
    print(f"网络范围: {generator.boundary}")


def example_3_different_rules():
    """示例 3: 不同生长规则的对比。"""
    print("\n" + "=" * 60)
    print("示例 3: 不同生长规则对比")
    print("=" * 60)
    
    rules = [
        (GrowthRule.GRID, "Grid (网格状)"),
        (GrowthRule.ORGANIC, "Organic (有机状)"),
        (GrowthRule.RADIAL, "Radial (放射状)"),
    ]
    
    for rule, name in rules:
        network = create_procedural_network(
            city_center=Vector2D(0, 0),
            boundary_size=500.0,
            iterations=15,
            rule=rule
        )
        
        intersections = sum(1 for n in network.nodes.values() if n.is_intersection)
        print(f"{name:20s}: {len(network.nodes):2d} 节点, "
              f"{len(network.edges):2d} 边, {intersections} 交叉口")


def example_4_initial_cross_network():
    """示例 4: 使用十字形初始路网。"""
    print("\n" + "=" * 60)
    print("示例 4: 十字形初始路网")
    print("=" * 60)
    
    # 创建仿真环境
    network = RoadNetwork("temp")
    env = SimulationEnvironment(network)
    
    # 创建十字形初始路网
    new_network = create_procedural_initial_network(
        env=env,
        center=Vector2D(0, 0),
        initial_radius=300.0,
        num_arms=4
    )
    
    print(f"初始路网: {len(new_network.nodes)} 节点, {len(new_network.edges)} 边")
    print("\n结构:")
    print("       [北_far]")
    print("           |")
    print("       [北_near]")
    print("           |")
    print("[西_far]--[中心]--[东_far]")
    print("           |")
    print("       [南_near]")
    print("           |")
    print("       [南_far]")
    
    # 如果需要，可以继续扩展
    print("\n可以在此基础上继续扩展路网...")


def example_5_simulation_integration():
    """示例 5: 与仿真系统集成。"""
    print("\n" + "=" * 60)
    print("示例 5: 与仿真系统集成")
    print("=" * 60)
    
    # 创建初始路网
    network = create_procedural_network(
        city_center=Vector2D(0, 0),
        boundary_size=400.0,
        iterations=10,
        rule=GrowthRule.GRID
    )
    
    # 创建仿真环境
    env = SimulationEnvironment(network)
    
    print(f"仿真环境创建完成")
    print(f"路网: {len(network.nodes)} 节点, {len(network.edges)} 边")
    
    # 检查环境状态
    print(f"环境运行状态: {env.is_running}")
    
    # 可以开始仿真
    # env.start()
    # for _ in range(100):
    #     env.step()
    
    print("可以开始仿真...")


def example_6_comparison_with_grid():
    """示例 6: 与传统网格对比。"""
    print("\n" + "=" * 60)
    print("示例 6: 与传统网格对比")
    print("=" * 60)
    
    # 传统 2x2 网格
    print("\n【传统 2x2 网格】")
    grid_network = RoadNetwork("grid")
    nodes = {}
    for i in range(2):
        for j in range(2):
            n = Node(Vector2D(i*300, j*300), name=f"g{i}_{j}")
            nodes[(i,j)] = n
            grid_network.add_node(n)
    for j in range(2):
        grid_network.create_edge(nodes[(0,j)], nodes[(1,j)], num_lanes=2, bidirectional=True)
    for i in range(2):
        grid_network.create_edge(nodes[(i,0)], nodes[(i,1)], num_lanes=2, bidirectional=True)
    
    print(f"节点: {len(grid_network.nodes)}, 边: {len(grid_network.edges)}")
    print("特点: 规则的正方形网格")
    
    # Procedural 路网
    print("\n【Procedural Grid 路网】")
    proc_network = create_procedural_network(
        city_center=Vector2D(150, 150),
        boundary_size=600.0,
        iterations=12,
        rule=GrowthRule.GRID
    )
    print(f"节点: {len(proc_network.nodes)}, 边: {len(proc_network.edges)}")
    print("特点: 自然生长的路网，有主干道和支路")
    
    print("\n【对比】")
    print(f"传统网格更规则，适合规划型城市")
    print(f"Procedural 路网更自然，适合演化型城市")


def main():
    """运行所有示例。"""
    examples = [
        example_1_basic_usage,
        example_2_custom_config,
        example_3_different_rules,
        example_4_initial_cross_network,
        example_5_simulation_integration,
        example_6_comparison_with_grid,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
