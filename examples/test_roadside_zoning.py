"""Test road-side zoning placement"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import ZoneManager
from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.utils.vector import Vector2D

# Create simple grid network
network = RoadNetwork('test')
nodes = {}
for i in range(3):
    for j in range(3):
        n = Node(Vector2D(i*300, j*300), name=f'n{i}_{j}')
        network.add_node(n)
        nodes[(i,j)] = n

# Create grid roads
for i in range(2):
    for j in range(3):
        network.create_edge(nodes[(i,j)], nodes[(i+1,j)], num_lanes=2, bidirectional=True)
for i in range(3):
    for j in range(2):
        network.create_edge(nodes[(i,j)], nodes[(i,j+1)], num_lanes=2, bidirectional=True)

env = SimulationEnvironment(network)
agent = ZoningAgent(env, use_llm=False)
agent.zone_manager = ZoneManager()

# Test getting road-side locations
locations = agent._get_road_side_locations()
print(f'Found {len(locations)} road-side locations')
for i, loc in enumerate(locations[:5]):
    print(f'  {i}: ({loc["x"]:.0f}, {loc["y"]:.0f}) - {loc["road_orientation"]} road, {loc["side"]} side')

# Test rule-based selection
decision = agent._rule_select_location_and_type(locations)
if decision:
    print(f'\nSelected: {decision["zone_type"].display_name}')
    print(f'  Location: ({decision["center"].x:.0f}, {decision["center"].y:.0f})')
    print(f'  Size: {decision["width"]:.0f}x{decision["height"]:.0f}m')
    print(f'  Road side: {decision["road_side"]}')
