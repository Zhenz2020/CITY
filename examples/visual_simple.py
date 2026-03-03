"""
可视化简单交叉口仿真。

实时显示车辆移动、交通信号灯状态变化等。
"""

import sys
sys.path.insert(0, '..')

from city.environment.road_network import (
    RoadNetwork, Node, TrafficLight
)
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.visualization.renderer import SimulationVisualizer
from city.agents.vehicle import VehicleType
from city.agents.traffic_manager import TrafficManager
from city.utils.vector import Vector2D


def create_intersection():
    """创建十字路口。"""
    network = RoadNetwork("visual_intersection")

    # 创建节点
    nodes = {
        'north_in': Node(Vector2D(0, 200), "north_in"),
        'north_out': Node(Vector2D(0, -200), "north_out"),
        'south_in': Node(Vector2D(0, -200), "south_in"),
        'south_out': Node(Vector2D(0, 200), "south_out"),
        'east_in': Node(Vector2D(200, 0), "east_in"),
        'east_out': Node(Vector2D(-200, 0), "east_out"),
        'west_in': Node(Vector2D(-200, 0), "west_in"),
        'west_out': Node(Vector2D(200, 0), "west_out"),
        'center': Node(Vector2D(0, 0), "center", is_intersection=True)
    }

    for node in nodes.values():
        network.add_node(node)

    # 创建路段
    network.create_edge(nodes['north_in'], nodes['center'], num_lanes=2)
    network.create_edge(nodes['south_in'], nodes['center'], num_lanes=2)
    network.create_edge(nodes['east_in'], nodes['center'], num_lanes=2)
    network.create_edge(nodes['west_in'], nodes['center'], num_lanes=2)
    network.create_edge(nodes['center'], nodes['north_out'], num_lanes=2)
    network.create_edge(nodes['center'], nodes['south_out'], num_lanes=2)
    network.create_edge(nodes['center'], nodes['east_out'], num_lanes=2)
    network.create_edge(nodes['center'], nodes['west_out'], num_lanes=2)

    # 信号灯
    nodes['center'].traffic_light = TrafficLight(
        nodes['center'], cycle_time=60, green_duration=30, yellow_duration=5
    )

    return network, nodes


def main():
    """主函数。"""
    print("=" * 60)
    print("可视化交通仿真")
    print("=" * 60)
    print("\n说明:")
    print("- 灰色粗线: 道路（双线）")
    print("- 白色虚线: 车道分隔线")
    print("- 浅灰色圆圈: 交叉口")
    print("- 小圆点: 交通信号灯（红/黄/绿）")
    print("- 彩色矩形: 车辆（蓝=轿车, 红=公交, 橙=卡车）")
    print("- 按 Ctrl+C 可随时停止仿真")
    print("=" * 60)

    # 创建道路网络
    network, nodes = create_intersection()
    print(f"\n创建道路网络: {len(network.nodes)} 个节点, {len(network.edges)} 个路段")

    # 创建仿真环境
    config = SimulationConfig(
        time_step=0.5,
        max_simulation_time=300.0,
        real_time_factor=1.0
    )
    env = SimulationEnvironment(network, config)

    # 添加交通管理者
    manager = TrafficManager(environment=env)
    manager.add_control_node(nodes['center'])
    env.add_agent(manager)

    # 生成初始车辆
    import random
    random.seed(42)

    entry_nodes = [nodes['north_in'], nodes['south_in'], nodes['east_in'], nodes['west_in']]
    exit_nodes = [nodes['north_out'], nodes['south_out'], nodes['east_out'], nodes['west_out']]

    for i in range(8):
        start = random.choice(entry_nodes)
        end = random.choice(exit_nodes)
        vtype = random.choice([VehicleType.CAR, VehicleType.CAR, VehicleType.BUS, VehicleType.TRUCK])
        env.spawn_vehicle(start, end, vtype)

    # 创建可视化器并运行
    print("\n启动可视化...")
    visualizer = SimulationVisualizer(
        env,
        figsize=(12, 10),
        show_labels=True,
        show_stats=True
    )

    try:
        visualizer.run()
    except Exception as e:
        print(f"\n发生错误: {e}")
    finally:
        # 保存最终状态截图
        visualizer.save_screenshot("simulation_final.png")
        print("\n已保存截图到 simulation_final.png")

    # 打印统计
    stats = env.get_statistics()
    print("\n" + "=" * 60)
    print("仿真统计:")
    print(f"  总时间: {env.current_time:.1f}s")
    print(f"  生成车辆: {stats['total_vehicles_spawned']}")
    print(f"  完成车辆: {stats['total_vehicles_completed']}")
    print(f"  完成率: {stats['vehicle_completion_rate']*100:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
