"""
动态路网管理器 - 支持仿照 procedural_city_generation 的自然路网生成。

从十字形种子开始，使用生长规则（Grid/Organic/Radial）生成自然城市路网。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment


class DynamicNetworkManager:
    """
    动态路网管理器。
    
    管理一个从十字形种子开始的自然生长路网，支持动态扩展。
    """
    
    def __init__(self, env: SimulationEnvironment, node_spacing: float = 200.0) -> None:
        self.env = env
        self.node_spacing = node_spacing
        self._setup_initial_network()
    
    def _setup_initial_network(self) -> None:
        """
        设置初始路网 - 仿照 procedural_city_generation 的十字形种子。
        
        创建4个方向的初始道路，形成自然城市的起始结构。
        """
        network = RoadNetwork("procedural_city")
        
        center = Vector2D(0, 0)
        spacing = self.node_spacing
        
        # 创建中心节点
        center_node = Node(
            position=center,
            name="center",
            is_intersection=True
        )
        network.add_node(center_node)
        
        # 创建4个方向的节点（十字形布局）
        directions = [
            ("east", Vector2D(1, 0)),
            ("west", Vector2D(-1, 0)),
            ("south", Vector2D(0, 1)),
            ("north", Vector2D(0, -1))
        ]
        
        outer_nodes: list[Node] = []
        
        for name, direction in directions:
            # 每个方向创建2个节点（近、远）
            near_pos = center + Vector2D(direction.x * spacing, direction.y * spacing)
            far_pos = center + Vector2D(direction.x * spacing * 2, direction.y * spacing * 2)
            
            near_node = Node(
                position=near_pos,
                name=f"{name}_near",
                is_intersection=False
            )
            far_node = Node(
                position=far_pos,
                name=f"{name}_far",
                is_intersection=False
            )
            
            network.add_node(near_node)
            network.add_node(far_node)
            outer_nodes.append(far_node)
            
            # 连接：中心 -> 近 -> 远
            network.create_edge(center_node, near_node, num_lanes=2, bidirectional=True)
            network.create_edge(near_node, far_node, num_lanes=2, bidirectional=True)
        
        # 在中心添加红绿灯
        if network.needs_traffic_light(center_node):
            network.register_traffic_light(
                center_node,
                TrafficLight(center_node, cycle_time=60, green_duration=25, yellow_duration=5),
            )
            # 添加红绿灯智能体
            from city.agents.traffic_light_agent import TrafficLightAgent
            tl_agent = TrafficLightAgent(
                control_node=center_node,
                environment=self.env,
                use_llm=True,
                name="traffic_light_center"
            )
            tl_agent.activate()
            self.env.add_agent(tl_agent)
        
        # 设置为环境路网
        self.env.road_network = network
        self.env._setup_network()
        
        print(f"[DynamicNetwork] 初始十字形路网创建完成，共{len(network.nodes)}个节点，{len(network.edges)}条边")
    
    def expand_grid_like(
        self,
        new_nodes: list[tuple[float, float]],
        connect_to: list[str] | None = None
    ) -> list[Node]:
        """
        以网格状扩展路网。
        
        Args:
            new_nodes: 新节点位置列表 [(x1, y1), (x2, y2), ...]
            connect_to: 要连接的现有节点ID列表，None则自动连接最近节点
            
        Returns:
            创建的新节点列表
        """
        network = self.env.road_network
        created_nodes: list[Node] = []
        
        for x, y in new_nodes:
            pos = Vector2D(x, y)
            
            # 检查是否已存在接近的节点
            too_close = False
            for existing in network.nodes.values():
                if existing.position.distance_to(pos) < 100:
                    too_close = True
                    break
            
            if too_close:
                continue
            
            # 创建新节点
            node = Node(
                position=pos,
                name=f"node_{int(x)}_{int(y)}",
                is_intersection=True
            )
            network.add_node(node)
            created_nodes.append(node)
            
            # 确定连接目标
            if connect_to:
                target_nodes = [
                    network.get_node(nid) for nid in connect_to
                    if network.get_node(nid)
                ]
            else:
                # 自动连接最近节点
                target_nodes = sorted(
                    list(network.nodes.values()),
                    key=lambda n: n.position.distance_to(pos)
                )[:3]  # 连接最多3个最近节点
            
            # 创建连接（避免重复）
            for target in target_nodes:
                if target is node:
                    continue
                dist = target.position.distance_to(pos)
                if dist < 50:  # 太近的忽略
                    continue
                
                # 检查是否已有连接
                if not network.has_edge_between(node, target):
                    network.create_edge(node, target, num_lanes=2, bidirectional=True)
                
                # 如果是交叉口，添加红绿灯
                for signal_node in (node, target):
                    if network.needs_traffic_light(signal_node) and not signal_node.traffic_light:
                        network.register_traffic_light(
                            signal_node,
                            TrafficLight(signal_node, cycle_time=60, green_duration=25, yellow_duration=5),
                        )
                        
                        from city.agents.traffic_light_agent import TrafficLightAgent
                        tl_agent = TrafficLightAgent(
                            control_node=signal_node,
                            environment=self.env,
                            use_llm=True,
                            name=f"traffic_light_{signal_node.node_id}"
                        )
                        tl_agent.activate()
                        self.env.add_agent(tl_agent)
        
        self.env._setup_network()
        print(f"[DynamicNetwork] 网格扩展完成，新增{len(created_nodes)}个节点")
        return created_nodes
    
    def add_intermediate_node(self, start_node: Node, end_node: Node) -> Node | None:
        """
        在两个节点之间添加中间节点。
        
        Args:
            start_node: 起始节点
            end_node: 目标节点
            
        Returns:
            新创建的节点，如果失败返回None
        """
        network = self.env.road_network
        
        # 检查是否已有直接连接
        if not network.has_edge_between(start_node, end_node):
            return None
        
        # 计算中间位置
        mid_x = (start_node.position.x + end_node.position.x) / 2
        mid_y = (start_node.position.y + end_node.position.y) / 2
        
        # 创建中间节点
        mid_node = Node(
            position=Vector2D(mid_x, mid_y),
            name=f"mid_{start_node.name}_{end_node.name}",
            is_intersection=True
        )
        network.add_node(mid_node)
        
        # 移除旧边
        network.remove_edge_between(start_node, end_node)
        network.remove_edge_between(end_node, start_node)
        
        # 添加新边（经过中间节点）
        network.create_edge(start_node, mid_node, num_lanes=2, bidirectional=True)
        network.create_edge(mid_node, end_node, num_lanes=2, bidirectional=True)
        
        # 添加红绿灯
        if not network.needs_traffic_light(mid_node):
            print(f"[DynamicNetwork] 娣诲姞涓棿鑺傜偣: {start_node.name} <-> {end_node.name}")
            return mid_node
        network.register_traffic_light(
            mid_node,
            TrafficLight(mid_node, cycle_time=60, green_duration=25, yellow_duration=5),
        )
        
        from city.agents.traffic_light_agent import TrafficLightAgent
        tl_agent = TrafficLightAgent(
            control_node=mid_node,
            environment=self.env,
            use_llm=True,
            name=f"traffic_light_{mid_node.node_id}"
        )
        tl_agent.activate()
        self.env.add_agent(tl_agent)
        
        print(f"[DynamicNetwork] 添加中间节点: {start_node.name} <-> {end_node.name}")
        return mid_node


def create_procedural_initial_network(
    env: SimulationEnvironment,
    center: Vector2D | None = None,
    initial_radius: float = 400.0,
    num_arms: int = 4
) -> RoadNetwork:
    """
    创建仿 procedural_city_generation 风格的初始路网（改进版）。
    
    修复了原版的以下问题：
    1. 末端节点被错误标记为交叉口（实际连接数只有2）
    2. 中间节点未标记为交叉口（实际连接数为4）
    3. 只有中心节点有红绿灯
    
    Args:
        env: 仿真环境
        center: 城市中心，默认 (0, 0)
        initial_radius: 初始道路半径
        num_arms: 放射臂数量（4=十字形，6=六角星形等）
        
    Returns:
        初始道路网络
    """
    from city.agents.traffic_light_agent import TrafficLightAgent
    
    network = RoadNetwork("procedural_initial")
    center = center or Vector2D(0, 0)
    
    # 创建中心交叉口
    center_node = Node(
        position=center,
        name="center",
        is_intersection=True
    )
    network.add_node(center_node)
    
    # 创建放射臂
    angle_step = 2 * math.pi / num_arms
    arm_end_nodes: list[Node] = []
    
    for i in range(num_arms):
        angle = i * angle_step
        direction = Vector2D(math.cos(angle), math.sin(angle))
        
        # 每个臂创建2个节点：中间节点 + 末端节点
        # 中间节点（距离中心一半）- 真正的交叉口
        mid_distance = initial_radius / 2
        mid_pos = center + Vector2D(direction.x * mid_distance, direction.y * mid_distance)
        
        mid_node = Node(
            position=mid_pos,
            name=f"arm{i}_mid",
            is_intersection=True  # 连接中心+末端+可能的对向+环路
        )
        network.add_node(mid_node)
        network.create_edge(center_node, mid_node, num_lanes=2, bidirectional=True)
        
        # 末端节点
        end_pos = center + Vector2D(direction.x * initial_radius, direction.y * initial_radius)
        end_node = Node(
            position=end_pos,
            name=f"arm{i}_end",
            is_intersection=False  # 普通节点，除非连接环路
        )
        network.add_node(end_node)
        network.create_edge(mid_node, end_node, num_lanes=2, bidirectional=True)
        
        arm_end_nodes.append(end_node)
    
    # 可选：连接相邻臂的末端节点形成外围环路
    for i in range(len(arm_end_nodes)):
        next_i = (i + 1) % len(arm_end_nodes)
        dist = arm_end_nodes[i].position.distance_to(arm_end_nodes[next_i].position)
        
        # 如果距离合适，创建环路连接
        if dist <= initial_radius * 1.5:
            network.create_edge(
                arm_end_nodes[i], arm_end_nodes[next_i],
                num_lanes=2, bidirectional=True
            )
            # 连接环路后，末端节点也成为交叉口
            arm_end_nodes[i].is_intersection = True
            arm_end_nodes[next_i].is_intersection = True
    
    # 为所有交叉口添加红绿灯（连接数 >= 3）
    for node in network.nodes.values():
        if network.needs_traffic_light(node) and not node.traffic_light:
            node.is_intersection = True
            network.register_traffic_light(
                node,
                TrafficLight(node, cycle_time=60, green_duration=25, yellow_duration=5),
            )
            
            tl_agent = TrafficLightAgent(
                control_node=node,
                environment=env,
                use_llm=True,
                name=f"traffic_light_{node.name}"
            )
            tl_agent.activate()
            env.add_agent(tl_agent)
    
    return network


import math
