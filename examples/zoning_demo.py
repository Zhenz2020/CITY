"""
城市规划Agent演示脚本。

展示基于LLM的城市功能区域规划智能体。

使用方法:
    python examples/zoning_demo.py [--visual] [--no-llm]

选项:
    --visual: 启用可视化
    --no-llm: 不使用LLM，仅使用规则规划
"""

import argparse
import sys
import time

# 添加项目路径
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.urban_planning.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def create_grid_network(size: int = 2, spacing: float = 400.0) -> RoadNetwork:
    """
    创建网格状道路网络。
    
    Args:
        size: 网格大小 (size x size)
        spacing: 节点间距
    
    Returns:
        RoadNetwork实例
    """
    network = RoadNetwork("grid_city")
    nodes: dict[tuple[int, int], Node] = {}
    
    # 创建节点
    for i in range(size):
        for j in range(size):
            x = i * spacing
            y = j * spacing
            node = Node(
                position=Vector2D(x, y),
                name=f"node_{i}_{j}"
            )
            network.add_node(node)
            nodes[(i, j)] = node
    
    # 创建边（网格连接）
    for i in range(size):
        for j in range(size):
            current = nodes[(i, j)]
            
            # 向右连接
            if i < size - 1:
                right = nodes[(i + 1, j)]
                network.create_edge(current, right, num_lanes=2)
            
            # 向上连接
            if j < size - 1:
                up = nodes[(i, j + 1)]
                network.create_edge(current, up, num_lanes=2)
    
    print(f"[路网] 创建了 {size}x{size} 网格网络，共 {len(network.nodes)} 个节点，{len(network.edges)} 条边")
    return network


def run_zoning_simulation(use_visual: bool = True, use_llm: bool = True, duration: float = 120.0):
    """
    运行城市规划仿真。
    
    Args:
        use_visual: 是否启用可视化
        use_llm: 是否使用LLM
        duration: 仿真时长（秒）
    """
    print("=" * 60)
    print("城市规划Agent演示")
    print(f"模式: {'可视化' if use_visual else '无可视化'} | {'LLM规划' if use_llm else '规则规划'}")
    print("=" * 60)
    
    # 创建道路网络
    network = create_grid_network(size=3, spacing=400.0)
    
    # 创建仿真环境
    env = SimulationEnvironment(network)
    
    # 创建城市规划智能体
    zoning_agent = ZoningAgent(
        environment=env,
        use_llm=use_llm,
        planning_interval=15.0,  # 每15秒尝试规划一次
        max_zones=20,
        min_zone_size=60.0,
        max_zone_size=150.0,
        buffer_distance=15.0
    )
    env.add_agent(zoning_agent)
    
    # 初始化一些区域
    print("\n[初始化] 创建初始区域...")
    _create_initial_zones(zoning_agent, network)
    
    # 设置可视化
    visualizer = None
    if use_visual:
        try:
            from city.visualization.zoning_visualizer import ZoningVisualizer
            visualizer = ZoningVisualizer(env, zoning_agent, figsize=(14, 12))
            print("[可视化] 已启用")
        except ImportError as e:
            print(f"[警告] 无法启用可视化: {e}")
            use_visual = False
    
    # 启动仿真
    print(f"\n[仿真] 开始运行，时长: {duration}秒...")
    print("-" * 60)
    
    env.start()
    start_time = time.time()
    step_count = 0
    
    try:
        while env.is_running and (time.time() - start_time) < duration:
            # 执行一步
            env.step()
            step_count += 1
            
            # 更新可视化
            if visualizer and step_count % 5 == 0:
                visualizer.render(pause=0.001)
            
            # 定期输出状态
            if step_count % 100 == 0:
                stats = zoning_agent.zone_manager.get_statistics()
                print(f"[t={env.current_time:.1f}s] 区域: {stats['total_zones']}, "
                      f"人口: {stats['total_population']}, "
                      f"面积: {stats['total_area']:.0f}m²")
    
    except KeyboardInterrupt:
        print("\n[仿真] 被用户中断")
    
    finally:
        # 输出最终统计
        print("\n" + "=" * 60)
        print("仿真结束 - 最终统计")
        print("=" * 60)
        
        final_stats = zoning_agent.zone_manager.get_statistics()
        print(f"总区域数: {final_stats['total_zones']}")
        print(f"总人口: {final_stats['total_population']}")
        print(f"总规划面积: {final_stats['total_area']:.0f}m²")
        
        print("\n各类型区域分布:")
        for zone_type in ZoneType:
            if zone_type.name in final_stats['by_type']:
                type_stats = final_stats['by_type'][zone_type.name]
                print(f"  {zone_type.display_name}: {type_stats['count']}个, "
                      f"面积{type_stats['total_area']:.0f}m², "
                      f"人口{type_stats['total_population']}")
        
        print(f"\n规划历史记录数: {len(zoning_agent.planning_history)}")
        
        # 关闭可视化
        if visualizer:
            visualizer.save_frame("zoning_result.png")
            print("\n[可视化] 已保存截图: zoning_result.png")
            input("\n按Enter键关闭可视化窗口...")
            visualizer.close()
        
        env.stop()


def _create_initial_zones(zoning_agent: ZoningAgent, network: RoadNetwork) -> None:
    """创建初始区域。"""
    # 获取网络边界
    positions = [n.position for n in network.nodes.values()]
    min_x = min(p.x for p in positions)
    max_x = max(p.x for p in positions)
    min_y = min(p.y for p in positions)
    max_y = max(p.y for p in positions)
    
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    
    # 创建几个初始住宅区
    residential_positions = [
        (center_x - 150, center_y - 150),
        (center_x + 150, center_y - 150),
        (center_x - 150, center_y + 150),
    ]
    
    for i, (x, y) in enumerate(residential_positions):
        zone = Zone(
            zone_type=ZoneType.RESIDENTIAL,
            center=Vector2D(x, y),
            width=120,
            height=100,
            name=f"住宅区_{i+1}"
        )
        zone.target_population = int(zone.max_population * 0.5)
        zone.population = zone.target_population
        
        # 连接到最近的节点
        nearest = min(network.nodes.values(), key=lambda n: zone.distance_to_node(n))
        zone.connect_to_node(nearest)
        
        zoning_agent.zone_manager.add_zone(zone)
        print(f"  创建: {zone.name}, 人口: {zone.population}")
    
    # 创建一个初始商业区
    commercial_zone = Zone(
        zone_type=ZoneType.COMMERCIAL,
        center=Vector2D(center_x + 150, center_y + 150),
        width=100,
        height=80,
        name="商业区_1"
    )
    commercial_zone.target_population = int(commercial_zone.max_population * 0.4)
    commercial_zone.population = commercial_zone.target_population
    nearest = min(network.nodes.values(), key=lambda n: commercial_zone.distance_to_node(n))
    commercial_zone.connect_to_node(nearest)
    zoning_agent.zone_manager.add_zone(commercial_zone)
    print(f"  创建: {commercial_zone.name}, 人口: {commercial_zone.population}")


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description='城市规划Agent演示')
    parser.add_argument('--visual', action='store_true', help='启用可视化')
    parser.add_argument('--no-llm', action='store_true', help='不使用LLM')
    parser.add_argument('--duration', type=float, default=120.0, help='仿真时长(秒)')
    
    args = parser.parse_args()
    
    run_zoning_simulation(
        use_visual=args.visual,
        use_llm=not args.no_llm,
        duration=args.duration
    )


if __name__ == "__main__":
    main()
