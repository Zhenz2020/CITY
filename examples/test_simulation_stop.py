"""Test why simulation stops"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.agents.planning_agent import PopulationCityPlanner
from city.utils.vector import Vector2D


def test_simulation():
    """Run simulation and check when it stops."""
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
    
    # Create config with debug
    config = SimulationConfig(time_step=0.1, max_simulation_time=3600.0, real_time_factor=0)
    env = SimulationEnvironment(network, config)
    
    # Create planning agent
    planner = PopulationCityPlanner(env, use_llm=False)
    env.add_agent(planner)
    
    # Add vehicles
    for i in range(5):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    print(f"Initial state:")
    print(f"  is_running: {env.is_running}")
    print(f"  is_paused: {env.is_paused}")
    print(f"  max_simulation_time: {env.config.max_simulation_time}")
    print(f"  current_time: {env.current_time}")
    
    # Start simulation
    env.start()
    print(f"\nAfter start:")
    print(f"  is_running: {env.is_running}")
    print(f"  is_paused: {env.is_paused}")
    
    # Run many steps
    print(f"\nRunning simulation...")
    last_time = 0
    for i in range(5000):  # Run 5000 steps = 500 seconds
        result = env.step()
        
        if not result:
            print(f"\nSimulation stopped at step {i}, time {env.current_time:.1f}s")
            print(f"  is_running: {env.is_running}")
            print(f"  is_paused: {env.is_paused}")
            print(f"  Vehicles: {len(env.vehicles)}")
            break
        
        # Print progress every 100 steps
        if i % 100 == 0:
            print(f"  Step {i}: time={env.current_time:.1f}s, vehicles={len(env.vehicles)}")
        
        # Print warning if time jumps
        if env.current_time - last_time > 1.0:
            print(f"  Time jump: {last_time:.1f} -> {env.current_time:.1f}")
        last_time = env.current_time
    
    print(f"\nFinal state:")
    print(f"  Total steps: {env.step_count}")
    print(f"  Final time: {env.current_time:.1f}s")
    print(f"  Vehicles remaining: {len(env.vehicles)}")


if __name__ == '__main__':
    test_simulation()
