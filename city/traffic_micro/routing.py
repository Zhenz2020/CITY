"""边级路径规划。"""

from __future__ import annotations

from city.traffic_micro.types import RoutePlan


class RoutingEngine:
    """第一期边级路径规划器。"""

    def plan_route(self, road_network, start_node, end_node) -> RoutePlan | None:
        nodes = road_network.find_shortest_path(start_node, end_node)
        if not nodes:
            return None

        edge_ids: list[str] = []
        desired_lane_indices_by_edge: dict[str, int] = {}
        for from_node, to_node in zip(nodes[:-1], nodes[1:]):
            edge = road_network.get_edge_between(from_node, to_node)
            if edge is None:
                return None
            edge_ids.append(edge.edge_id)
            desired_lane_indices_by_edge[edge.edge_id] = self._recommend_lane_index(edge)

        return RoutePlan(
            nodes=[node.node_id for node in nodes],
            edges=edge_ids,
            desired_lane_indices_by_edge=desired_lane_indices_by_edge,
        )

    def _recommend_lane_index(self, edge) -> int:
        if not edge.lanes:
            return 0
        return min(len(edge.lanes) - 1, max(0, len(edge.lanes) // 2))
