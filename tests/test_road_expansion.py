from city.agents.planning_agent import PlanningAgent
from city.agents.vehicle import Vehicle
from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.utils.vector import Vector2D


def _build_bidirectional_edge_environment() -> tuple[SimulationEnvironment, object, object]:
    network = RoadNetwork()
    a = Node(position=Vector2D(0, 0))
    b = Node(position=Vector2D(100, 0))
    network.add_node(a)
    network.add_node(b)
    edge_ab, edge_ba = network.create_edge(a, b, num_lanes=2, bidirectional=True)
    env = SimulationEnvironment(network)
    return env, edge_ab, edge_ba


def test_expand_edge_lanes_rebuilds_bidirectional_capacity():
    env, edge_ab, edge_ba = _build_bidirectional_edge_environment()

    result = env.expand_road_capacity_dynamically(edge_ab, target_num_lanes=4, sync_reverse=True)

    assert result is not None
    assert len(edge_ab.lanes) == 4
    assert len(edge_ba.lanes) == 4
    assert edge_ab.lane_connections


def test_planning_agent_can_choose_road_expansion():
    env, edge_ab, _ = _build_bidirectional_edge_environment()

    for idx in range(8):
        vehicle = Vehicle(environment=env)
        vehicle.spawn_on_edge(edge_ab, lane_index=idx % len(edge_ab.lanes))
        vehicle.distance_on_edge = 5.0 + idx * 6.0
        vehicle.velocity = 1.0
        env.add_agent(vehicle)

    planner = PlanningAgent(environment=env, use_llm=False)
    env.current_time = planner.expansion_cooldown + 1.0
    decision = planner.decide()

    assert decision is not None
    assert decision["action"] == "expand_road_capacity"
    assert decision["edge_id"] == edge_ab.edge_id

    success = planner.act(decision)
    assert success
    assert len(edge_ab.lanes) == 4
