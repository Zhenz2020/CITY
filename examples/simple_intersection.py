"""
简单交叉口仿真示例。

演示一个包含四个方向的简单交叉口，车辆从各方向进入并通过交叉口。
"""

import sys
sys.path.insert(0, '..')

from city.environment.road_network import (
    RoadNetwork, Node, Edge, TrafficLight, TrafficLightState
)
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.agents.vehicle import Vehicle, VehicleType
from city.agents.traffic_manager import TrafficManager
from city.utils.vector import Vector2D


def create_simple_intersection() -> tuple[RoadNetwork, dict[str, Node]]:
    """创建一个简单的十字路口，返回网络和节点字典。"""
    network = RoadNetwork("simple_intersection")

    # 创建四个方向的入口/出口节点
    north_in = Node(position=Vector2D(0, 200), name="north_in")
    north_out = Node(position=Vector2D(0, -200), name="north_out")
    south_in = Node(position=Vector2D(0, -200), name="south_in")
    south_out = Node(position=Vector2D(0, 200), name="south_out")
    east_in = Node(position=Vector2D(200, 0), name="east_in")
    east_out = Node(position=Vector2D(-200, 0), name="east_out")
    west_in = Node(position=Vector2D(-200, 0), name="west_in")
    west_out = Node(position=Vector2D(200, 0), name="west_out")
    center = Node(position=Vector2D(0, 0), name="center", is_intersection=True)

    # 添加节点到网络
    for node in [north_in, north_out, south_in, south_out,
                 east_in, east_out, west_in, west_out, center]:
        network.add_node(node)

    # 创建路段
    network.create_edge(north_in, center, num_lanes=2)
    network.create_edge(south_in, center, num_lanes=2)
    network.create_edge(east_in, center, num_lanes=2)
    network.create_edge(west_in, center, num_lanes=2)
    network.create_edge(center, north_out, num_lanes=2)
    network.create_edge(center, south_out, num_lanes=2)
    network.create_edge(center, east_out, num_lanes=2)
    network.create_edge(center, west_out, num_lanes=2)

    # 为交叉口添加信号灯
    center.traffic_light = TrafficLight(
        node=center,
        cycle_time=60.0,
        green_duration=30.0,
        yellow_duration=5.0
    )

    # 返回网络和节点字典
    nodes = {
        'north_in': north_in, 'north_out': north_out,
        'south_in': south_in, 'south_out': south_out,
        'east_in': east_in, 'east_out': east_out,
        'west_in': west_in, 'west_out': west_out,
        'center': center
    }

    return network, nodes


def run_simple_simulation():
    """运行简单仿真。"""
    print("=" * 60)
    print("简单交叉口交通仿真")
    print("=" * 60)

    # 创建道路网络
    network, nodes = create_simple_intersection()
    print(f"\n创建道路网络: {network}")
    print(f"  - 节点数: {len(network.nodes)}")
    print(f"  - 路段数: {len(network.edges)}")

    # 创建仿真环境
    config = SimulationConfig(
        time_step=0.5,
        max_simulation_time=300.0,  # 5分钟
        real_time_factor=0.0  # 尽可能快
    )
    env = SimulationEnvironment(network, config)

    # 添加交通管理者
    manager = TrafficManager(environment=env)
    manager.add_control_node(nodes['center'])
    env.add_agent(manager)
    print(f"\n添加交通管理者: {manager}")

    # 生成一些车辆
    print("\n生成车辆...")
    entry_nodes = [nodes['north_in'], nodes['south_in'], nodes['east_in'], nodes['west_in']]
    exit_nodes = [nodes['north_out'], nodes['south_out'], nodes['east_out'], nodes['west_out']]

    import random
    random.seed(42)

    # 生成10辆车
    for i in range(10):
        start = random.choice([n for n in entry_nodes if n is not None])
        end = random.choice([n for n in exit_nodes if n is not None])

        vehicle_type = random.choice([
            VehicleType.CAR,
            VehicleType.CAR,
            VehicleType.CAR,
            VehicleType.BUS,
            VehicleType.TRUCK
        ])

        vehicle = env.spawn_vehicle(start, end, vehicle_type)
        if vehicle:
            print(f"  - 生成车辆: {vehicle.agent_id} ({vehicle.vehicle_type.name}) "
                  f"从 {start.name} 到 {end.name}")

    # 运行仿真
    print("\n开始仿真...")
    print("-" * 60)

    # 逐步运行并打印状态
    env.start()
    report_interval = 60.0  # 每60秒报告一次
    next_report = report_interval

    while env.is_running:
        env.step()

        # 定期报告
        if env.current_time >= next_report:
            stats = env.get_statistics()
            print(f"\n[时间: {env.current_time:.1f}s] 状态报告:")
            print(f"  - 活跃车辆: {stats['active_vehicles']}")
            print(f"  - 已完成车辆: {stats['total_vehicles_completed']}")
            print(f"  - 完成率: {stats['vehicle_completion_rate']*100:.1f}%")

            # 交通管理报告
            traffic_report = manager.get_traffic_report()
            print(f"  - 系统状态: {traffic_report['system_status']}")
            print(f"  - 活跃事件: {traffic_report['active_incidents']}")

            next_report += report_interval

        # 定期生成新车
        if int(env.current_time) % 30 == 0 and env.current_time > 0:
            if len(env.vehicles) < 5:  # 保持一定车辆数
                start = random.choice(entry_nodes)
                end = random.choice(exit_nodes)
                env.spawn_vehicle(start, end)

    print("\n" + "=" * 60)
    print("仿真结束")
    print("=" * 60)

    # 最终统计
    final_stats = env.get_statistics()
    print(f"\n最终统计:")
    print(f"  - 总仿真时间: {env.current_time:.1f} 秒")
    print(f"  - 生成车辆总数: {final_stats['total_vehicles_spawned']}")
    print(f"  - 完成车辆数: {final_stats['total_vehicles_completed']}")
    print(f"  - 完成率: {final_stats['vehicle_completion_rate']*100:.1f}%")


if __name__ == "__main__":
    run_simple_simulation()
