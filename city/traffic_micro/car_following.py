"""跟驰模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from city.traffic_micro.types import CarFollowingContext


class BaseCarFollowingModel(ABC):
    """跟驰模型抽象基类。"""

    @abstractmethod
    def compute_acceleration(self, ctx: CarFollowingContext) -> float:
        """计算期望加速度。"""


class IDMCarFollowingModel(BaseCarFollowingModel):
    """简化版 IDM 跟驰模型。"""

    def __init__(self, delta: float = 4.0) -> None:
        self.delta = delta

    def compute_acceleration(self, ctx: CarFollowingContext) -> float:
        target_speed = max(0.1, min(ctx.desired_speed, ctx.ego_max_speed, ctx.speed_limit))
        free_road_term = (ctx.ego_speed / target_speed) ** self.delta

        if ctx.leader_gap is None or ctx.leader_speed is None:
            return ctx.max_acceleration * (1.0 - free_road_term)

        gap = max(0.1, ctx.leader_gap)
        closing_speed = ctx.ego_speed - ctx.leader_speed
        desired_gap = (
            ctx.min_gap
            + max(
                0.0,
                ctx.ego_speed * ctx.reaction_time
                + (ctx.ego_speed * closing_speed)
                / max(0.1, 2.0 * (ctx.max_acceleration * ctx.comfortable_deceleration) ** 0.5),
            )
        )
        interaction_term = (desired_gap / gap) ** 2
        return ctx.max_acceleration * (1.0 - free_road_term - interaction_term)
