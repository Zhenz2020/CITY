"""
道路网络模块测试。
"""

import sys
sys.path.insert(0, '..')

from city.environment.road_network import (
    RoadNetwork, Node, Edge, TrafficLight, TrafficLightState, LaneType
)
from city.utils.vector import Vector2D


def test_node_creation():
    """测试节点创建。"""
    node = Node(position=Vector2D(0, 0), name="test_node")
    assert node.position.x == 0
    assert node.position.y == 0
    assert node.name == "test_node"
    assert not node.is_intersection
    print("[PASS] 节点创建测试通过")


def test_traffic_light():
    """测试交通信号灯。"""
    node = Node(position=Vector2D(0, 0), is_intersection=True)
    light = TrafficLight(node, cycle_time=60, green_duration=30, yellow_duration=5)

    assert light.state == TrafficLightState.RED
    assert not light.can_pass()

    # 模拟时间推进
    light.update(35)  # 红灯时间后变绿灯
    assert light.state == TrafficLightState.GREEN
    assert light.can_pass()

    print("[PASS] 交通信号灯测试通过")


def test_edge_creation():
    """测试路段创建。"""
    network = RoadNetwork()

    n1 = Node(position=Vector2D(0, 0))
    n2 = Node(position=Vector2D(100, 0))
    network.add_node(n1)
    network.add_node(n2)

    edge = network.create_edge(n1, n2, num_lanes=2)

    assert isinstance(edge, Edge) or isinstance(edge, tuple)
    if isinstance(edge, Edge):
        assert len(edge.lanes) == 2
        assert edge.length == 100.0

    print("[PASS] 路段创建测试通过")


def test_shortest_path():
    """测试最短路径算法。"""
    network = RoadNetwork()

    # 创建简单网络: A -> B -> C
    a = Node(position=Vector2D(0, 0), name="A")
    b = Node(position=Vector2D(100, 0), name="B")
    c = Node(position=Vector2D(200, 0), name="C")

    for node in [a, b, c]:
        network.add_node(node)

    network.create_edge(a, b, num_lanes=1, bidirectional=False)
    network.create_edge(b, c, num_lanes=1, bidirectional=False)

    # 测试最短路径
    path = network.find_shortest_path(a, c)
    assert path is not None
    assert len(path) == 3
    assert path[0] == a
    assert path[1] == b
    assert path[2] == c

    print("[PASS] 最短路径测试通过")


def test_network_statistics():
    """测试网络统计。"""
    network = RoadNetwork("test_network")

    # 添加节点
    for i in range(4):
        node = Node(position=Vector2D(i * 100, 0))
        network.add_node(node)

    # 创建连接
    nodes = list(network.nodes.values())
    for i in range(len(nodes) - 1):
        network.create_edge(nodes[i], nodes[i + 1], num_lanes=2)

    assert len(network.nodes) == 4
    assert len(network.edges) == 6  # 双向连接

    print("[PASS] 网络统计测试通过")


def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("道路网络模块测试")
    print("=" * 50)

    test_node_creation()
    test_traffic_light()
    test_edge_creation()
    test_shortest_path()
    test_network_statistics()

    print("=" * 50)
    print("所有测试通过!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
