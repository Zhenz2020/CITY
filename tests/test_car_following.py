from city.traffic_micro.car_following import IDMCarFollowingModel
from city.traffic_micro.types import CarFollowingContext


def test_idm_accelerates_on_free_road():
    model = IDMCarFollowingModel()
    ctx = CarFollowingContext(
        ego_speed=5.0,
        ego_max_speed=30.0,
        speed_limit=20.0,
        desired_speed=20.0,
        reaction_time=1.0,
        min_gap=2.0,
        max_acceleration=2.5,
        comfortable_deceleration=4.5,
    )

    assert model.compute_acceleration(ctx) > 0


def test_idm_brakes_when_gap_is_small():
    model = IDMCarFollowingModel()
    ctx = CarFollowingContext(
        ego_speed=15.0,
        ego_max_speed=30.0,
        speed_limit=20.0,
        desired_speed=20.0,
        reaction_time=1.0,
        min_gap=2.0,
        max_acceleration=2.5,
        comfortable_deceleration=4.5,
        leader_gap=5.0,
        leader_speed=5.0,
    )

    assert model.compute_acceleration(ctx) < 0
