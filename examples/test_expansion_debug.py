"""Detailed debug of expansion process"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def debug_expansion():
    """Debug the expansion process step by step."""
    # Create initial 2x2 grid at (0,0), (300,0), (0,300), (300,300)
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
    
    print("=" * 60)
    print("INITIAL STATE")
    print("=" * 60)
    print(f"Nodes: {[(n.node_id, int(n.position.x), int(n.position.y)) for n in network.nodes.values()]}")
    print(f"Edges: {len(network.edges)}")
    
    # Create zoning agent
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Add a zone that blocks left expansion at (-150, 0)
    zone = Zone(
        ZoneType.RESIDENTIAL,
        Vector2D(-150, 0),
        200, 200,
        "BlockLeft"
    )
    zoning_agent.zone_manager.add_zone(zone)
    print(f"\nZone added: {zone.name} at ({zone.center.x}, {zone.center.y})")
    print(f"Zone bounds: X[{zone.center.x-zone.width/2}, {zone.center.x+zone.width/2}], Y[{zone.center.y-zone.height/2}, {zone.center.y+zone.height/2}]")
    
    # Create planning agent
    planner = PopulationCityPlanner(env, use_llm=False)
    env.add_agent(planner)
    
    # Add vehicles to trigger expansion
    for i in range(5):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    # Simulate 3 expansions
    for exp_idx in range(3):
        print("\n" + "=" * 60)
        print(f"EXPANSION {exp_idx + 1}")
        print("=" * 60)
        
        # Get current state
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
        
        print(f"Current bounds: X[{min_x:.0f}, {max_x:.0f}], Y[{min_y:.0f}, {max_y:.0f}]")
        print(f"Current nodes: {len(nodes_info)}")
        
        # Get candidates
        candidates = planner._find_expansion_candidates_with_zones(nodes_info, 300, 'balanced')
        print(f"\nCandidates found: {len(candidates)}")
        for i, c in enumerate(candidates[:6]):  # Show first 6
            print(f"  {i+1}. ({c['x']:.0f}, {c['y']:.0f}) dir={c['direction']} anchor={c['anchor']['id']} priority={c['priority']}")
        
        # Get decision
        decision = planner._plan_expansion()
        if not decision:
            print("No expansion decision!")
            break
        
        new_pos = decision['new_node_position']
        print(f"\nDecision:")
        print(f"  New node at: ({new_pos['x']:.0f}, {new_pos['y']:.0f})")
        print(f"  Direction: {decision.get('expansion_direction')}")
        print(f"  Connect to: {decision.get('connect_to', [])}")
        
        if decision.get('path_waypoints'):
            print(f"  Path waypoints: {decision['path_waypoints']}")
        
        # Execute
        success = planner.act(decision)
        print(f"\nExecution: {success}")
        
        if success:
            print(f"\nAfter expansion:")
            print(f"  Total nodes: {len(network.nodes)}")
            for node in sorted(network.nodes.values(), key=lambda n: (n.position.x, n.position.y)):
                print(f"    {node.node_id}: ({int(node.position.x)}, {int(node.position.y)})")
            
            # Check new node connections
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
        
        # Add more vehicles for next iteration
        for i in range(3):
            env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    print(f"Total nodes: {len(network.nodes)}")
    print(f"Total edges: {len(network.edges)}")
    for node in sorted(network.nodes.values(), key=lambda n: (n.position.x, n.position.y)):
        conns = len(node.outgoing_edges) + len(node.incoming_edges)
        print(f"  {node.node_id}: ({int(node.position.x)}, {int(node.position.y)}) - {conns} connections")


if __name__ == '__main__':
    debug_expansion()
