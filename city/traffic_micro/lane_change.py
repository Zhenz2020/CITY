"""规则化变道模型。"""

from __future__ import annotations

from city.traffic_micro.types import LaneChangeContext, LaneChangeDecision, LaneChangeDesire


class RuleBasedLaneChangeModel:
    """第一期规则变道模型。"""

    def __init__(
        self,
        min_front_gap_factor: float = 1.5,
        min_rear_gap_factor: float = 1.2,
        desire_threshold: float = 0.3,
    ) -> None:
        self.min_front_gap_factor = min_front_gap_factor
        self.min_rear_gap_factor = min_rear_gap_factor
        self.desire_threshold = desire_threshold

    def decide(self, ctx: LaneChangeContext) -> LaneChangeDecision:
        left = self._evaluate_side(ctx, side="left")
        right = self._evaluate_side(ctx, side="right")
        candidates = [c for c in (left, right) if c.should_change]
        if not candidates:
            return LaneChangeDecision(False)
        return max(candidates, key=lambda item: item.urgency)

    def _evaluate_side(self, ctx: LaneChangeContext, side: str) -> LaneChangeDecision:
        target_lane_index = ctx.current_lane_index + (-1 if side == "left" else 1)
        if target_lane_index < 0 or target_lane_index >= ctx.lane_count:
            return LaneChangeDecision(False)

        front_gap = ctx.left_front_gap if side == "left" else ctx.right_front_gap
        front_speed = ctx.left_front_speed if side == "left" else ctx.right_front_speed
        rear_gap = ctx.left_rear_gap if side == "left" else ctx.right_rear_gap
        rear_speed = ctx.left_rear_speed if side == "left" else ctx.right_rear_speed

        if not self._is_safe(ctx, front_gap, rear_gap, rear_speed):
            return LaneChangeDecision(False)

        desire = LaneChangeDesire()
        current_front_gap = ctx.front_gap if ctx.front_gap is not None else float("inf")
        target_front_gap = front_gap if front_gap is not None else float("inf")
        current_front_speed = ctx.front_speed if ctx.front_speed is not None else ctx.desired_speed
        target_front_speed = front_speed if front_speed is not None else ctx.desired_speed

        if target_front_gap > current_front_gap + max(5.0, ctx.ego_speed * 0.5):
            desire.speed_gain += 0.4
        if target_front_speed > current_front_speed + 1.0:
            desire.speed_gain += 0.3

        if ctx.target_lane_index is not None and target_lane_index == ctx.target_lane_index:
            strategic_factor = 1.0
            if ctx.distance_to_lane_end < 40:
                strategic_factor = 1.5
            desire.strategic += 0.5 * strategic_factor

        if side == "right" and ctx.target_lane_index is None:
            desire.keep_right += 0.2

        if desire.total < self.desire_threshold:
            return LaneChangeDecision(False)

        reason_parts: list[str] = []
        if desire.strategic > 0:
            reason_parts.append("strategic")
        if desire.speed_gain > 0:
            reason_parts.append("speed_gain")
        if desire.keep_right > 0:
            reason_parts.append("keep_right")

        return LaneChangeDecision(
            should_change=True,
            target_side=side,
            target_lane_index=target_lane_index,
            reason="+".join(reason_parts),
            urgency=desire.total,
        )

    def _is_safe(
        self,
        ctx: LaneChangeContext,
        front_gap: float | None,
        rear_gap: float | None,
        rear_speed: float | None,
    ) -> bool:
        min_front_gap = max(ctx.min_gap * self.min_front_gap_factor, ctx.ego_speed * ctx.reaction_time)
        if front_gap is not None and front_gap < min_front_gap:
            return False

        rear_required_gap = ctx.min_gap * self.min_rear_gap_factor
        if rear_speed is not None and rear_speed > ctx.ego_speed:
            rear_required_gap += (rear_speed - ctx.ego_speed) * ctx.reaction_time
        if rear_gap is not None and rear_gap < rear_required_gap:
            return False
        return True
