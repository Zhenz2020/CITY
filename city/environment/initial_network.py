"""
改进的初始路网生成器。

提供多种初始路网模板，确保生成的路网合理且可用。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from city.environment.road_network import RoadNetwork, Node, TrafficLight
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment


def create_cross_network(
    env: SimulationEnvironment | None = None,
    center: Vector2D | None = None,
    arm_length: float = 400.0,
    add_ring: bool = False
) -> RoadNetwork:
    """
    创建十字形初始路网（改进版）。
    
    结构：
    ```
            [北]
             |
        [西]-[中心]-[东]
             |
            [南]
    ```
    
    Args:
        env: 仿真环境（可选，用于添加红绿灯代理）
        center: 中心位置
        arm_length: 臂长（从中心到末端）
        add_ring: 是否添加外围环路
        
    Returns:
        道路网络
    """
    network = RoadNetwork("cross_initial")
    center = center or Vector2D(0, 0)
    
    # 创建中心交叉口
    center_node = Node(
        position=center,
        name="center",
        is_intersection=True
    )
    network.add_node(center_node)
    
    # 创建4个方向臂（每个臂2个节点）
    directions = [
        ("east", Vector2D(1, 0)),
        ("west", Vector2D(-1, 0)),
        ("north", Vector2D(0, 1)),
        ("south", Vector2D(0, -1))
    ]
    
    arm_nodes: dict[str, list[Node]] = {}
    
    for name, direction in directions:
        nodes: list[Node] = []
        prev_node = center_node
        
        # 每个臂创建2个节点
        for i in range(1, 3):
            distance = (arm_length / 2) * i
            pos = center + Vector2D(direction.x * distance, direction.y * distance)
            
            # 中间节点是真正的交叉口（连接中心+末端+可能的对向+环路）
            is_intersection = (i == 1)
            
            node = Node(
                position=pos,
                name=f"{name}_{i}",
                is_intersection=is_intersection
            )
            network.add_node(node)
            nodes.append(node)
            
            # 连接到前一个节点
            network.create_edge(prev_node, node, num_lanes=2, bidirectional=True)
            prev_node = node
        
        arm_nodes[name] = nodes
    
    # 可选：连接相邻臂的末端节点形成外围环路
    if add_ring:
        ring_nodes = [
            arm_nodes["east"][-1],
            arm_nodes["north"][-1],
            arm_nodes["west"][-1],
            arm_nodes["south"][-1]
        ]
        
        for i in range(len(ring_nodes)):
            next_i = (i + 1) % len(ring_nodes)
            network.create_edge(
                ring_nodes[i], ring_nodes[next_i],
                num_lanes=2, bidirectional=True
            )
    
    # 添加红绿灯（可选，需要 env）
    if env is not None:
        _add_traffic_lights_to_network(network, env)
    
    return network


def create_grid_network(
    env: SimulationEnvironment | None = None,
    center: Vector2D | None = None,
    grid_size: int = 2,
    spacing: float = 300.0
) -> RoadNetwork:
    """
    创建网格初始路网。
    
    Args:
        env: 仿真环境（可选，用于添加红绿灯代理）
        center: 中心位置
        grid_size: 网格大小（2=2x2, 3=3x3等）
        spacing: 节点间距
        
    Returns:
        道路网络
    """
    network = RoadNetwork("grid_initial")
    center = center or Vector2D(0, 0)
    
    # 计算起始位置（左下角）
    start_x = center.x - (grid_size - 1) * spacing / 2
    start_y = center.y - (grid_size - 1) * spacing / 2
    
    # 创建节点
    nodes: dict[tuple[int, int], Node] = {}
    
    for i in range(grid_size):
        for j in range(grid_size):
            pos = Vector2D(
                start_x + i * spacing,
                start_y + j * spacing
            )
            
            # 判断是否为交叉口（内部节点）
            is_intersection = (0 < i < grid_size - 1) and (0 < j < grid_size - 1)
            
            node = Node(
                position=pos,
                name=f"node_{i}_{j}",
                is_intersection=is_intersection
            )
            network.add_node(node)
            nodes[(i, j)] = node
    
    # 创建水平连接
    for j in range(grid_size):
        for i in range(grid_size - 1):
            network.create_edge(
                nodes[(i, j)], nodes[(i + 1, j)],
                num_lanes=2, bidirectional=True
            )
    
    # 创建垂直连接
    for i in range(grid_size):
        for j in range(grid_size - 1):
            network.create_edge(
                nodes[(i, j)], nodes[(i, j + 1)],
                num_lanes=2, bidirectional=True
            )
    
    # 添加红绿灯（可选，需要 env）
    if env is not None:
        _add_traffic_lights_to_network(network, env)
    
    return network


def create_radial_network(
    env: SimulationEnvironment | None = None,
    center: Vector2D | None = None,
    num_arms: int = 6,
    num_rings: int = 2,
    arm_length: float = 500.0
) -> RoadNetwork:
    """
    创建放射状+环形初始路网。
    
    Args:
        env: 仿真环境（可选，用于添加红绿灯代理）
        center: 中心位置
        num_arms: 放射臂数量
        num_rings: 环数
        arm_length: 臂长
        
    Returns:
        道路网络
    """
    network = RoadNetwork("radial_initial")
    center = center or Vector2D(0, 0)
    
    # 创建中心节点
    center_node = Node(
        position=center,
        name="center",
        is_intersection=True
    )
    network.add_node(center_node)
    
    # 创建放射臂
    angle_step = 2 * math.pi / num_arms
    ring_nodes: list[list[Node]] = [[] for _ in range(num_rings)]
    
    for arm_idx in range(num_arms):
        angle = arm_idx * angle_step
        direction = Vector2D(math.cos(angle), math.sin(angle))
        
        prev_node = center_node
        
        for ring_idx in range(num_rings):
            distance = arm_length * (ring_idx + 1) / num_rings
            pos = center + Vector2D(direction.x * distance, direction.y * distance)
            
            # 在环上的节点都是交叉口（连接放射臂+环）
            is_intersection = True
            
            node = Node(
                position=pos,
                name=f"arm{arm_idx}_ring{ring_idx}",
                is_intersection=is_intersection
            )
            network.add_node(node)
            ring_nodes[ring_idx].append(node)
            
            # 放射连接
            network.create_edge(prev_node, node, num_lanes=2, bidirectional=True)
            prev_node = node
    
    # 创建环连接
    for ring_idx in range(num_rings):
        nodes = ring_nodes[ring_idx]
        for i in range(len(nodes)):
            next_i = (i + 1) % len(nodes)
            network.create_edge(
                nodes[i], nodes[next_i],
                num_lanes=2, bidirectional=True
            )
    
    # 添加红绿灯（可选，需要 env）
    if env is not None:
        _add_traffic_lights_to_network(network, env)
    
    return network


def _add_traffic_lights_to_network(
    network: RoadNetwork,
    env: SimulationEnvironment
) -> None:
    """为网络中所有合适的节点添加红绿灯。"""
    from city.agents.traffic_light_agent import TrafficLightAgent
    
    for node in network.nodes.values():
        # 连接数 >= 3 的节点需要红绿灯
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


def create_improved_initial_network(
    env: SimulationEnvironment,
    network_type: str = "cross",
    center: Vector2D | None = None,
    **kwargs
) -> RoadNetwork:
    """
    创建改进的初始路网。
    
    Args:
        env: 仿真环境
        network_type: 网络类型 ("cross", "grid", "radial")
        center: 中心位置
        **kwargs: 额外参数传递给具体创建函数
        
    Returns:
        道路网络
    """
    center = center or Vector2D(0, 0)
    
    if network_type == "cross":
        return create_cross_network(env, center, **kwargs)
    elif network_type == "grid":
        return create_grid_network(env, center, **kwargs)
    elif network_type == "radial":
        return create_radial_network(env, center, **kwargs)
    else:
        raise ValueError(f"Unknown network type: {network_type}")
