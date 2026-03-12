"""
动态路网管理器 - 支持从2x2网格动态扩展。
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
    
    管理一个从2x2网格开始的动态扩展路网。
    
    Attributes:
        env: 仿真环境
        grid_size: 当前网格大小（从2开始）
        node_spacing: 节点间距
    """
    
    def __init__(self, env: SimulationEnvironment, node_spacing: float = 200.0) -> None:
        self.env = env
        self.grid_size = 2
        self.node_spacing = node_spacing
        self._setup_initial_network()
    
    def _setup_initial_network(self) -> None:
        """设置初始2x2网格路网。"""
        network = RoadNetwork("dynamic_grid")
        
        # 创建2x2节点（4个节点）
        nodes = {}
        for i in range(2):
            for j in range(2):
                node = Node(
                    position=Vector2D(i * self.node_spacing, j * self.node_spacing),
                    name=f"node_{i}_{j}",
                    is_intersection=False  # 初始不是交叉口
                )
                nodes[(i, j)] = node
                network.add_node(node)
        
        # 创建连接（2x2网格有4条边）
        # 水平连接
        for j in range(2):
            network.create_edge(nodes[(0, j)], nodes[(1, j)], num_lanes=2)
            network.create_edge(nodes[(1, j)], nodes[(0, j)], num_lanes=2)
        
        # 垂直连接
        for i in range(2):
            network.create_edge(nodes[(i, 0)], nodes[(i, 1)], num_lanes=2)
            network.create_edge(nodes[(i, 1)], nodes[(i, 0)], num_lanes=2)
        
        # 设置为环境路网
        self.env.road_network = network
        self.env._setup_network()  # 重新初始化网络相关设置
        
        print(f"[DynamicNetwork] 初始2x2网格创建完成，共4个节点，8条边")
    
    def expand_to_grid(self, new_size: int) -> None:
        """
        扩展网格到指定大小。
        
        Args:
            new_size: 新的网格大小（必须大于当前大小）
        """
        if new_size <= self.grid_size:
            return
        
        old_size = self.grid_size
        self.grid_size = new_size
        network = self.env.road_network
        
        # 获取现有节点
        existing_nodes = {}
        for node in network.nodes.values():
            # 解析节点名称获取坐标
            parts = node.name.split('_')
            if len(parts) == 3 and parts[0] == 'node':
                i, j = int(parts[1]), int(parts[2])
                existing_nodes[(i, j)] = node
        
        # 创建新节点
        new_nodes = {}
        for i in range(new_size):
            for j in range(new_size):
                if (i, j) not in existing_nodes:
                    # 新节点
                    is_intersection = (0 < i < new_size - 1) and (0 < j < new_size - 1)
                    node = Node(
                        position=Vector2D(i * self.node_spacing, j * self.node_spacing),
                        name=f"node_{i}_{j}",
                        is_intersection=is_intersection
                    )
                    network.add_node(node)
                    new_nodes[(i, j)] = node
                    existing_nodes[(i, j)] = node
                    
                    # 如果是交叉口，添加红绿灯
                    if is_intersection:
                        from city.agents.traffic_light_agent import TrafficLightAgent
                        node.traffic_light = TrafficLight(
                            node, cycle_time=60, green_duration=25, yellow_duration=5
                        )
                        
                        # 添加红绿灯智能体
                        tl_agent = TrafficLightAgent(
                            control_node=node,
                            environment=self.env,
                            use_llm=True,
                            name=f"红绿灯_{i}_{j}"
                        )
                        tl_agent.activate()
                        self.env.add_agent(tl_agent)
        
        # 创建新边（水平方向）
        for j in range(new_size):
            for i in range(new_size - 1):
                if not network.has_edge_between(existing_nodes[(i, j)], existing_nodes[(i + 1, j)]):
                    network.create_edge(existing_nodes[(i, j)], existing_nodes[(i + 1, j)], num_lanes=2)
                    network.create_edge(existing_nodes[(i + 1, j)], existing_nodes[(i, j)], num_lanes=2)
        
        # 创建新边（垂直方向）
        for i in range(new_size):
            for j in range(new_size - 1):
                if not network.has_edge_between(existing_nodes[(i, j)], existing_nodes[(i, j + 1)]):
                    network.create_edge(existing_nodes[(i, j)], existing_nodes[(i, j + 1)], num_lanes=2)
                    network.create_edge(existing_nodes[(i, j + 1)], existing_nodes[(i, j)], num_lanes=2)
        
        # 更新环境网络
        self.env._setup_network()
        
        print(f"[DynamicNetwork] 网格扩展: {old_size}x{old_size} -> {new_size}x{new_size}")
        print(f"  新增节点: {len(new_nodes)}")
    
    def get_grid_nodes(self) -> dict[tuple[int, int], Node]:
        """获取所有网格节点（按坐标索引）。"""
        nodes = {}
        for node in self.env.road_network.nodes.values():
            parts = node.name.split('_')
            if len(parts) == 3 and parts[0] == 'node':
                i, j = int(parts[1]), int(parts[2])
                nodes[(i, j)] = node
        return nodes
    
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
        network.create_edge(start_node, mid_node, num_lanes=2)
        network.create_edge(mid_node, start_node, num_lanes=2)
        network.create_edge(mid_node, end_node, num_lanes=2)
        network.create_edge(end_node, mid_node, num_lanes=2)
        
        # 添加红绿灯
        mid_node.traffic_light = TrafficLight(mid_node, cycle_time=60, green_duration=25, yellow_duration=5)
        
        from city.agents.traffic_light_agent import TrafficLightAgent
        tl_agent = TrafficLightAgent(
            control_node=mid_node,
            environment=self.env,
            use_llm=True,
            name=f"红绿灯_mid"
        )
        tl_agent.activate()
        self.env.add_agent(tl_agent)
        
        print(f"[DynamicNetwork] 添加中间节点: {start_node.name} <-> {end_node.name}")
        return mid_node
