"""Test for deadlock in planning agent"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

import time
import threading

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.utils.vector import Vector2D


def test_with_timing():
    """Test simulation with timing to find bottleneck."""
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
    
    # Create environment
    config = SimulationConfig(time_step=0.1, max_simulation_time=3600.0, real_time_factor=0)
    env = SimulationEnvironment(network, config)
    
    # Add planning agent
    planner = PopulationCityPlanner(env, use_llm=False)
    env.add_agent(planner)
    
    # Add zoning agent
    zoning_agent = ZoningAgent(env, use_llm=False)
    env.add_agent(zoning_agent)
    
    # Start
    env.start()
    
    print("Running 300 steps (30 seconds simulation time)...")
    slow_steps = []
    
    for i in range(300):
        start_time = time.time()
        result = env.step()
        elapsed = time.time() - start_time
        
        if elapsed > 0.1:  # Slow step
            slow_steps.append((i, elapsed, env.current_time))
        
        if not result:
            print(f"Simulation stopped at step {i}")
            break
        
        if i % 50 == 0:
            print(f"Step {i}: time={env.current_time:.1f}s, vehicles={len(env.vehicles)}")
    
    print(f"\nSimulation complete: time={env.current_time:.1f}s")
    print(f"Slow steps (>0.1s): {len(slow_steps)}")
    for step, elapsed, sim_time in slow_steps[:10]:
        print(f"  Step {step} at t={sim_time:.1f}s took {elapsed:.3f}s")


if __name__ == '__main__':
    test_with_timing()
