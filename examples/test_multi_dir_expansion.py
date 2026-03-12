"""Test multi-direction expansion with proper grid structure"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_multi_direction():
    """Test expansion in multiple directions."""
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
    
    # Create zoning agent - NO blocking zones for this test
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    print("=" * 60)
    print("MULTI-DIRECTION EXPANSION TEST")
    print("=" * 60)
    print(f"Initial nodes: {[(n.node_id, int(n.position.x), int(n.position.y)) for n in network.nodes.values()]}")
    
    # Create planning agent
    planner = PopulationCityPlanner(
        env,
        use_llm=False,
        population_per_node=2,
        expansion_threshold=0.3,  # Lower threshold for faster expansion
        max_nodes=15
    )
    env.add_agent(planner)
    
    # Add initial vehicles
    for i in range(4):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    # Simulate 6 expansions
    for exp_idx in range(6):
        print(f"\n--- Expansion {exp_idx + 1} ---")
        
        # Get decision
        decision = planner._plan_expansion()
        if not decision:
            print("No expansion decision!")
            break
        
        new_pos = decision['new_node_position']
        print(f"New node at: ({new_pos['x']:.0f}, {new_pos['y']:.0f})")
        print(f"Direction: {decision.get('expansion_direction')}")
        print(f"Connect to: {decision.get('connect_to', [])}")
        
        # Execute
        success = planner.act(decision)
        print(f"Success: {success}")
        
        if success:
            # Show current bounds
            xs = [n.position.x for n in network.nodes.values()]
            ys = [n.position.y for n in network.nodes.values()]
            print(f"Bounds: X[{min(xs):.0f}, {max(xs):.0f}], Y[{min(ys):.0f}, {max(ys):.0f}]")
            
            # Add more vehicles
            for i in range(3):
                env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    print(f"Total nodes: {len(network.nodes)}")
    print(f"Total edges: {len(network.edges)}")
    
    # Show grid layout
    print("\nGrid layout:")
    grid = {}
    for node in network.nodes.values():
        x, y = int(node.position.x), int(node.position.y)
        if x not in grid:
            grid[x] = {}
        grid[x][y] = node.node_id
    
    for x in sorted(grid.keys()):
        row = f"X={x:5d}: "
        for y in sorted(grid[x].keys()):
            row += f"{grid[x][y]:8s}({y:4d}) "
        print(row)
    
    print("\nConnections:")
    for node in sorted(network.nodes.values(), key=lambda n: (n.position.x, n.position.y)):
        conns = []
        for e in node.outgoing_edges:
            conns.append(f"->{e.to_node.node_id}")
        for e in node.incoming_edges:
            conns.append(f"<-{e.from_node.node_id}")
        print(f"  {node.node_id}: ({int(node.position.x)}, {int(node.position.y)}) - {conns}")


if __name__ == '__main__':
    test_multi_direction()
