"""
交通管理者模块。

负责实时交通协调、指挥和监控。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from city.agents.base import BaseAgent, AgentType, AgentState

if TYPE_CHECKING:
    from city.environment.road_network import RoadNetwork, Node, Edge, TrafficLight, TrafficLightState
    from city.simulation.environment import SimulationEnvironment
    from city.agents.vehicle import Vehicle


class TrafficIncidentType(Enum):
    """交通事件类型。"""
    ACCIDENT = auto()      # 交通事故
    CONGESTION = auto()    # 拥堵
    ROADWORK = auto()      # 道路施工
    WEATHER = auto()       # 恶劣天气
    EVENT = auto()         # 大型活动


@dataclass
class TrafficIncident:
    """交通事件。"""
    incident_id: str
    incident_type: TrafficIncidentType
    location: Node
    severity: int  # 1-10，严重程度
    start_time: float
    duration: float
    description: str = ""
    is_resolved: bool = False


@dataclass
class TrafficMetrics:
    """交通指标。"""
    avg_speed: float
    density: float  # 车辆数/公里
    flow_rate: float  # 车辆数/小时
    congestion_level: float  # 0-1


class TrafficManager(BaseAgent):
    """
    交通管理者。

    负责整体交通的协调、指挥和监控，确保交通系统的平稳运行。

    职责：
    1. 实时调整交通信号灯的时长
    2. 处理事故等突发事件
    3. 发布交通信息和警告
    4. 通过交通数据（流量、速度、密度等）调整策略

    Attributes:
        control_area: 管理区域（节点列表）
        incidents: 当前活跃的事件列表
        metrics_history: 历史交通指标
    """

    def __init__(
        self,
        environment: SimulationEnvironment | None = None,
        control_area: list[Node] | None = None,
        use_llm: bool = False
    ) -> None:
        super().__init__(AgentType.TRAFFIC_MANAGER, environment, use_llm)

        self.control_area = control_area or []
        self.incidents: dict[str, TrafficIncident] = {}
        self.metrics_history: list[tuple[float, dict[str, TrafficMetrics]]] = []

        # 控制参数
        self.signal_adaptation_interval = 300.0  # 5分钟调整一次信号灯
        self.last_signal_adjustment = 0.0

        # 拥堵阈值
        self.congestion_threshold = 0.7

    def __repr__(self) -> str:
        return f"TrafficManager({self.agent_id}, area={len(self.control_area)} nodes, incidents={len(self.incidents)})"

    def add_control_node(self, node: Node) -> None:
        """添加控制节点。"""
        if node not in self.control_area:
            self.control_area.append(node)

    def report_incident(
        self,
        incident_type: TrafficIncidentType,
        location: Node,
        severity: int,
        duration: float,
        description: str = ""
    ) -> TrafficIncident:
        """
        报告交通事件。

        Args:
            incident_type: 事件类型
            location: 发生位置
            severity: 严重程度 (1-10)
            duration: 预计持续时间
            description: 描述

        Returns:
            创建的事件对象
        """
        incident_id = f"incident_{len(self.incidents) + 1}"
        incident = TrafficIncident(
            incident_id=incident_id,
            incident_type=incident_type,
            location=location,
            severity=severity,
            start_time=self.lifetime,
            duration=duration,
            description=description
        )
        self.incidents[incident_id] = incident

        # 触发应急响应
        self._handle_incident(incident)

        return incident

    def resolve_incident(self, incident_id: str) -> bool:
        """解决交通事件。"""
        if incident_id in self.incidents:
            self.incidents[incident_id].is_resolved = True
            return True
        return False

    def _handle_incident(self, incident: TrafficIncident) -> None:
        """处理交通事件。"""
        if incident.incident_type == TrafficIncidentType.ACCIDENT:
            # 事故处理：调整附近信号灯引导车流绕行
            self._adjust_signals_for_accident(incident)
        elif incident.incident_type == TrafficIncidentType.CONGESTION:
            # 拥堵处理：优化信号灯配时
            self._optimize_signals_for_congestion(incident.location)
        elif incident.incident_type == TrafficIncidentType.ROADWORK:
            # 施工处理：发布绕行建议
            pass

    def _adjust_signals_for_accident(self, incident: TrafficIncident) -> None:
        """为事故调整信号灯。"""
        # 找到事故附近的交叉口
        for node in self.control_area:
            if node.is_intersection and node.traffic_light:
                distance = node.position.distance_to(incident.location.position)
                if distance < 500:  # 500米范围内
                    # 延长绿灯时间，疏导车流
                    node.traffic_light.green_duration = min(
                        node.traffic_light.green_duration + 10,
                        60
                    )

    def perceive(self) -> dict[str, Any]:
        """
        感知交通状况。

        Returns:
            交通状况信息字典
        """
        perception = {
            'time': self.lifetime,
            'node_metrics': {},
            'active_incidents': list(self.incidents.values()),
            'system_status': 'normal'
        }

        # 收集各节点的交通指标
        for node in self.control_area:
            metrics = self._calculate_node_metrics(node)
            perception['node_metrics'][node.node_id] = metrics

        # 判断整体交通状况
        avg_congestion = sum(m.congestion_level for m in perception['node_metrics'].values()) / len(perception['node_metrics']) if perception['node_metrics'] else 0

        if avg_congestion > self.congestion_threshold:
            perception['system_status'] = 'congested'
        elif avg_congestion > 0.4:
            perception['system_status'] = 'busy'

        return perception

    def _calculate_node_metrics(self, node: Node) -> TrafficMetrics:
        """计算节点的交通指标。"""
        if not self.environment:
            return TrafficMetrics(0, 0, 0, 0)

        # 收集通过该节点的车辆
        vehicles: list[Vehicle] = []
        for agent in self.environment.agents.values():
            from city.agents.vehicle import Vehicle
            if isinstance(agent, Vehicle):
                # 检查车辆是否在节点附近
                if agent.current_edge and (agent.current_edge.from_node == node or agent.current_edge.to_node == node):
                    vehicles.append(agent)

        if not vehicles:
            return TrafficMetrics(0, 0, 0, 0)

        # 计算指标
        avg_speed = sum(v.velocity for v in vehicles) / len(vehicles)
        density = len(vehicles) / 0.5  # 假设500米范围

        # 计算流量（简化）
        flow_rate = avg_speed * density * 3.6  # 转换为车辆/小时

        # 计算拥堵程度（基于平均速度）
        max_speed = 13.89  # 50 km/h
        congestion_level = max(0, 1 - avg_speed / max_speed)

        return TrafficMetrics(avg_speed, density, flow_rate, congestion_level)

    def decide(self) -> dict[str, Any]:
        """
        做出交通管理决策。

        Returns:
            决策动作字典
        """
        perception = self.perceive()
        decisions = {
            'adjust_signals': False,
            'signal_adjustments': {},
            'publish_warning': False,
            'warning_message': ''
        }

        # 检查是否需要调整信号灯
        if self.lifetime - self.last_signal_adjustment >= self.signal_adaptation_interval:
            decisions['adjust_signals'] = True

        # 检查拥堵情况
        congested_nodes = [
            node_id for node_id, metrics in perception['node_metrics'].items()
            if metrics.congestion_level > self.congestion_threshold
        ]

        if congested_nodes:
            decisions['publish_warning'] = True
            decisions['warning_message'] = f"以下区域拥堵: {', '.join(congested_nodes)}"

            # 为拥堵节点生成信号灯调整方案
            if decisions['adjust_signals']:
                for node_id in congested_nodes:
                    decisions['signal_adjustments'][node_id] = {
                        'green_extension': 15,
                        'cycle_reduction': 10
                    }

        return decisions

    def act(self, action: dict[str, Any]) -> None:
        """执行交通管理动作。"""
        # 调整信号灯
        if action.get('adjust_signals'):
            adjustments = action.get('signal_adjustments', {})
            for node_id, adj in adjustments.items():
                node = self._get_node_by_id(node_id)
                if node and node.traffic_light:
                    # 延长绿灯时间
                    node.traffic_light.green_duration += adj.get('green_extension', 0)
                    # 缩短周期
                    node.traffic_light.cycle_time -= adj.get('cycle_reduction', 0)

            self.last_signal_adjustment = self.lifetime

        # 发布警告
        if action.get('publish_warning'):
            self._publish_warning(action['warning_message'])

    def _get_node_by_id(self, node_id: str) -> Node | None:
        """根据ID获取节点。"""
        for node in self.control_area:
            if node.node_id == node_id:
                return node
        return None

    def _publish_warning(self, message: str) -> None:
        """发布交通警告。"""
        # 简化实现：打印到日志
        print(f"[交通警告] {message}")

    def _optimize_signals_for_congestion(self, location: Node) -> None:
        """针对拥堵优化信号灯。"""
        # 找到附近的交叉口并优化
        for node in self.control_area:
            if node.is_intersection and node.traffic_light:
                distance = node.position.distance_to(location.position)
                if distance < 300:
                    # 增加绿灯时间
                    node.traffic_light.green_duration = min(
                        node.traffic_light.green_duration * 1.2,
                        45
                    )

    def update(self, dt: float) -> None:
        """更新交通管理者状态。"""
        # 清理已解决的事件
        resolved = [k for k, v in self.incidents.items() if v.is_resolved]
        for k in resolved:
            del self.incidents[k]

        # 定期记录交通指标
        if int(self.lifetime) % 60 == 0:  # 每分钟记录
            perception = self.perceive()
            self.metrics_history.append((self.lifetime, perception['node_metrics']))

    def get_traffic_report(self) -> dict[str, Any]:
        """
        生成交通状况报告。

        Returns:
            交通报告字典
        """
        perception = self.perceive()

        return {
            'timestamp': self.lifetime,
            'system_status': perception['system_status'],
            'active_incidents': len(self.incidents),
            'avg_congestion': sum(m.congestion_level for m in perception['node_metrics'].values()) / len(perception['node_metrics']) if perception['node_metrics'] else 0,
            'node_details': perception['node_metrics']
        }
