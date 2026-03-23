from city.traffic_micro.lane_change import RuleBasedLaneChangeModel
from city.traffic_micro.types import LaneChangeContext


def test_lane_change_prefers_faster_left_lane():
    model = RuleBasedLaneChangeModel()
    ctx = LaneChangeContext(
        ego_speed=10.0,
        desired_speed=18.0,
        min_gap=2.0,
        reaction_time=1.0,
        current_lane_index=1,
        lane_count=3,
        distance_to_lane_end=120.0,
        front_gap=8.0,
        front_speed=7.0,
        left_front_gap=30.0,
        left_front_speed=15.0,
        left_rear_gap=20.0,
        left_rear_speed=9.0,
        target_lane_index=0,
    )

    decision = model.decide(ctx)
    assert decision.should_change
    assert decision.target_side == "left"


def test_lane_change_rejects_unsafe_rear_gap():
    model = RuleBasedLaneChangeModel()
    ctx = LaneChangeContext(
        ego_speed=10.0,
        desired_speed=18.0,
        min_gap=2.0,
        reaction_time=1.0,
        current_lane_index=0,
        lane_count=2,
        distance_to_lane_end=120.0,
        front_gap=8.0,
        front_speed=7.0,
        right_front_gap=30.0,
        right_front_speed=15.0,
        right_rear_gap=2.0,
        right_rear_speed=18.0,
    )

    decision = model.decide(ctx)
    assert not decision.should_change
