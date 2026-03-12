"""
Test road block detection
"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.urban_planning.zone import ZoneManager
from city.urban_planning.realistic_zoning import RealisticZoningPlanner, ZoningConstraints, ZoneType
from city.utils.vector import Vector2D


def test_road_block_detection():
    """Test road block detection."""
    # Create 2x2 grid road network
    network = RoadNetwork('test_grid')
    nodes = {}
    for i in range(3):
        for j in range(3):
            node = Node(position=Vector2D(i * 300, j * 300), name=f'n{i}_{j}')
            network.add_node(node)
            nodes[(i, j)] = node

    # Create horizontal roads
    for j in range(3):
        for i in range(2):
            network.create_edge(nodes[(i, j)], nodes[(i+1, j)], num_lanes=2, bidirectional=True)

    # Create vertical roads
    for i in range(3):
        for j in range(2):
            network.create_edge(nodes[(i, j)], nodes[(i, j+1)], num_lanes=2, bidirectional=True)

    print('[RoadNetwork] 2x2 grid created')
    print(f'  Nodes: {len(network.nodes)}')
    print(f'  Edges: {len(network.edges)}')

    # Create planner
    env = SimulationEnvironment(network)
    zm = ZoneManager()
    planner = RealisticZoningPlanner(zm, env, use_llm=False, constraints=ZoningConstraints())

    # Detect road blocks
    blocks = planner._detect_road_blocks()
    print(f'\n[BlockDetection] Found {len(blocks)} road blocks:')
    for i, block in enumerate(blocks):
        print(f'  Block{i+1}: {block["width"]:.0f}x{block["height"]:.0f}m, '
              f'center({block["center"].x:.0f}, {block["center"].y:.0f}), '
              f'area{block["area"]:.0f}m2')

    # Test finding block for residential
    residential_block = planner.find_block_for_zone(ZoneType.RESIDENTIAL)
    if residential_block:
        print(f'\n[Residential] Found block: {residential_block["width"]:.0f}x{residential_block["height"]:.0f}m')
    else:
        print('\n[Residential] No suitable block found')

    # Test finding block for commercial
    commercial_block = planner.find_block_for_zone(ZoneType.COMMERCIAL)
    if commercial_block:
        print(f'[Commercial] Found block: {commercial_block["width"]:.0f}x{commercial_block["height"]:.0f}m')

    # Test full location finding
    print('\n[LocationTest] Finding optimal residential location...')
    result = planner.find_optimal_location(
        ZoneType.RESIDENTIAL, -100, 700, -100, 700, num_candidates=5
    )
    if result:
        print(f'  Selected: ({result["center"].x:.0f}, {result["center"].y:.0f})')
        print(f'  Size: {result["width"]:.0f}x{result["height"]:.0f}m')
        print(f'  Is block fill: {result.get("is_block_fill", False)}')
        print(f'  Score: {result["score"]:.2f}')
    else:
        print('  No suitable location found')


if __name__ == '__main__':
    test_road_block_detection()
