"""
智能体模块测试。
"""

import sys
sys.path.insert(0, '..')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.agents.vehicle import Vehicle, VehicleType, VehicleAction
from city.agents.pedestrian import Pedestrian, PedestrianState
from city.agents.traffic_manager import TrafficManager, TrafficIncidentType
from city.utils.vector import Vector2D


def test_vehicle_creation():
    """测试车辆创建。"""
    vehicle = Vehicle(vehicle_type=VehicleType.CAR)

    assert vehicle.vehicle_type == VehicleType.CAR
    assert vehicle.max_speed > 0
    assert vehicle.velocity == 0
    assert vehicle.state.name == 'IDLE'

    print("[PASS] 车辆创建测试通过")


def test_vehicle_types():
    """测试不同车辆类型。"""
    car = Vehicle(vehicle_type=VehicleType.CAR)
    bus = Vehicle(vehicle_type=VehicleType.BUS)
    truck = Vehicle(vehicle_type=VehicleType.TRUCK)

    assert car.max_speed > bus.max_speed  # 汽车比公交车快
    assert bus.length > car.length  # 公交车比汽车长

    print("[PASS] 车辆类型测试通过")


def test_pedestrian_creation():
    """测试行人创建。"""
    start = Vector2D(0, 0)
    end = Vector2D(100, 0)
    pedestrian = Pedestrian(start_position=start, end_position=end)

    assert pedestrian.position == start
    assert pedestrian.target_position == end
    assert pedestrian.max_speed < 2.0  # 步行速度较慢

    print("[PASS] 行人创建测试通过")


def test_traffic_manager():
    """测试交通管理者。"""
    manager = TrafficManager()

    assert manager.agent_type.name == 'TRAFFIC_MANAGER'
    assert len(manager.control_area) == 0
    assert len(manager.incidents) == 0

    # 添加控制节点
    node = Node(position=Vector2D(0, 0), is_intersection=True)
    manager.add_control_node(node)
    assert len(manager.control_area) == 1

    print("[PASS] 交通管理者测试通过")


def test_vehicle_route_planning():
    """测试车辆路线规划。"""
    # 创建简单网络
    network = RoadNetwork()
    n1 = Node(position=Vector2D(0, 0))
    n2 = Node(position=Vector2D(100, 0))
    n3 = Node(position=Vector2D(200, 0))

    for n in [n1, n2, n3]:
        network.add_node(n)

    network.create_edge(n1, n2, bidirectional=False)
    network.create_edge(n2, n3, bidirectional=False)

    # 创建环境
    env = SimulationEnvironment(network)

    # 创建车辆并规划路线
    vehicle = Vehicle(environment=env)
    success = vehicle.plan_route(n1, n3)

    assert success
    assert len(vehicle.route) == 3
    assert vehicle.route[0] == n1
    assert vehicle.route[2] == n3

    print("[PASS] 车辆路线规划测试通过")


def test_vehicle_decision():
    """测试车辆决策。"""
    vehicle = Vehicle(vehicle_type=VehicleType.CAR)
    vehicle.activate()

    # 测试感知
    perception = vehicle.perceive()
    assert 'position' in perception
    assert 'velocity' in perception

    # 测试决策
    action = vehicle.decide()
    assert isinstance(action, VehicleAction)

    print("[PASS] 车辆决策测试通过")


def test_traffic_incident():
    """测试交通事件报告。"""
    env = SimulationEnvironment()
    manager = TrafficManager(environment=env)
    env.add_agent(manager)

    node = Node(position=Vector2D(0, 0))
    incident = manager.report_incident(
        incident_type=TrafficIncidentType.ACCIDENT,
        location=node,
        severity=8,
        duration=3600,
        description="测试事故"
    )

    assert incident.incident_type == TrafficIncidentType.ACCIDENT
    assert incident.severity == 8
    assert len(manager.incidents) == 1

    print("[PASS] 交通事件测试通过")


def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("智能体模块测试")
    print("=" * 50)

    test_vehicle_creation()
    test_vehicle_types()
    test_pedestrian_creation()
    test_traffic_manager()
    test_vehicle_route_planning()
    test_vehicle_decision()
    test_traffic_incident()

    print("=" * 50)
    print("所有测试通过!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
