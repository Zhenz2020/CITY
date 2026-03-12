"""Test full expansion process"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_full_expansion():
    """Test complete expansion process."""
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
    
    # Create zoning agent and add a zone
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Add a residential zone in the center
    zone = Zone(
        zone_type=ZoneType.RESIDENTIAL,
        center=Vector2D(150, 150),
        width=200,
        height=200,
        name="TestZone"
    )
    zoning_agent.zone_manager.add_zone(zone)
    
    print("Initial state:")
    print(f"  Nodes: {[(n.node_id, n.position.x, n.position.y) for n in network.nodes.values()]}")
    print(f"  Zone: ({zone.center.x}, {zone.center.y}) size {zone.width}x{zone.height}")
    
    # Create planning agent
    planner = PopulationCityPlanner(
        env,
        use_llm=False,
        population_per_node=2,
        expansion_threshold=0.5,
        max_nodes=10
    )
    env.add_agent(planner)
    
    # Add vehicles to trigger expansion
    for i in range(5):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    print(f"\nAdded {len(env.vehicles)} vehicles")
    
    # Simulate multiple expansions
    for i in range(5):
        print(f"\n--- Expansion {i+1} ---")
        
        stats = planner.get_city_stats()
        print(f"  Density: {stats['density']:.2f} (threshold: {stats['expansion_threshold']})")
        print(f"  Should expand: {stats['should_expand']}")
        
        # Get current nodes info
        nodes_info = []
        for node in network.nodes.values():
            load = len(node.incoming_edges) + len(node.outgoing_edges)
            nodes_info.append({
                'id': node.node_id,
                'name': node.name,
                'x': node.position.x,
                'y': node.position.y,
                'load': load
            })
        
        min_x = min(n['x'] for n in nodes_info)
        max_x = max(n['x'] for n in nodes_info)
        min_y = min(n['y'] for n in nodes_info)
        max_y = max(n['y'] for n in nodes_info)
        
        print(f"  Current bounds: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
        print(f"  Current nodes: {len(nodes_info)}")
        
        # Get expansion decision
        decision = planner.decide()
        if not decision:
            print("  No expansion decision - forcing expansion")
            # Force expansion by calling _plan_expansion directly
            decision = planner._plan_expansion()
        
        if not decision:
            print("  Still no expansion decision - breaking")
            break
            
        new_pos = decision['new_node_position']
        print(f"  Decision: new node at ({new_pos['x']}, {new_pos['y']})")
        print(f"  Connect to: {decision.get('connect_to', [])}")
        if decision.get('path_waypoints'):
            print(f"  Path waypoints: {decision['path_waypoints']}")
        
        # Execute expansion
        success = planner.act(decision)
        print(f"  Success: {success}")
        
        if success:
            print(f"  After expansion: {len(network.nodes)} nodes")
            # Show all node positions
            for node in network.nodes.values():
                print(f"    {node.node_id}: ({node.position.x}, {node.position.y})")
            
            # Add more vehicles for next expansion
            for v in range(3):
                env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    print("\nFinal state:")
    print(f"  Total nodes: {len(network.nodes)}")
    print(f"  Total edges: {len(network.edges)}")
    for node in network.nodes.values():
        print(f"    {node.node_id}: ({node.position.x}, {node.position.y})")


if __name__ == '__main__':
    test_full_expansion()
