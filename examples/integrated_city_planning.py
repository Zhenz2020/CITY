"""
集成城市规划演示 - 路网规划 + 功能区域规划。

结合路网规划Agent和城市规划Agent，展示完整的城市演化过程：
1. 路网规划Agent根据人口需求扩展道路网络
2. 城市规划Agent规划功能区域（住宅、商业、医院、学校等）

使用方法:
    python examples/integrated_city_planning.py [--visual] [--no-llm]
"""

import argparse
import sys
import time

sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.urban_planning.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def create_initial_network() -> RoadNetwork:
    """创建初始2x2网格网络。"""
    network = RoadNetwork("evolving_city")
    
    # 创建2x2网格
    nodes = {}
    for i in range(2):
        for j in range(2):
            node = Node(
                position=Vector2D(i * 400, j * 400),
                name=f"node_{i}_{j}"
            )
            network.add_node(node)
            nodes[(i, j)] = node
    
    # 连接节点
    for i in range(2):
        for j in range(2):
            if i < 1:
                network.create_edge(nodes[(i, j)], nodes[(i+1, j)], num_lanes=2)
            if j < 1:
                network.create_edge(nodes[(i, j)], nodes[(i, j+1)], num_lanes=2)
    
    return network


def run_integrated_planning(use_visual: bool = True, use_llm: bool = True, duration: float = 180.0):
    """
    运行集成规划仿真。
    
    Args:
        use_visual: 是否启用可视化
        use_llm: 是否使用LLM
        duration: 仿真时长
    """
    print("=" * 70)
    print("集成城市规划演示 - 路网规划 + 功能区域规划")
    print(f"模式: {'可视化' if use_visual else '无可视化'} | {'LLM驱动' if use_llm else '规则驱动'}")
    print("=" * 70)
    
    # 创建初始网络
    network = create_initial_network()
    print(f"\n[初始化] 创建初始2x2网格网络，{len(network.nodes)}个节点")
    
    # 创建仿真环境
    env = SimulationEnvironment(network)
    
    # 创建路网规划Agent（人口驱动）
    road_planner = PopulationCityPlanner(
        environment=env,
        use_llm=use_llm,
        population_per_node=3,
        expansion_threshold=0.7,
        spawn_interval=4.0,
        max_nodes=16,
        min_edge_length=200.0,
        max_edge_length=500.0
    )
    env.add_agent(road_planner)
    print(f"[路网规划] Agent已添加，扩展阈值: {road_planner.expansion_threshold*100:.0f}%")
    
    # 创建城市规划Agent
    zoning_agent = ZoningAgent(
        environment=env,
        use_llm=use_llm,
        planning_interval=25.0,
        max_zones=25,
        min_zone_size=50.0,
        max_zone_size=150.0,
        buffer_distance=20.0
    )
    env.add_agent(zoning_agent)
    print(f"[城市规划] Agent已添加，规划间隔: {zoning_agent.planning_interval}秒")
    
    # 设置可视化
    visualizer = None
    if use_visual:
        try:
            from city.visualization.zoning_visualizer import IntegratedCityVisualizer
            visualizer = IntegratedCityVisualizer(
                env, 
                zoning_agent=zoning_agent,
                figsize=(16, 10),
                enable_zones=True,
                enable_traffic=True
            )
            print("[可视化] 集成可视化已启用")
        except ImportError as e:
            print(f"[警告] 无法启用可视化: {e}")
            use_visual = False
    
    # 启动仿真
    print(f"\n[仿真] 开始运行，时长: {duration}秒...")
    print("-" * 70)
    
    env.start()
    start_time = time.time()
    step_count = 0
    last_report_time = 0
    
    try:
        while env.is_running and (time.time() - start_time) < duration:
            # 执行一步
            env.step()
            step_count += 1
            
            # 更新可视化
            if visualizer and step_count % 3 == 0:
                visualizer.render(pause=0.001)
            
            # 定期输出状态报告
            current_time = env.current_time
            if current_time - last_report_time >= 20:
                last_report_time = current_time
                _print_status_report(env, road_planner, zoning_agent)
    
    except KeyboardInterrupt:
        print("\n[仿真] 被用户中断")
    
    finally:
        # 最终报告
        print("\n" + "=" * 70)
        print("仿真结束 - 最终报告")
        print("=" * 70)
        _print_final_report(env, road_planner, zoning_agent)
        
        # 保存截图
        if visualizer:
            visualizer.save_frame("integrated_city_planning.png")
            print("\n[可视化] 已保存截图: integrated_city_planning.png")
            input("\n按Enter键关闭可视化窗口...")
            visualizer.close()
        
        env.stop()


def _print_status_report(
    env: SimulationEnvironment,
    road_planner: PopulationCityPlanner,
    zoning_agent: ZoningAgent
) -> None:
    """打印状态报告。"""
    road_stats = road_planner.get_city_stats()
    zone_stats = zoning_agent.zone_manager.get_statistics()
    
    print(f"\n[状态报告 t={env.current_time:.1f}s]")
    print(f"  路网: {road_stats['nodes']}节点 | 人口: {road_stats['current_population']}/"
          f"{road_stats['max_capacity']} ({road_stats['density_percent']:.0f}%)")
    print(f"  区域: {zone_stats['total_zones']}个 | 总人口: {zone_stats['total_population']} | "
          f"面积: {zone_stats['total_area']:.0f}m²")


def _print_final_report(
    env: SimulationEnvironment,
    road_planner: PopulationCityPlanner,
    zoning_agent: ZoningAgent
) -> None:
    """打印最终报告。"""
    # 路网规划统计
    road_stats = road_planner.get_city_stats()
    print("\n【路网规划统计】")
    print(f"  最终节点数: {road_stats['nodes']}")
    print(f"  扩张次数: {len(road_planner.expansion_history)}")
    print(f"  总生成车辆: {road_planner.total_spawns}")
    
    # 城市规划统计
    zone_stats = zoning_agent.zone_manager.get_statistics()
    print("\n【城市规划统计】")
    print(f"  总区域数: {zone_stats['total_zones']}")
    print(f"  总人口: {zone_stats['total_population']}")
    print(f"  总规划面积: {zone_stats['total_area']:.0f}m²")
    print(f"  规划历史: {len(zoning_agent.planning_history)}次")
    
    print("\n【各类型区域分布】")
    for zone_type in ZoneType:
        if zone_type.name in zone_stats['by_type']:
            type_stats = zone_stats['by_type'][zone_type.name]
            percentage = (type_stats['total_area'] / zone_stats['total_area']) * 100
            print(f"  {zone_type.display_name:8s}: {type_stats['count']:2d}个, "
                  f"面积{type_stats['total_area']:8.0f}m² ({percentage:5.1f}%), "
                  f"人口{type_stats['total_population']:4d}")


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description='集成城市规划演示')
    parser.add_argument('--visual', action='store_true', help='启用可视化')
    parser.add_argument('--no-llm', action='store_true', help='不使用LLM')
    parser.add_argument('--duration', type=float, default=180.0, help='仿真时长(秒)')
    
    args = parser.parse_args()
    
    run_integrated_planning(
        use_visual=args.visual,
        use_llm=not args.no_llm,
        duration=args.duration
    )


if __name__ == "__main__":
    main()
