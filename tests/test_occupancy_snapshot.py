from city.agents.vehicle import Vehicle
from city.environment.road_network import RoadNetwork, Node
from city.traffic_micro.occupancy import TrafficSnapshot
from city.utils.vector import Vector2D


def test_snapshot_returns_leader_and_follower():
    network = RoadNetwork()
    start = Node(position=Vector2D(0, 0))
    end = Node(position=Vector2D(100, 0))
    network.add_node(start)
    network.add_node(end)
    edge = network.create_edge(start, end, num_lanes=2, bidirectional=False)

    rear = Vehicle()
    middle = Vehicle()
    leader = Vehicle()

    rear.spawn_on_edge(edge, lane_index=0)
    middle.spawn_on_edge(edge, lane_index=0)
    leader.spawn_on_edge(edge, lane_index=0)

    rear.distance_on_edge = 10
    middle.distance_on_edge = 30
    leader.distance_on_edge = 60

    snapshot = TrafficSnapshot.build(network)
    leader_ref, leader_gap = snapshot.get_leader(middle)
    follower_ref, follower_gap = snapshot.get_follower(middle)

    assert leader_ref is leader
    assert follower_ref is rear
    assert leader_gap is not None and leader_gap > 0
    assert follower_gap is not None and follower_gap > 0
