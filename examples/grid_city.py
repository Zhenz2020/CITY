"""
网格城市仿真示例。

创建一个简化的网格状城市道路网络，模拟多辆车的行驶。
"""

import sys
sys.path.insert(0, '..')

from city.environment.road_network import (
    RoadNetwork, Node, TrafficLight
)
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.agents.vehicle import Vehicle, VehicleType
from city.agents.pedestrian import Pedestrian
from city.agents.traffic_manager import TrafficManager
from city.agents.traffic_planner import TrafficPlanner
from city.utils.vector import Vector2D


def create_grid_network(size: int = 3, spacing: float = 200.0) -> RoadNetwork:
    """
    创建网格状道路网络。

    Args:
        size: 网格大小（size x size）
        spacing: 节点间距

    Returns:
        道路网络
    """
    network = RoadNetwork(f"grid_{size}x{size}")

    # 创建节点
    nodes: dict[tuple[int, int], Node] = {}
    for i in range(size):
        for j in range(size):
            # 判断是否为交叉口（非边缘节点）
            is_intersection = (0 < i < size - 1) and (0 < j < size - 1)

            node = Node(
                position=Vector2D(i * spacing, j * spacing),
                name=f"node_{i}_{j}",
                is_intersection=is_intersection
            )
            nodes[(i, j)] = node
            network.add_node(node)

    # 创建水平路段
    for i in range(size):
        for j in range(size - 1):
            from_node = nodes[(i, j)]
            to_node = nodes[(i, j + 1)]
            network.create_edge(from_node, to_node, num_lanes=2)

    # 创建垂直路段
    for i in range(size - 1):
        for j in range(size):
            from_node = nodes[(i, j)]
            to_node = nodes[(i + 1, j)]
            network.create_edge(from_node, to_node, num_lanes=2)

    # 为交叉口添加信号灯
    for (i, j), node in nodes.items():
        if node.is_intersection:
            node.traffic_light = TrafficLight(
                node=node,
                cycle_time=60.0,
                green_duration=25.0,
                yellow_duration=5.0
            )

    return network


def run_grid_simulation():
    """运行网格城市仿真。"""
    print("=" * 60)
    print("网格城市交通仿真")
    print("=" * 60)

    # 创建3x3网格
    network = create_grid_network(size=3, spacing=200.0)
    print(f"\n创建道路网络: {network}")

    # 创建仿真环境
    config = SimulationConfig(
        time_step=0.5,
        max_simulation_time=600.0,  # 10分钟
        real_time_factor=0.0
    )
    env = SimulationEnvironment(network, config)

    # 添加交通管理者
    manager = TrafficManager(environment=env)
    for node in network.nodes.values():
        if node.is_intersection:
            manager.add_control_node(node)
    env.add_agent(manager)
    print(f"\n添加交通管理者: {manager}")

    # 添加交通规划者
    planner = TrafficPlanner(environment=env, planning_horizon=30.0)
    env.add_agent(planner)
    print(f"添加交通规划者: {planner}")

    # 获取所有节点
    all_nodes = list(network.nodes.values())
    corner_nodes = [
        network.get_node("node_0_0"),
        network.get_node("node_0_2"),
        network.get_node("node_2_0"),
        network.get_node("node_2_2")
    ]
    corner_nodes = [n for n in corner_nodes if n is not None]

    print(f"\n网络包含 {len(all_nodes)} 个节点")
    print(f"  - 交叉口: {sum(1 for n in all_nodes if n.is_intersection)}")
    print(f"  - 路段: {len(network.edges)}")

    # 生成车辆
    print("\n生成初始车辆...")
    import random
    random.seed(42)

    for i in range(8):
        start = random.choice(corner_nodes)
        end = random.choice([n for n in corner_nodes if n != start])

        vehicle_type = random.choice([
            VehicleType.CAR,
            VehicleType.CAR,
            VehicleType.BUS,
            VehicleType.TRUCK
        ])

        vehicle = env.spawn_vehicle(start, end, vehicle_type)
        if vehicle:
            print(f"  - {vehicle.agent_id}: {vehicle.vehicle_type.name} "
                  f"从 {start.name} 到 {end.name}")

    # 生成行人
    print("\n生成行人...")
    for i in range(4):
        start_node = random.choice(corner_nodes)
        end_node = random.choice([n for n in corner_nodes if n != start_node])

        # 在节点附近生成行人
        start_pos = start_node.position + Vector2D(random.uniform(-20, 20), random.uniform(-20, 20))
        end_pos = end_node.position + Vector2D(random.uniform(-20, 20), random.uniform(-20, 20))

        pedestrian = env.spawn_pedestrian(start_pos, end_pos)
        if pedestrian:
            print(f"  - {pedestrian.agent_id}: 从 ({start_pos.x:.1f}, {start_pos.y:.1f}) "
                  f"到 ({end_pos.x:.1f}, {end_pos.y:.1f})")

    # 运行仿真
    print("\n开始仿真...")
    print("-" * 60)

    env.start()
    report_interval = 120.0  # 每2分钟报告一次
    next_report = report_interval

    while env.is_running:
        env.step()

        # 定期报告
        if env.current_time >= next_report:
            stats = env.get_statistics()
            print(f"\n[时间: {env.current_time:.1f}s] 状态报告:")
            print(f"  - 活跃车辆: {stats['active_vehicles']}")
            print(f"  - 活跃行人: {stats['active_pedestrians']}")
            print(f"  - 已完成车辆: {stats['total_vehicles_completed']}")
            print(f"  - 已完成行人: {stats['total_pedestrians_completed']}")

            # 交通管理报告
            traffic_report = manager.get_traffic_report()
            print(f"  - 交通状况: {traffic_report['system_status']}")
            print(f"  - 活跃事件: {traffic_report['active_incidents']}")

            # 规划报告
            if int(env.current_time) % 240 == 0:  # 每4分钟生成规划报告
                planning_report = planner.get_planning_report()
                print(f"  - 规划提案: {planning_report['active_proposals']}")
                print(f"  - 识别瓶颈: {planning_report['bottlenecks_identified']}")

            next_report += report_interval

        # 动态生成新车辆
        if int(env.current_time) % 60 == 0 and env.current_time > 0:
            if len(env.vehicles) < 10:
                start = random.choice(corner_nodes)
                end = random.choice([n for n in corner_nodes if n != start])
                vehicle = env.spawn_vehicle(start, end)
                if vehicle:
                    print(f"  [新车辆] {vehicle.agent_id} 进入系统")

    print("\n" + "=" * 60)
    print("仿真结束")
    print("=" * 60)

    # 最终统计
    final_stats = env.get_statistics()
    print(f"\n最终统计:")
    print(f"  - 总仿真时间: {env.current_time:.1f} 秒 ({env.current_time/60:.1f} 分钟)")
    print(f"  - 仿真步数: {env.step_count}")
    print(f"  - 生成车辆总数: {final_stats['total_vehicles_spawned']}")
    print(f"  - 完成车辆数: {final_stats['total_vehicles_completed']}")
    print(f"  - 车辆完成率: {final_stats['vehicle_completion_rate']*100:.1f}%")
    print(f"  - 生成行人数: {final_stats['total_pedestrians_spawned']}")
    print(f"  - 完成行人数: {final_stats['total_pedestrians_completed']}")

    # 规划提案
    print(f"\n规划提案:")
    for proposal_id, proposal in planner.proposals.items():
        print(f"  - {proposal_id}: {proposal.description}")
        evaluation = planner.evaluate_proposal(proposal_id)
        print(f"    评估: {evaluation['recommendation']} (优先级: {evaluation['priority']})")


if __name__ == "__main__":
    run_grid_simulation()
