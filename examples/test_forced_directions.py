"""Test forced expansion in all four directions"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_direction(forced_direction):
    """Test expansion in a specific direction by manipulating priority."""
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
    
    # Create zoning agent - NO zones
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Create planning agent
    planner = PopulationCityPlanner(env, use_llm=False)
    env.add_agent(planner)
    
    # Add vehicles
    for i in range(4):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    print(f"\n{'='*60}")
    print(f"FORCED DIRECTION: {forced_direction}")
    print(f"{'='*60}")
    
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
    
    # Get candidates
    candidates = planner._find_expansion_candidates_with_zones(nodes_info, 300, 'balanced')
    
    # Filter for desired direction
    dir_candidates = [c for c in candidates if c['direction'] == forced_direction]
    
    if not dir_candidates:
        print(f"No candidates for direction {forced_direction}")
        return
    
    # Pick first candidate
    candidate = dir_candidates[0]
    print(f"Candidate: ({candidate['x']:.0f}, {candidate['y']:.0f})")
    print(f"Anchor: {candidate['anchor']['id']} at ({candidate['anchor']['x']:.0f}, {candidate['anchor']['y']:.0f})")
    
    # Create manual decision
    decision = {
        'action': 'expand_city',
        'new_node_position': {'x': candidate['x'], 'y': candidate['y']},
        'connect_to': [candidate['anchor']['id']],
        'path_waypoints': {},
        'expansion_direction': forced_direction,
        'reason': f'Manual test for {forced_direction}',
        'is_llm': False
    }
    
    # Execute
    success = planner.act(decision)
    print(f"Success: {success}")
    
    if success:
        print(f"\nAfter expansion:")
        print(f"  Total nodes: {len(network.nodes)}")
        for node in sorted(network.nodes.values(), key=lambda n: (n.position.x, n.position.y)):
            print(f"    {node.node_id}: ({int(node.position.x)}, {int(node.position.y)})")
        
        # Find new node and show connections
        new_node = None
        for node in network.nodes.values():
            if abs(node.position.x - candidate['x']) < 1 and abs(node.position.y - candidate['y']) < 1:
                new_node = node
                break
        
        if new_node:
            print(f"\n  New node {new_node.node_id} connections:")
            for edge in new_node.outgoing_edges:
                print(f"    -> {edge.to_node.node_id} ({int(edge.to_node.position.x)}, {int(edge.to_node.position.y)})")
            for edge in new_node.incoming_edges:
                print(f"    <- {edge.from_node.node_id} ({int(edge.from_node.position.x)}, {int(edge.from_node.position.y)})")


def test_all_directions():
    """Test all four directions."""
    for direction in ['left', 'right', 'up', 'down']:
        test_direction(direction)
    
    print(f"\n{'='*60}")
    print("ALL DIRECTION TESTS COMPLETED")
    print(f"{'='*60}")


if __name__ == '__main__':
    test_all_directions()
