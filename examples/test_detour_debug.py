"""Debug detour path calculation"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.agents.planning_agent import PopulationCityPlanner
from city.agents.zoning_agent import ZoningAgent
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D


def test_debug():
    """Debug the detour path calculation."""
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
    
    zone = Zone(
        zone_type=ZoneType.RESIDENTIAL,
        center=Vector2D(-150, 0),
        width=200,
        height=200,
        name="BlockingZone"
    )
    zoning_agent.zone_manager.add_zone(zone)
    
    print(f"Zoning agent added: {zoning_agent is not None}")
    print(f"Zoning agent type: {zoning_agent.agent_type}")
    print(f"Environment agents: {len(env.agents)}")
    for agent in env.agents.values():  # Fixed: iterate over values()
        print(f"  - {agent.agent_type}: has zone_manager = {hasattr(agent, 'zone_manager')}")
    
    # Create planning agent
    planner = PopulationCityPlanner(env, use_llm=False)
    env.add_agent(planner)
    
    # Check if planner can find zoning agent
    print(f"\nPlanner environment: {planner.environment is not None}")
    print(f"Planner env agents: {len(planner.environment.agents)}")
    
    zoning = planner._get_zoning_agent()
    print(f"Found zoning agent: {zoning is not None}")
    if zoning:
        print(f"  Zoning agent has {len(zoning.zone_manager.zones)} zones")
    
    # Get zones
    zones = planner._get_zones_for_expansion_planning()
    print(f"Zones found via _get_zones_for_expansion_planning: {len(zones)}")


if __name__ == '__main__':
    test_debug()
