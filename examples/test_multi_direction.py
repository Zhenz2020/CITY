"""Test multi-direction expansion with zone avoidance"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_multi_direction():
    """Test expansion in all directions with blocking zones."""
    # Create initial 2x2 grid
    network = RoadNetwork('test')
    nodes = {}
    for i in range(2):
        for j in range(2):
            n = Node(Vector2D(i*300, j*300), name=f'n{i}_{j}')
            network.add_node(n)
            nodes[(i,j)] = n
    
    # Create initial grid roads
    for i in range(2):
        network.create_edge(nodes[(i,0)], nodes[(i,1)], num_lanes=2, bidirectional=True)
    for j in range(2):
        network.create_edge(nodes[(0,j)], nodes[(1,j)], num_lanes=2, bidirectional=True)
    
    env = SimulationEnvironment(network)
    
    # Create zoning agent and add zones to block all directions
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Add zones at expansion points
    zones_data = [
        # Block left expansion
        Zone(ZoneType.RESIDENTIAL, Vector2D(-150, 0), 200, 200, "BlockLeft"),
        # Block right expansion
        Zone(ZoneType.COMMERCIAL, Vector2D(450, 0), 200, 200, "BlockRight"),
        # Block up (north) expansion
        Zone(ZoneType.PARK, Vector2D(0, -150), 200, 200, "BlockUp"),
        # Block down (south) expansion
        Zone(ZoneType.SCHOOL, Vector2D(0, 450), 200, 200, "BlockDown"),
    ]
    for zone in zones_data:
        zoning_agent.zone_manager.add_zone(zone)
    
    print("Initial state:")
    print(f"  Nodes: {[(n.node_id, int(n.position.x), int(n.position.y)) for n in network.nodes.values()]}")
    print(f"  Zones: {[(z.name, int(z.center.x), int(z.center.y)) for z in zoning_agent.zone_manager.zones.values()]}")
    
    # Create planning agent
    planner = PopulationCityPlanner(
        env,
        use_llm=False,
        population_per_node=2,
        expansion_threshold=0.5,
        max_nodes=20
    )
    env.add_agent(planner)
    
    # Add vehicles
    for i in range(5):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    # Simulate expansions
    for i in range(8):
        print(f"\n--- Expansion {i+1} ---")
        
        # Force expansion
        decision = planner._plan_expansion()
        if not decision:
            print("  No expansion possible")
            break
        
        new_pos = decision['new_node_position']
        print(f"  New node at: ({new_pos['x']}, {new_pos['y']})")
        print(f"  Connect to: {decision.get('connect_to', [])}")
        if decision.get('path_waypoints'):
            print(f"  Path waypoints: {decision['path_waypoints']}")
        
        # Execute
        success = planner.act(decision)
        print(f"  Success: {success}")
        
        if success:
            # Show current state
            xs = [n.position.x for n in network.nodes.values()]
            ys = [n.position.y for n in network.nodes.values()]
            print(f"  Current bounds: X[{min(xs):.0f}, {max(xs):.0f}], Y[{min(ys):.0f}, {max(ys):.0f}]")
            print(f"  Total nodes: {len(network.nodes)}")
            
            # Add more vehicles
            for v in range(2):
                env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    print("\nFinal state:")
    print(f"  Total nodes: {len(network.nodes)}")
    print(f"  Total edges: {len(network.edges)}")
    for node in sorted(network.nodes.values(), key=lambda n: (n.position.x, n.position.y)):
        conns = len(node.outgoing_edges) + len(node.incoming_edges)
        print(f"    {node.node_id}: ({int(node.position.x)}, {int(node.position.y)}) - {conns} connections")


if __name__ == '__main__':
    test_multi_direction()
