"""Test backend-like simulation"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

import time
import threading

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment, SimulationConfig
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.utils.vector import Vector2D


def simulation_loop(env, is_running_flag, lock):
    """仿真循环（类似后端）"""
    print("[仿真循环] 启动")
    step_count = 0
    
    while is_running_flag['value']:
        with lock:
            if not is_running_flag['value'] or env is None:
                break
            
            try:
                step_result = env.step()
                step_count += 1
                
                if not step_result:
                    print(f"[仿真循环] step() 返回 False，停止")
                    print(f"  is_running: {env.is_running}")
                    print(f"  is_paused: {env.is_paused}")
                    print(f"  current_time: {env.current_time}")
                    print(f"  max_time: {env.config.max_simulation_time}")
                    is_running_flag['value'] = False
                    break
                
                # 每100步打印一次
                if step_count % 100 == 0:
                    print(f"[仿真循环] Step {step_count}, time={env.current_time:.1f}s, vehicles={len(env.vehicles)}")
                
            except Exception as e:
                print(f"[仿真循环错误] {e}")
                import traceback
                traceback.print_exc()
                is_running_flag['value'] = False
                break
        
        time.sleep(0.05)  # 类似后端的延迟
    
    print(f"[仿真循环] 结束，共运行 {step_count} 步")


def test_backend_simulation():
    """Test simulation like backend does."""
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
    
    # Add initial vehicles
    for i in range(5):
        env.spawn_vehicle(nodes[(0,0)], nodes[(1,1)])
    
    # Start simulation
    env.start()
    
    # Create control flag and lock
    is_running = {'value': True}
    lock = threading.Lock()
    
    # Start simulation thread
    sim_thread = threading.Thread(target=simulation_loop, args=(env, is_running, lock))
    sim_thread.daemon = True
    sim_thread.start()
    
    # Let it run for 10 seconds
    print("\n[测试] 仿真运行 10 秒...")
    time.sleep(10)
    
    # Check status
    print(f"\n[测试] 10秒后状态:")
    print(f"  is_running flag: {is_running['value']}")
    print(f"  env.is_running: {env.is_running}")
    print(f"  env.is_paused: {env.is_paused}")
    print(f"  current_time: {env.current_time:.1f}s")
    print(f"  vehicles: {len(env.vehicles)}")
    
    # Stop
    print("\n[测试] 停止仿真...")
    is_running['value'] = False
    sim_thread.join(timeout=2)
    
    print("\n[测试] 完成")


if __name__ == '__main__':
    test_backend_simulation()
