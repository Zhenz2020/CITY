"""
交通规划者模块。

负责长远的交通规划，包括道路建设、公共交通路线设计等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from city.agents.base import BaseAgent, AgentType, AgentState

if TYPE_CHECKING:
    from city.environment.road_network import RoadNetwork, Node, Edge
    from city.simulation.environment import SimulationEnvironment


@dataclass
class PlanningProposal:
    """规划提案。"""
    proposal_id: str
    proposal_type: str  # 'new_road', 'new_bus_route', 'intersection_upgrade'等
    description: str
    estimated_cost: float
    estimated_benefit: float  # 预期效益评分
    target_area: list[Node] = field(default_factory=list)
    is_approved: bool = False
    implementation_time: float = 0.0


@dataclass
class HistoricalData:
    """历史数据记录。"""
    timestamp: float
    traffic_volume: dict[str, float]  # 路段ID -> 流量
    avg_speed: dict[str, float]       # 路段ID -> 平均速度
    congestion_events: int


class TrafficPlanner(BaseAgent):
    """
    交通规划者。

    负责长远的交通规划，包括道路建设、公共交通路线的设计等。

    职责：
    1. 进行道路建设规划、公共交通路线设计和优化
    2. 通过历史数据和交通预测，对现有交通网络进行评估
    3. 分析哪些地区需要新增道路或公交站点
    4. 模拟不同规划方案并评估效果

    Attributes:
        planning_horizon: 规划时间跨度（天）
        data_collection_period: 数据收集周期（秒）
        historical_data: 历史交通数据
        proposals: 规划提案列表
    """

    def __init__(
        self,
        environment: SimulationEnvironment | None = None,
        planning_horizon: float = 365.0,
        use_llm: bool = False
    ) -> None:
        super().__init__(AgentType.TRAFFIC_PLANNER, environment, use_llm)

        self.planning_horizon = planning_horizon
        self.data_collection_period = 3600.0  # 每小时收集一次数据
        self.last_data_collection = 0.0

        self.historical_data: list[HistoricalData] = []
        self.proposals: dict[str, PlanningProposal] = {}

        # 规划参数
        self.congestion_threshold = 0.6
        self.min_traffic_volume_for_new_road = 1000  # 最小流量阈值

    def __repr__(self) -> str:
        return f"TrafficPlanner({self.agent_id}, proposals={len(self.proposals)}, data_points={len(self.historical_data)})"

    def perceive(self) -> dict[str, Any]:
        """
        收集规划所需信息。

        Returns:
            感知信息字典
        """
        perception = {
            'current_time': self.lifetime,
            'network_state': self._analyze_network_state(),
            'historical_trends': self._analyze_historical_trends(),
            'bottlenecks': self._identify_bottlenecks(),
            'growth_areas': self._identify_growth_areas()
        }

        return perception

    def _analyze_network_state(self) -> dict[str, Any]:
        """分析当前网络状态。"""
        if not self.environment or not self.environment.road_network:
            return {}

        state = {
            'total_edges': len(self.environment.road_network.edges),
            'total_nodes': len(self.environment.road_network.nodes),
            'avg_edge_utilization': 0.0,
            'edge_utilization': {}
        }

        # 计算各路段利用率
        total_utilization = 0.0
        for edge_id, edge in self.environment.road_network.edges.items():
            # 简化：根据车辆数估算
            vehicle_count = sum(len(lane.vehicles) for lane in edge.lanes)
            utilization = min(vehicle_count / 20, 1.0)  # 假设最大容量20辆车
            state['edge_utilization'][edge_id] = utilization
            total_utilization += utilization

        if state['total_edges'] > 0:
            state['avg_edge_utilization'] = total_utilization / state['total_edges']

        return state

    def _analyze_historical_trends(self) -> dict[str, Any]:
        """分析历史趋势。"""
        if len(self.historical_data) < 2:
            return {'trend': 'insufficient_data'}

        # 计算平均流量变化趋势
        recent_data = self.historical_data[-24:]  # 最近24个数据点
        if len(recent_data) < 2:
            return {'trend': 'stable'}

        # 简化：检查总体流量变化
        avg_volumes = []
        for data in recent_data:
            if data.traffic_volume:
                avg_vol = sum(data.traffic_volume.values()) / len(data.traffic_volume)
                avg_volumes.append(avg_vol)

        if len(avg_volumes) >= 2:
            trend = 'increasing' if avg_volumes[-1] > avg_volumes[0] * 1.1 else \
                    'decreasing' if avg_volumes[-1] < avg_volumes[0] * 0.9 else 'stable'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'data_points': len(self.historical_data),
            'avg_volume_change': (avg_volumes[-1] - avg_volumes[0]) / avg_volumes[0] if len(avg_volumes) >= 2 and avg_volumes[0] > 0 else 0
        }

    def _identify_bottlenecks(self) -> list[dict[str, Any]]:
        """识别交通瓶颈。"""
        bottlenecks = []

        network_state = self._analyze_network_state()
        for edge_id, utilization in network_state.get('edge_utilization', {}).items():
            if utilization > self.congestion_threshold:
                edge = self.environment.road_network.get_edge(edge_id) if self.environment else None
                if edge:
                    bottlenecks.append({
                        'edge_id': edge_id,
                        'from_node': edge.from_node.node_id,
                        'to_node': edge.to_node.node_id,
                        'utilization': utilization,
                        'severity': 'high' if utilization > 0.8 else 'medium'
                    })

        return sorted(bottlenecks, key=lambda x: x['utilization'], reverse=True)

    def _identify_growth_areas(self) -> list[Node]:
        """识别潜在增长区域。"""
        # 简化实现：返回流量增长最快的区域
        growth_areas = []

        if len(self.historical_data) >= 2:
            recent = self.historical_data[-1]
            older = self.historical_data[0]

            for edge_id, recent_vol in recent.traffic_volume.items():
                old_vol = older.traffic_volume.get(edge_id, 0)
                if old_vol > 0 and recent_vol / old_vol > 1.5:  # 增长50%以上
                    edge = self.environment.road_network.get_edge(edge_id) if self.environment else None
                    if edge and edge.to_node not in growth_areas:
                        growth_areas.append(edge.to_node)

        return growth_areas

    def decide(self) -> list[PlanningProposal]:
        """
        生成规划提案。

        Returns:
            规划提案列表
        """
        perception = self.perceive()
        proposals = []

        # 根据瓶颈提出改进方案
        bottlenecks = perception['bottlenecks']
        for bottleneck in bottlenecks[:3]:  # 处理前3个瓶颈
            proposal = self._generate_road_expansion_proposal(bottleneck)
            if proposal:
                proposals.append(proposal)

        # 根据增长区域提出新道路建议
        growth_areas = perception['growth_areas']
        if len(growth_areas) >= 2:
            proposal = self._generate_new_road_proposal(growth_areas)
            if proposal:
                proposals.append(proposal)

        # 根据历史趋势提出公交路线建议
        trends = perception['historical_trends']
        if trends.get('trend') == 'increasing':
            proposal = self._generate_bus_route_proposal()
            if proposal:
                proposals.append(proposal)

        return proposals

    def _generate_road_expansion_proposal(self, bottleneck: dict[str, Any]) -> PlanningProposal | None:
        """生成道路扩建提案。"""
        proposal_id = f"proposal_{len(self.proposals) + 1}"

        return PlanningProposal(
            proposal_id=proposal_id,
            proposal_type='road_expansion',
            description=f"扩建路段 {bottleneck['edge_id']}，增加车道数以缓解拥堵",
            estimated_cost=1000000.0,  # 假设成本
            estimated_benefit=bottleneck['utilization'] * 10,
            target_area=[self.environment.road_network.get_edge(bottleneck['edge_id']).from_node] if self.environment else []
        )

    def _generate_new_road_proposal(self, growth_areas: list[Node]) -> PlanningProposal | None:
        """生成新建道路提案。"""
        proposal_id = f"proposal_{len(self.proposals) + 1}"

        return PlanningProposal(
            proposal_id=proposal_id,
            proposal_type='new_road',
            description=f"在增长区域之间建设新道路，连接 {len(growth_areas)} 个关键节点",
            estimated_cost=5000000.0,
            estimated_benefit=8.0,
            target_area=growth_areas
        )

    def _generate_bus_route_proposal(self) -> PlanningProposal | None:
        """生成公交路线提案。"""
        proposal_id = f"proposal_{len(self.proposals) + 1}"

        return PlanningProposal(
            proposal_id=proposal_id,
            proposal_type='new_bus_route',
            description="新增公交线路以缓解交通压力",
            estimated_cost=500000.0,
            estimated_benefit=7.0
        )

    def act(self, action: list[PlanningProposal]) -> None:
        """执行规划动作（保存提案）。"""
        for proposal in action:
            if proposal.proposal_id not in self.proposals:
                self.proposals[proposal.proposal_id] = proposal
                print(f"[规划提案] 生成新提案: {proposal.description}")

    def update(self, dt: float) -> None:
        """更新规划者状态，收集数据。"""
        # 定期收集历史数据
        if self.lifetime - self.last_data_collection >= self.data_collection_period:
            self._collect_historical_data()
            self.last_data_collection = self.lifetime

    def _collect_historical_data(self) -> None:
        """收集当前交通数据。"""
        if not self.environment or not self.environment.road_network:
            return

        traffic_volume = {}
        avg_speed = {}

        # 收集各路段数据
        for edge_id, edge in self.environment.road_network.edges.items():
            vehicle_count = sum(len(lane.vehicles) for lane in edge.lanes)
            traffic_volume[edge_id] = vehicle_count

            # 计算平均速度
            total_speed = 0.0
            total_vehicles = 0
            for agent in self.environment.agents.values():
                from city.agents.vehicle import Vehicle
                if isinstance(agent, Vehicle) and agent.current_edge == edge:
                    total_speed += agent.velocity
                    total_vehicles += 1

            avg_speed[edge_id] = total_speed / total_vehicles if total_vehicles > 0 else 0

        # 统计拥堵事件
        congestion_events = sum(1 for v in traffic_volume.values() if v > 15)

        data = HistoricalData(
            timestamp=self.lifetime,
            traffic_volume=traffic_volume,
            avg_speed=avg_speed,
            congestion_events=congestion_events
        )

        self.historical_data.append(data)

        # 限制历史数据大小
        if len(self.historical_data) > 168:  # 保留最近一周的数据（每小时一个点）
            self.historical_data = self.historical_data[-168:]

    def evaluate_proposal(self, proposal_id: str) -> dict[str, Any]:
        """
        评估规划提案的效果。

        Args:
            proposal_id: 提案ID

        Returns:
            评估结果字典
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {'error': '提案不存在'}

        # 简化评估
        cost_benefit_ratio = proposal.estimated_benefit / (proposal.estimated_cost / 1000000)

        return {
            'proposal_id': proposal_id,
            'cost_benefit_ratio': cost_benefit_ratio,
            'recommendation': 'approve' if cost_benefit_ratio > 0.5 else 'reject',
            'priority': 'high' if cost_benefit_ratio > 1.0 else 'medium' if cost_benefit_ratio > 0.5 else 'low'
        }

    def get_planning_report(self) -> dict[str, Any]:
        """
        生成规划报告。

        Returns:
            规划报告字典
        """
        perception = self.perceive()

        return {
            'timestamp': self.lifetime,
            'planning_horizon_days': self.planning_horizon,
            'data_points_collected': len(self.historical_data),
            'active_proposals': len(self.proposals),
            'bottlenecks_identified': len(perception['bottlenecks']),
            'growth_areas': len(perception['growth_areas']),
            'traffic_trend': perception['historical_trends'].get('trend', 'unknown'),
            'top_bottlenecks': perception['bottlenecks'][:5]
        }
