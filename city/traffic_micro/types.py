"""微观交通公共类型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NeighborRef:
    """邻车引用信息。"""

    vehicle: object | None
    distance: float | None


@dataclass(slots=True)
class CarFollowingContext:
    """跟驰模型输入。"""

    ego_speed: float
    ego_max_speed: float
    speed_limit: float
    desired_speed: float
    reaction_time: float
    min_gap: float
    max_acceleration: float
    comfortable_deceleration: float
    leader_gap: float | None = None
    leader_speed: float | None = None


@dataclass(slots=True)
class LaneChangeContext:
    """变道模型输入。"""

    ego_speed: float
    desired_speed: float
    min_gap: float
    reaction_time: float
    current_lane_index: int
    lane_count: int
    distance_to_lane_end: float
    front_gap: float | None
    front_speed: float | None
    left_front_gap: float | None = None
    left_front_speed: float | None = None
    left_rear_gap: float | None = None
    left_rear_speed: float | None = None
    right_front_gap: float | None = None
    right_front_speed: float | None = None
    right_rear_gap: float | None = None
    right_rear_speed: float | None = None
    target_lane_index: int | None = None


@dataclass(slots=True)
class LaneChangeDesire:
    """变道动机得分。"""

    strategic: float = 0.0
    speed_gain: float = 0.0
    cooperative: float = 0.0
    keep_right: float = 0.0

    @property
    def total(self) -> float:
        return self.strategic + self.speed_gain + self.cooperative + self.keep_right


@dataclass(slots=True)
class LaneChangeDecision:
    """变道决策结果。"""

    should_change: bool
    target_side: str | None = None
    target_lane_index: int | None = None
    reason: str = ""
    urgency: float = 0.0


@dataclass(slots=True)
class RoutePlan:
    """边级路径规划结果。"""

    nodes: list[str] = field(default_factory=list)
    edges: list[str] = field(default_factory=list)
    desired_lane_indices_by_edge: dict[str, int] = field(default_factory=dict)
