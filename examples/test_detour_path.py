"""Test detour path around zones"""
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
    
    # Create zoning agent and add a zone in the center
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Add a zone that blocks direct path from (-300, 0) to (0, 0)
    # Zone at (150, 150) with size 200x200 extends from (50, 50) to (250, 250)
    # The line from (-300, 0) to (0, 0) has y=0, which is outside the zone (y: 50-250)
    # So let's place a zone that actually blocks the path
    
    # Place zone at (0, 150) extending to block y=0 path
    # Zone center (0, 100), width 100, height 200 -> covers x:[-50,50], y:[0,200]
    # This would block path from (-300,0) to (0,0) if we extend the zone
    
    # Actually, let's place zone at (-100, 0) to block leftward expansion
    zone = Zone(
        zone_type=ZoneType.RESIDENTIAL,
        center=Vector2D(-150, 0),  # Left of the grid
        width=200,
        height=200,
        name="BlockingZone"
    )
    zoning_agent.zone_manager.add_zone(zone)
    
    print("Initial state:")
    print(f"  Nodes: {[(n.node_id, n.position.x, n.position.y) for n in network.nodes.values()]}")
    print(f"  Zone: ({zone.center.x}, {zone.center.y}) size {zone.width}x{zone.height}")
    print(f"  Zone bounds: X[{zone.center.x - zone.width/2}, {zone.center.x + zone.width/2}], Y[{zone.center.y - zone.height/2}, {zone.center.y + zone.height/2}]")
    
    # Check if line from (-300, 0) to (0, 0) intersects the zone
    x1, y1 = -300, 0
    x2, y2 = 0, 0
    zone_min_x = zone.center.x - zone.width / 2
    zone_max_x = zone.center.x + zone.width / 2
    zone_min_y = zone.center.y - zone.height / 2
    zone_max_y = zone.center.y + zone.height / 2
    
    print(f"\nDirect line from ({x1}, {y1}) to ({x2}, {y2})")
    print(f"  Zone X range: [{zone_min_x}, {zone_max_x}]")
    print(f"  Zone Y range: [{zone_min_y}, {zone_max_y}]")
    print(f"  Line Y = {y1} (constant)")
    
    # Check if y=0 is within zone Y range
    if zone_min_y <= y1 <= zone_max_y:
        print(f"  Y={y1} IS within zone Y range - POTENTIAL INTERSECTION")
        # Check if line X range overlaps with zone X range
        line_min_x = min(x1, x2)
        line_max_x = max(x1, x2)
        if line_min_x <= zone_max_x and line_max_x >= zone_min_x:
            print(f"  X ranges overlap - LINE INTERSECTS ZONE!")
        else:
            print(f"  X ranges don't overlap - no intersection")
    else:
        print(f"  Y={y1} is outside zone Y range - no intersection")
    
    # Create planning agent
    planner = PopulationCityPlanner(
        env,
        use_llm=False,
        population_per_node=2,
        expansion_threshold=0.5,
        max_nodes=10
    )
    env.add_agent(planner)
    
    # Manually test the line intersection check
    print("\n--- Testing _line_intersects_zone ---")
    intersects = planner._line_intersects_zone(x1, y1, x2, y2, zone)
    print(f"  _line_intersects_zone result: {intersects}")
    
    # Now test the path finding
    print("\n--- Testing _find_path_around_zones ---")
    # Create temporary nodes for testing
    from_node = Node(Vector2D(x1, y1), name="temp_from")
    to_node = Node(Vector2D(x2, y2), name="temp_to")
    path = planner._find_path_around_zones(from_node, to_node, [zone])
    print(f"  Detour path: {path}")
    
    # Now let's actually run an expansion and see what happens
    print("\n--- Running actual expansion ---")
    
    # Add vehicles to trigger expansion
    for i in range(5):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    # Force expansion to left
    decision = {
        'action': 'expand_city',
        'new_node_position': {'x': -300, 'y': 0},
        'connect_to': ['node_1'],  # Connect to (0,0)
        'reasoning': 'Test expansion to left',
        'expansion_direction': 'left'
    }
    
    print(f"  Decision: new node at (-300, 0), connect to node_1 (0,0)")
    success = planner.act(decision)
    print(f"  Success: {success}")
    
    if success:
        print(f"\n  After expansion:")
        print(f"    Total nodes: {len(network.nodes)}")
        print(f"    Total edges: {len(network.edges)}")
        for node in network.nodes.values():
            print(f"    {node.node_id}: ({node.position.x}, {node.position.y})")
        
        # Check the path taken
        new_node = None
        for node in network.nodes.values():
            if node.position.x == -300 and node.position.y == 0:
                new_node = node
                break
        
        if new_node:
            print(f"\n  New node {new_node.node_id} connections:")
            for edge in new_node.outgoing_edges:
                print(f"    -> {edge.to_node.node_id} at ({edge.to_node.position.x}, {edge.to_node.position.y})")
            for edge in new_node.incoming_edges:
                print(f"    <- {edge.from_node.node_id} at ({edge.from_node.position.x}, {edge.from_node.position.y})")


if __name__ == '__main__':
    test_detour_path()
