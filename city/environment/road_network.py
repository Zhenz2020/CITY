"""
道路网络模块。

定义道路网络的基本组件：节点（交叉口）、路段、车道、道路网络等。
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from city.utils.vector import Vector2D


class Direction(Enum):
    """行驶方向。"""
    NORTH = auto()
    SOUTH = auto()
    EAST = auto()
    WEST = auto()


class LaneType(Enum):
    """车道类型。"""
    REGULAR = auto()      # 普通车道
    BUS = auto()          # 公交专用道
    BIKE = auto()         # 自行车道
    PEDESTRIAN = auto()   # 人行道
    EMERGENCY = auto()    # 应急车道


class Node:
    """
    道路网络节点，表示交叉口或道路端点。

    Attributes:
        node_id: 节点唯一标识
        position: 节点位置坐标
        name: 节点名称（可选）
        is_intersection: 是否为交叉口
    """

    _id_counter = 0

    def __init__(
        self,
        position: Vector2D,
        name: str | None = None,
        is_intersection: bool = False
    ) -> None:
        Node._id_counter += 1
        self.node_id = f"node_{Node._id_counter}"
        self.position = position
        self.name = name or self.node_id
        self.is_intersection = is_intersection

        # 连接的路段
        self.incoming_edges: list[Edge] = []
        self.outgoing_edges: list[Edge] = []

        # 如果是交叉口，包含交通信号灯
        self.traffic_light: TrafficLight | None = None

    def __repr__(self) -> str:
        return f"Node({self.node_id}, pos={self.position})"

    def add_incoming_edge(self, edge: Edge) -> None:
        """添加入向路段。"""
        self.incoming_edges.append(edge)

    def add_outgoing_edge(self, edge: Edge) -> None:
        """添加出向路段。"""
        self.outgoing_edges.append(edge)


class TrafficLightState(Enum):
    """交通信号灯状态。"""
    RED = auto()
    YELLOW = auto()
    GREEN = auto()


class TrafficLight:
    """
    交通信号灯。

    控制交叉口的车辆通行。
    """

    def __init__(
        self,
        node: Node,
        cycle_time: float = 60.0,
        green_duration: float = 30.0,
        yellow_duration: float = 5.0
    ) -> None:
        self.node = node
        self.state = TrafficLightState.RED
        self.cycle_time = cycle_time
        self.green_duration = green_duration
        self.yellow_duration = yellow_duration
        self.red_duration = cycle_time - green_duration - yellow_duration

        self.current_phase_time = 0.0

    @property
    def timer(self) -> float:
        """获取当前相位剩余时间。"""
        if self.state == TrafficLightState.GREEN:
            return max(0, self.green_duration - self.current_phase_time)
        elif self.state == TrafficLightState.YELLOW:
            return max(0, self.yellow_duration - self.current_phase_time)
        else:  # RED
            return max(0, self.red_duration - self.current_phase_time)

    def update(self, dt: float) -> None:
        """更新信号灯状态。"""
        self.current_phase_time += dt

        if self.state == TrafficLightState.GREEN:
            if self.current_phase_time >= self.green_duration:
                self.state = TrafficLightState.YELLOW
                self.current_phase_time = 0.0
        elif self.state == TrafficLightState.YELLOW:
            if self.current_phase_time >= self.yellow_duration:
                self.state = TrafficLightState.RED
                self.current_phase_time = 0.0
        elif self.state == TrafficLightState.RED:
            if self.current_phase_time >= self.red_duration:
                self.state = TrafficLightState.GREEN
                self.current_phase_time = 0.0

    def set_state(self, state: TrafficLightState) -> None:
        """手动设置信号灯状态。"""
        self.state = state
        self.current_phase_time = 0.0

    def can_pass(self) -> bool:
        """检查是否允许通行。"""
        return self.state == TrafficLightState.GREEN


class Lane:
    """
    车道。

    道路的基本组成单元，车辆沿车道行驶。

    Attributes:
        lane_id: 车道唯一标识
        lane_type: 车道类型
        length: 车道长度
        max_speed: 最高限速
        width: 车道宽度
    """

    _id_counter = 0

    def __init__(
        self,
        length: float,
        lane_type: LaneType = LaneType.REGULAR,
        max_speed: float = 13.89,  # 默认50km/h，单位m/s
        width: float = 3.5
    ) -> None:
        Lane._id_counter += 1
        self.lane_id = f"lane_{Lane._id_counter}"
        self.lane_type = lane_type
        self.length = length
        self.max_speed = max_speed
        self.width = width

        # 相邻车道
        self.left_lane: Lane | None = None
        self.right_lane: Lane | None = None

        # 当前车道上的车辆
        self.vehicles: list[Any] = []

    def __repr__(self) -> str:
        return f"Lane({self.lane_id}, len={self.length:.1f}m)"

    def add_vehicle(self, vehicle: Any) -> None:
        """添加车辆到车道。"""
        self.vehicles.append(vehicle)

    def remove_vehicle(self, vehicle: Any) -> None:
        """从车道移除车辆。"""
        if vehicle in self.vehicles:
            self.vehicles.remove(vehicle)


class Edge:
    """
    路段，连接两个节点的道路。

    Attributes:
        edge_id: 路段唯一标识
        from_node: 起点节点
        to_node: 终点节点
        lanes: 路段包含的车道列表
        length: 路段长度
    """

    _id_counter = 0

    def __init__(
        self,
        from_node: Node,
        to_node: Node,
        num_lanes: int = 2,
        lane_width: float = 3.5,
        max_speed: float = 13.89
    ) -> None:
        Edge._id_counter += 1
        self.edge_id = f"edge_{Edge._id_counter}"
        self.from_node = from_node
        self.to_node = to_node

        # 计算路段长度
        self.length = from_node.position.distance_to(to_node.position)

        # 创建车道
        self.lanes: list[Lane] = []
        for i in range(num_lanes):
            lane = Lane(
                length=self.length,
                max_speed=max_speed,
                width=lane_width
            )
            self.lanes.append(lane)

        # 设置车道相邻关系
        for i in range(num_lanes - 1):
            self.lanes[i].right_lane = self.lanes[i + 1]
            self.lanes[i + 1].left_lane = self.lanes[i]

        # 注册到节点
        from_node.add_outgoing_edge(self)
        to_node.add_incoming_edge(self)

    def __repr__(self) -> str:
        return f"Edge({self.edge_id}, {self.from_node.node_id} -> {self.to_node.node_id})"

    def get_free_lane(self) -> Lane | None:
        """获取车辆数最少的车道。"""
        if not self.lanes:
            return None
        return min(self.lanes, key=lambda l: len(l.vehicles))


class RoadNetwork:
    """
    道路网络。

    管理所有道路网络组件（节点、路段、车道）。
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.traffic_lights: dict[str, TrafficLight] = {}

    def __repr__(self) -> str:
        return f"RoadNetwork({self.name}, {len(self.nodes)} nodes, {len(self.edges)} edges)"

    def add_node(self, node: Node) -> Node:
        """添加节点到网络。"""
        self.nodes[node.node_id] = node
        if node.is_intersection and node.traffic_light:
            self.traffic_lights[node.node_id] = node.traffic_light
        return node

    def add_edge(self, edge: Edge) -> Edge:
        """添加路段到网络。"""
        self.edges[edge.edge_id] = edge
        return edge

    def create_edge(
        self,
        from_node: Node,
        to_node: Node,
        num_lanes: int = 2,
        bidirectional: bool = True
    ) -> Edge | tuple[Edge, Edge]:
        """
        创建路段。

        Args:
            from_node: 起点节点
            to_node: 终点节点
            num_lanes: 车道数
            bidirectional: 是否双向

        Returns:
            单向返回一个Edge，双向返回两个Edge的元组
        """
        edge1 = Edge(from_node, to_node, num_lanes)
        self.add_edge(edge1)

        if bidirectional:
            edge2 = Edge(to_node, from_node, num_lanes)
            self.add_edge(edge2)
            return edge1, edge2

        return edge1

    def get_node(self, node_id: str) -> Node | None:
        """根据ID获取节点。"""
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Edge | None:
        """根据ID获取路段。"""
        return self.edges.get(edge_id)

    def update_traffic_lights(self, dt: float, skip_nodes: set[str] | None = None) -> None:
        """更新所有交通信号灯。"""
        skip = skip_nodes or set()
        for node_id, traffic_light in self.traffic_lights.items():
            if node_id in skip:
                continue
            traffic_light.update(dt)

    def find_shortest_path(self, start: Node, end: Node) -> list[Node] | None:
        """
        使用Dijkstra算法找到最短路径。

        Args:
            start: 起点节点
            end: 终点节点

        Returns:
            节点列表表示的路径，如果不可达返回None
        """
        import heapq

        dist = {node_id: float('inf') for node_id in self.nodes}
        prev = {node_id: None for node_id in self.nodes}
        dist[start.node_id] = 0

        pq = [(0, start.node_id)]
        visited = set()

        while pq:
            d, current_id = heapq.heappop(pq)

            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == end.node_id:
                break

            current = self.nodes[current_id]
            for edge in current.outgoing_edges:
                neighbor_id = edge.to_node.node_id
                new_dist = d + edge.length

                if new_dist < dist[neighbor_id]:
                    dist[neighbor_id] = new_dist
                    prev[neighbor_id] = current_id
                    heapq.heappush(pq, (new_dist, neighbor_id))

        # 重建路径
        if prev[end.node_id] is None and start != end:
            return None

        path = []
        current_id = end.node_id
        while current_id is not None:
            path.append(self.nodes[current_id])
            current_id = prev[current_id]

        return list(reversed(path))
