"""Test road expansion logic"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_expansion():
    """Test that new nodes expand outward and roads avoid zones."""
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
    print(f"Added zone at ({zone.center.x}, {zone.center.y}) size {zone.width}x{zone.height}")
    
    # Create planning agent
    planner = PopulationCityPlanner(
        env,
        use_llm=False,
        population_per_node=2,
        expansion_threshold=0.5,
        max_nodes=10
    )
    
    # Test finding candidates
    nodes_info = [{'id': n.node_id, 'x': n.position.x, 'y': n.position.y, 'load': 2} 
                  for n in network.nodes.values()]
    
    candidates = planner._find_expansion_candidates_with_zones(nodes_info, 300, 'balanced')
    print(f"\nFound {len(candidates)} expansion candidates:")
    for c in candidates[:5]:
        print(f"  ({c['x']:.0f}, {c['y']:.0f}) dir={c['direction']} type={c['type']}")
    
    # Check that candidates are outside initial grid
    min_x = min(n['x'] for n in nodes_info)
    max_x = max(n['x'] for n in nodes_info)
    min_y = min(n['y'] for n in nodes_info)
    max_y = max(n['y'] for n in nodes_info)
    
    print(f"\nInitial grid bounds: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
    
    outward_count = 0
    for c in candidates:
        if c['x'] < min_x or c['x'] > max_x or c['y'] < min_y or c['y'] > max_y:
            outward_count += 1
    
    print(f"Candidates outside initial grid: {outward_count}/{len(candidates)}")
    
    # Test line intersection with zone
    # Line from (0,0) to (300,300) should intersect zone at (150,150)
    intersects = planner._line_intersects_zone(0, 0, 300, 300, zone)
    print(f"\nLine (0,0)->(300,300) intersects zone: {intersects} (expected: True)")
    
    # Line from (-100,0) to (-100,300) should NOT intersect
    intersects2 = planner._line_intersects_zone(-100, 0, -100, 300, zone)
    print(f"Line (-100,0)->(-100,300) intersects zone: {intersects2} (expected: False)")
    
    print("\nTest completed!")


if __name__ == '__main__':
    test_expansion()
