"""Test detour path around zones with proper decision"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_detour_path():
    """Test that roads detour around zones instead of going through them."""
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
    
    # Create zoning agent and add a zone that blocks leftward expansion
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Place zone at (-150, 0) to block path from (-300, 0) to (0, 0)
    zone = Zone(
        zone_type=ZoneType.RESIDENTIAL,
        center=Vector2D(-150, 0),
        width=200,
        height=200,
        name="BlockingZone"
    )
    zoning_agent.zone_manager.add_zone(zone)
    
    print("Initial state:")
    print(f"  Nodes: {[(n.node_id, int(n.position.x), int(n.position.y)) for n in network.nodes.values()]}")
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
    
    # Use _rule_plan_expansion to generate proper decision with path_waypoints
    print("\n--- Calling _rule_plan_expansion ---")
    
    # Build nodes_info
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
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    aspect_ratio = (max_x - min_x) / (max_y - min_y) if max_y > min_y else 1.0
    preferred_direction = 'balanced'
    
    print(f"  Bounds: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
    print(f"  Aspect ratio: {aspect_ratio:.2f}, preferred: {preferred_direction}")
    
    decision = planner._rule_plan_expansion(
        nodes_info, min_x, max_x, min_y, max_y,
        center_x, center_y, aspect_ratio, preferred_direction
    )
    
    if not decision:
        print("  No decision generated!")
        return
    
    new_pos = decision['new_node_position']
    print(f"\n  Decision generated:")
    print(f"    New node at: ({new_pos['x']}, {new_pos['y']})")
    print(f"    Connect to: {decision.get('connect_to', [])}")
    print(f"    Path waypoints: {decision.get('path_waypoints', {})}")
    
    # Execute expansion
    print("\n--- Executing expansion ---")
    success = planner.act(decision)
    print(f"  Success: {success}")
    
    if success:
        print(f"\n  After expansion:")
        print(f"    Total nodes: {len(network.nodes)}")
        for node in network.nodes.values():
            print(f"    {node.node_id}: ({int(node.position.x)}, {int(node.position.y)})")
        
        # Find the new node
        new_node = None
        for node in network.nodes.values():
            if abs(node.position.x - new_pos['x']) < 1 and abs(node.position.y - new_pos['y']) < 1:
                new_node = node
                break
        
        if new_node:
            print(f"\n  New node {new_node.node_id} connections:")
            for edge in new_node.outgoing_edges:
                print(f"    -> {edge.to_node.node_id} at ({int(edge.to_node.position.x)}, {int(edge.to_node.position.y)})")
            for edge in new_node.incoming_edges:
                print(f"    <- {edge.from_node.node_id} at ({int(edge.from_node.position.x)}, {int(edge.from_node.position.y)})")
            
            # Check if path goes through intermediate nodes (detour)
            intermediate_nodes = []
            for edge in new_node.outgoing_edges:
                if edge.to_node.node_id not in ['node_1', 'node_2', 'node_3', 'node_4']:
                    intermediate_nodes.append(edge.to_node)
            for edge in new_node.incoming_edges:
                if edge.from_node.node_id not in ['node_1', 'node_2', 'node_3', 'node_4']:
                    intermediate_nodes.append(edge.from_node)
            
            if intermediate_nodes:
                print(f"\n  Intermediate nodes (detour path):")
                for node in intermediate_nodes:
                    print(f"    {node.node_id}: ({int(node.position.x)}, {int(node.position.y)})")
            else:
                print(f"\n  No intermediate nodes - direct connection!")


if __name__ == '__main__':
    test_detour_path()
