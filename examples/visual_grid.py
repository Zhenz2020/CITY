"""
可视化网格城市仿真。

显示一个3x3网格城市的交通流。
"""

import sys
sys.path.insert(0, '..')

from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.visualization.renderer import SimulationVisualizer
from city.agents.vehicle import VehicleType
from city.agents.traffic_manager import TrafficManager
from city.utils.vector import Vector2D


def create_grid_network(size: int = 3, spacing: float = 200.0):
    """创建网格网络。"""
    network = RoadNetwork(f"grid_{size}x{size}")
    nodes = {}

    # 创建节点
    for i in range(size):
        for j in range(size):
            is_intersection = (0 < i < size - 1) and (0 < j < size - 1)
            node = Node(
                position=Vector2D(i * spacing, j * spacing),
                name=f"node_{i}_{j}",
                is_intersection=is_intersection
            )
            nodes[(i, j)] = node
            network.add_node(node)

    # 水平路段
    for i in range(size):
        for j in range(size - 1):
            network.create_edge(nodes[(i, j)], nodes[(i, j + 1)], num_lanes=2)

    # 垂直路段
    for i in range(size - 1):
        for j in range(size):
            network.create_edge(nodes[(i, j)], nodes[(i + 1, j)], num_lanes=2)

    # 信号灯
    for (i, j), node in nodes.items():
        if node.is_intersection:
            node.traffic_light = TrafficLight(
                node, cycle_time=60, green_duration=25, yellow_duration=5
            )

    return network, nodes


def main():
    """主函数。"""
    print("=" * 60)
    print("可视化网格城市仿真")
    print("=" * 60)

    # 创建网络
    network, nodes = create_grid_network(size=3, spacing=200)
    print(f"创建网格: {len(network.nodes)} 节点, {len(network.edges)} 路段")

    # 环境配置
    config = SimulationConfig(
        time_step=0.5,
        max_simulation_time=600.0,
        real_time_factor=1.0
    )
    env = SimulationEnvironment(network, config)

    # 交通管理者
    manager = TrafficManager(environment=env)
    for node in network.nodes.values():
        if node.is_intersection:
            manager.add_control_node(node)
    env.add_agent(manager)
    print(f"交通管理者控制 {len(manager.control_area)} 个交叉口")

    # 生成车辆
    import random
    random.seed(42)

    corners = [nodes[(0, 0)], nodes[(0, 2)], nodes[(2, 0)], nodes[(2, 2)]]

    for i in range(12):
        start = random.choice(corners)
        end = random.choice([c for c in corners if c != start])
        vtype = random.choice([VehicleType.CAR, VehicleType.BUS, VehicleType.TRUCK])
        env.spawn_vehicle(start, end, vtype)

    # 运行可视化仿真
    print("\n启动可视化... (按 Ctrl+C 停止)")
    visualizer = SimulationVisualizer(env, figsize=(14, 12))

    step_count = 0
    env.start()

    try:
        while env.is_running:
            if not visualizer.step():
                break

            step_count += 1

            # 每60步（约30秒）生成新车
            if step_count % 60 == 0 and len(env.vehicles) < 15:
                start = random.choice(corners)
                end = random.choice([c for c in corners if c != start])
                env.spawn_vehicle(start, end)

    except KeyboardInterrupt:
        print("\n用户中断仿真")
    finally:
        visualizer.save_screenshot("grid_simulation.png")
        print("已保存截图到 grid_simulation.png")
        visualizer.visualizer.close()

    # 统计
    stats = env.get_statistics()
    print("\n仿真统计:")
    print(f"  总时间: {env.current_time:.1f}s")
    print(f"  生成车辆: {stats['total_vehicles_spawned']}")
    print(f"  完成: {stats['total_vehicles_completed']}")
    print(f"  完成率: {stats['vehicle_completion_rate']*100:.1f}%")


if __name__ == "__main__":
    main()
