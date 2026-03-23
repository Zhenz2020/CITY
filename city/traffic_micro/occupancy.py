"""车道占用快照。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from city.agents.vehicle import Vehicle
    from city.environment.road_network import Lane, RoadNetwork


@dataclass(slots=True)
class TrafficSnapshot:
    """按车道缓存车辆顺序，供单步查询使用。"""

    lane_vehicles: dict[str, list[Any]]

    @classmethod
    def build(cls, road_network: "RoadNetwork") -> "TrafficSnapshot":
        lane_vehicles: dict[str, list[Any]] = {}
        for edge in road_network.edges.values():
            for lane in edge.lanes:
                ordered = sorted(
                    lane.vehicles,
                    key=lambda vehicle: getattr(vehicle, "distance_on_edge", 0.0),
                )
                lane_vehicles[lane.lane_id] = ordered
        return cls(lane_vehicles=lane_vehicles)

    def get_lane_vehicles(self, lane: "Lane | None") -> list[Any]:
        if lane is None:
            return []
        return self.lane_vehicles.get(lane.lane_id, [])

    def get_leader(self, vehicle: "Vehicle", lane: "Lane | None" = None) -> tuple[Any | None, float | None]:
        target_lane = lane or vehicle.current_lane
        candidates = self.get_lane_vehicles(target_lane)
        for other in candidates:
            if other is vehicle:
                continue
            if other.distance_on_edge > vehicle.distance_on_edge:
                gap = other.distance_on_edge - vehicle.distance_on_edge - getattr(other, "length", 0.0)
                return other, max(0.0, gap)
        return None, None

    def get_follower(self, vehicle: "Vehicle", lane: "Lane | None" = None) -> tuple[Any | None, float | None]:
        target_lane = lane or vehicle.current_lane
        candidates = reversed(self.get_lane_vehicles(target_lane))
        for other in candidates:
            if other is vehicle:
                continue
            if other.distance_on_edge < vehicle.distance_on_edge:
                gap = vehicle.distance_on_edge - other.distance_on_edge - vehicle.length
                return other, max(0.0, gap)
        return None, None

    def get_adjacent_neighbors(self, vehicle: "Vehicle", side: str) -> dict[str, tuple[Any | None, float | None]]:
        if not vehicle.current_lane:
            return {"leader": (None, None), "follower": (None, None)}
        target_lane = vehicle.current_lane.left_lane if side == "left" else vehicle.current_lane.right_lane
        return {
            "leader": self.get_leader(vehicle, lane=target_lane),
            "follower": self.get_follower(vehicle, lane=target_lane),
        }
