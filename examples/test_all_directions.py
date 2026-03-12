"""Test expansion in all four directions"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_direction(direction):
    """Test expansion in a specific direction."""
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
    
    # Create zoning agent
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Add blocking zone based on direction
    zone_positions = {
        'left': (-150, 0),
        'right': (450, 0),
        'up': (0, -150),  # North (negative Y)
        'down': (0, 450)  # South (positive Y)
    }
    
    zone_center = zone_positions.get(direction, (-150, 0))
    zone = Zone(
        ZoneType.RESIDENTIAL,
        Vector2D(*zone_center),
        200, 200,
        f"Block{direction.capitalize()}"
    )
    zoning_agent.zone_manager.add_zone(zone)
    
    print(f"\n{'='*50}")
    print(f"Testing expansion: {direction}")
    print(f"Block zone at: {zone_center}")
    print(f"Initial nodes: {[(n.node_id, int(n.position.x), int(n.position.y)) for n in network.nodes.values()]}")
    
    # Create planning agent
    planner = PopulationCityPlanner(env, use_llm=False)
    env.add_agent(planner)
    
    # Add vehicles
    for i in range(5):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    # Force expansion
    decision = planner._plan_expansion()
    if not decision:
        print("  No expansion possible")
        return
    
    new_pos = decision['new_node_position']
    print(f"  New node at: ({new_pos['x']}, {new_pos['y']})")
    print(f"  Direction: {decision.get('expansion_direction', 'unknown')}")
    print(f"  Connect to: {decision.get('connect_to', [])}")
    if decision.get('path_waypoints'):
        print(f"  Path waypoints: {decision['path_waypoints']}")
    else:
        print(f"  No path waypoints (direct connection)")
    
    # Execute
    success = planner.act(decision)
    print(f"  Success: {success}")
    
    if success:
        for node in network.nodes.values():
            if abs(node.position.x - new_pos['x']) < 1 and abs(node.position.y - new_pos['y']) < 1:
                print(f"  New node: {node.node_id} at ({int(node.position.x)}, {int(node.position.y)})")
                # Count connections
                conns = []
                for e in node.outgoing_edges:
                    conns.append(f"->{e.to_node.node_id}")
                for e in node.incoming_edges:
                    conns.append(f"<-{e.from_node.node_id}")
                print(f"  Connections: {conns}")


def test_all():
    """Test all four directions."""
    for direction in ['left', 'right', 'up', 'down']:
        test_direction(direction)
    
    print(f"\n{'='*50}")
    print("All direction tests completed!")


if __name__ == '__main__':
    test_all()
