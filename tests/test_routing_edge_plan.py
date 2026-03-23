from city.environment.road_network import RoadNetwork, Node
from city.traffic_micro.routing import RoutingEngine
from city.utils.vector import Vector2D


def test_routing_engine_returns_edge_plan():
    network = RoadNetwork()
    a = Node(position=Vector2D(0, 0))
    b = Node(position=Vector2D(100, 0))
    c = Node(position=Vector2D(200, 0))
    for node in (a, b, c):
        network.add_node(node)

    edge_ab = network.create_edge(a, b, num_lanes=2, bidirectional=False)
    edge_bc = network.create_edge(b, c, num_lanes=2, bidirectional=False)

    route_plan = RoutingEngine().plan_route(network, a, c)

    assert route_plan is not None
    assert route_plan.nodes == [a.node_id, b.node_id, c.node_id]
    assert route_plan.edges == [edge_ab.edge_id, edge_bc.edge_id]
    assert edge_ab.edge_id in route_plan.desired_lane_indices_by_edge
