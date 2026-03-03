"""
行人代理模块。

模拟行人在交通环境中的行为。
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from city.agents.base import BaseAgent, AgentType, AgentState
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.environment.road_network import Node, Crosswalk
    from city.simulation.environment import SimulationEnvironment


class PedestrianState(Enum):
    """行人状态。"""
    WALKING = auto()      # 行走
    WAITING = auto()      # 等待
    CROSSING = auto()     # 过马路
    STOPPED = auto()      # 停止


class PedestrianAction(Enum):
    """行人动作。"""
    WALK = auto()         # 行走
    WAIT = auto()         # 等待
    CROSS = auto()        # 过马路
    STOP = auto()         # 停止


class Pedestrian(BaseAgent):
    """
    行人代理。

    模拟行人在交叉口、人行道等区域的行为。

    Attributes:
        position: 当前位置
        velocity: 当前速度
        direction: 行走方向
        max_speed: 最大步行速度
        state: 行人状态
        target_position: 目标位置
        route: 行走路径
    """

    # 默认行人参数
    DEFAULT_MAX_SPEED = 1.39  # 约 5 km/h
    DEFAULT_ACCELERATION = 0.5
    DEFAULT_SIZE = 0.5  # 直径约0.5米

    def __init__(
        self,
        environment: SimulationEnvironment | None = None,
        start_position: Vector2D | None = None,
        end_position: Vector2D | None = None,
        use_llm: bool = False
    ) -> None:
        super().__init__(AgentType.PEDESTRIAN, environment, use_llm)

        # 物理参数
        self.max_speed = self.DEFAULT_MAX_SPEED
        self.acceleration = self.DEFAULT_ACCELERATION
        self.size = self.DEFAULT_SIZE

        # 动态状态
        self.position = start_position or Vector2D()
        self.velocity = 0.0
        self.direction = Vector2D(1, 0)
        self.pedestrian_state = PedestrianState.WALKING

        # 路径相关
        self.start_position = start_position
        self.end_position = end_position
        self.target_position = end_position
        self.route: list[Vector2D] = []
        self.route_index = 0

        # 等待相关
        self.wait_time = 0.0
        self.max_wait_time = 60.0  # 最大等待时间

        # 过马路相关
        self.is_crossing = False
        self.current_crosswalk: Crosswalk | None = None

    def __repr__(self) -> str:
        return f"Pedestrian({self.agent_id}, pos={self.position}, state={self.pedestrian_state.name})"

    def set_route(self, waypoints: list[Vector2D]) -> None:
        """设置行走路径。"""
        self.route = waypoints
        self.route_index = 0
        if waypoints:
            self.start_position = waypoints[0]
            self.end_position = waypoints[-1]
            self.position = waypoints[0].copy()
            self.target_position = waypoints[1] if len(waypoints) > 1 else waypoints[0]
            self._update_direction()

    def plan_route(self, start: Vector2D, end: Vector2D) -> None:
        """
        规划行走路径。

        简化实现：直线路径。
        """
        self.set_route([start, end])

    def perceive(self) -> dict[str, Any]:
        """
        感知周围环境。

        Returns:
            感知信息字典
        """
        perception = {
            'position': self.position,
            'velocity': self.velocity,
            'state': self.pedestrian_state,
            'distance_to_target': self._distance_to_target(),
            'has_reached_destination': self._has_reached_destination(),
            'traffic_light_state': None,
            'nearby_vehicles': [],
            'is_safe_to_cross': True
        }

        # 检测附近车辆
        perception['nearby_vehicles'] = self._detect_nearby_vehicles()

        # 检测交通信号灯（如果在交叉口）
        perception['traffic_light_state'] = self._detect_traffic_light()

        # 判断是否安全过马路
        perception['is_safe_to_cross'] = self._is_safe_to_cross(perception['nearby_vehicles'])

        return perception

    def _detect_nearby_vehicles(self) -> list[Any]:
        """检测附近的车辆。"""
        nearby = []
        if not self.environment:
            return nearby

        detection_radius = 20.0  # 检测半径

        for agent in self.environment.agents.values():
            from city.agents.vehicle import Vehicle
            if isinstance(agent, Vehicle):
                distance = self.position.distance_to(agent.position)
                if distance < detection_radius:
                    nearby.append({
                        'vehicle': agent,
                        'distance': distance,
                        'velocity': agent.velocity,
                        'direction': agent.direction
                    })

        return nearby

    def _detect_traffic_light(self) -> Any:
        """检测附近的交通信号灯。"""
        if not self.environment or not self.environment.road_network:
            return None

        # 找到最近的交叉口
        closest_node = None
        closest_distance = float('inf')

        for node in self.environment.road_network.nodes.values():
            if node.is_intersection and node.traffic_light:
                dist = self.position.distance_to(node.position)
                if dist < closest_distance:
                    closest_distance = dist
                    closest_node = node

        if closest_node and closest_distance < 30.0:
            return closest_node.traffic_light

        return None

    def _is_safe_to_cross(self, nearby_vehicles: list[dict]) -> bool:
        """判断是否安全过马路。"""
        for v in nearby_vehicles:
            if v['distance'] < 10.0 and v['velocity'] > 5.0:
                return False
        return True

    def _distance_to_target(self) -> float:
        """计算到目标的距离。"""
        if self.target_position:
            return self.position.distance_to(self.target_position)
        return 0.0

    def _has_reached_destination(self) -> bool:
        """检查是否已到达目的地。"""
        if not self.end_position:
            return False
        return self.position.distance_to(self.end_position) < 1.0

    def _update_direction(self) -> None:
        """更新行走方向。"""
        if self.target_position:
            self.direction = (self.target_position - self.position).normalize()

    def decide(self) -> PedestrianAction:
        """
        根据感知信息做出决策。

        简单的规则式决策逻辑。
        """
        perception = self.perceive()

        # 检查是否到达目的地
        if perception['has_reached_destination']:
            return PedestrianAction.STOP

        # 如果在过马路，继续
        if self.is_crossing:
            if perception['is_safe_to_cross']:
                return PedestrianAction.WALK
            else:
                return PedestrianAction.WAIT

        # 如果在交叉口等待
        traffic_light = perception['traffic_light_state']
        if traffic_light and not traffic_light.can_pass():
            # 检查是否正在等待
            if self.pedestrian_state == PedestrianState.WAITING:
                self.wait_time += 0.1  # 假设时间步长
                if self.wait_time > self.max_wait_time:
                    # 等待太久，尝试过马路
                    if perception['is_safe_to_cross']:
                        return PedestrianAction.CROSS
            return PedestrianAction.WAIT

        # 正常情况下继续行走
        return PedestrianAction.WALK

    def act(self, action: PedestrianAction) -> None:
        """执行行人动作。"""
        if action == PedestrianAction.WALK:
            self.pedestrian_state = PedestrianState.WALKING
            self.velocity = min(
                self.velocity + self.acceleration * 0.1,
                self.max_speed
            )
        elif action == PedestrianAction.WAIT:
            self.pedestrian_state = PedestrianState.WAITING
            self.velocity = max(self.velocity - self.acceleration * 0.2, 0)
        elif action == PedestrianAction.CROSS:
            self.pedestrian_state = PedestrianState.CROSSING
            self.is_crossing = True
            self.velocity = self.max_speed * 0.8
        elif action == PedestrianAction.STOP:
            self.pedestrian_state = PedestrianState.STOPPED
            self.velocity = 0
            self.complete()

    def update(self, dt: float) -> None:
        """更新行人状态。"""
        if self.state != AgentState.ACTIVE:
            return

        # 更新位置
        if self.velocity > 0 and self.target_position:
            move_distance = self.velocity * dt
            distance_to_target = self._distance_to_target()

            if move_distance >= distance_to_target:
                # 到达当前目标点
                self.position = self.target_position.copy()
                self._advance_to_next_waypoint()
            else:
                # 继续移动
                self.position = self.position + self.direction * move_distance

    def _advance_to_next_waypoint(self) -> None:
        """前进到下一个路径点。"""
        self.route_index += 1

        if self.route_index >= len(self.route):
            # 到达终点
            self.complete()
            return

        self.target_position = self.route[self.route_index]
        self._update_direction()

        # 重置过马路状态
        if self.is_crossing:
            self.is_crossing = False
            self.wait_time = 0.0

    def activate(self) -> None:
        """激活行人。"""
        super().activate()
        self.pedestrian_state = PedestrianState.WALKING
