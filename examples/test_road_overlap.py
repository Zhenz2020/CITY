"""
测试道路重叠检测
"""
import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.urban_planning.zone import Zone, ZoneType
from city.urban_planning.realistic_zoning import RealisticZoningPlanner, ZoningConstraints
from city.utils.vector import Vector2D


def create_test_network():
    """创建带道路的网络。"""
    network = RoadNetwork("test_city")
    
    # 创建4个节点形成十字道路
    nodes = {}
    positions = [
        (0, 200), (200, 200),  # 水平道路
        (200, 0), (200, 400)   # 垂直道路
    ]
    
    for i, (x, y) in enumerate(positions):
        node = Node(position=Vector2D(x, y), name=f"node_{i}")
        network.add_node(node)
        nodes[i] = node
    
    # 创建道路边
    network.create_edge(nodes[0], nodes[1], num_lanes=2, bidirectional=True)  # 水平
    network.create_edge(nodes[2], nodes[3], num_lanes=2, bidirectional=True)  # 垂直
    
    return network


def test_road_overlap():
    """测试道路重叠检测。"""
    print("=" * 60)
    print("道路重叠检测测试")
    print("=" * 60)
    
    # 创建仿真环境
    network = create_test_network()
    env = SimulationEnvironment(network)
    
    # 创建规划器
    from city.urban_planning.zone import ZoneManager
    zone_manager = ZoneManager()
    planner = RealisticZoningPlanner(
        zone_manager=zone_manager,
        environment=env,
        use_llm=False,
        constraints=ZoningConstraints()
    )
    
    print("\n[网络信息]")
    print(f"节点数: {len(network.nodes)}")
    print(f"道路数: {len(network.edges)}")
    
    # 测试位置1：与道路重叠（应该检测到）
    print("\n[测试1] 区域与道路重叠")
    zone1 = Zone(
        zone_type=ZoneType.RESIDENTIAL,
        center=Vector2D(200, 200),  # 在交叉口
        width=100,
        height=100,
        name="重叠区域"
    )
    overlap1 = planner._check_road_overlap(zone1)
    print(f"  位置: (200, 200)")
    print(f"  是否与道路重叠: {overlap1}")
    print(f"  期望: True")
    
    # 测试位置2：不与道路重叠
    print("\n[测试2] 区域不与道路重叠")
    zone2 = Zone(
        zone_type=ZoneType.RESIDENTIAL,
        center=Vector2D(50, 50),  # 远离道路
        width=60,
        height=60,
        name="非重叠区域"
    )
    overlap2 = planner._check_road_overlap(zone2)
    print(f"  位置: (50, 50)")
    print(f"  是否与道路重叠: {overlap2}")
    print(f"  期望: False")
    
    # 测试位置3：靠近道路但不重叠
    print("\n[测试3] 区域靠近道路但不重叠")
    zone3 = Zone(
        zone_type=ZoneType.RESIDENTIAL,
        center=Vector2D(200, 100),  # 靠近垂直道路
        width=50,
        height=50,
        name="靠近道路区域"
    )
    overlap3 = planner._check_road_overlap(zone3)
    road_dist = planner._evaluate_road_distance(zone3.center)
    print(f"  位置: (200, 100)")
    print(f"  是否与道路重叠: {overlap3}")
    print(f"  道路距离评分: {road_dist:.2f}")
    print(f"  期望重叠: False")
    
    # 完整评估
    print("\n[测试4] 完整位置评估")
    eval_result = planner.evaluate_location(
        ZoneType.RESIDENTIAL,
        Vector2D(50, 50),
        80, 60
    )
    print(f"  总分: {eval_result['total_score']:.2f}")
    print(f"  是否适宜: {eval_result['is_suitable']}")
    print(f"  优点: {eval_result['advantages']}")
    print(f"  问题: {eval_result['issues']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_road_overlap()
