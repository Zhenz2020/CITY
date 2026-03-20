"""
红绿灯智能体 - 使用LLM智能控制交通信号灯。

根据实时交通流量，动态优化信号灯配时，减少拥堵。
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, TYPE_CHECKING

from city.agents.base import BaseAgent, AgentType, AgentState
from city.environment.road_network import TrafficLightState

if TYPE_CHECKING:
    from city.environment.road_network import Node, TrafficLight
    from city.simulation.environment import SimulationEnvironment


class SignalPhase(Enum):
    """
    信号灯相位 - 双相位系统。
    
    采用横纵分离的双相位设计，从根本上防止路口死锁：
    - 纵向相位: 南北方向同时绿灯，东西方向红灯
    - 横向相位: 东西方向同时绿灯，南北方向红灯
    - 这样就不会有横向和纵向车辆同时进入路口
    """
    NS_GREEN = auto()   # 南北绿灯（东西红灯）- 纵向通行
    NS_YELLOW = auto()  # 南北黄灯（东西红灯）- 纵向清空
    ALL_RED_1 = auto()  # 全红灯过渡1
    EW_GREEN = auto()   # 东西绿灯（南北红灯）- 横向通行
    EW_YELLOW = auto()  # 东西黄灯（南北红灯）- 横向清空
    ALL_RED_2 = auto()  # 全红灯过渡2


class TrafficLightAgent(BaseAgent):
    """
    红绿灯智能体。
    
    通过LLM分析各方向车流量，动态调整信号灯配时。
    
    Attributes:
        control_node: 控制的交叉口节点
        traffic_light: 信号灯对象
        current_phase: 当前信号灯相位
        phase_timer: 当前相位持续时间
        detection_range: 检测范围（米）
    """

    def __init__(
        self,
        control_node: Node,
        environment: SimulationEnvironment | None = None,
        use_llm: bool = True,
        name: str = "智能红绿灯",
        enable_memory: bool = True
    ) -> None:
        super().__init__(AgentType.TRAFFIC_MANAGER, environment, use_llm, enable_memory=enable_memory, memory_capacity=40)
        self.control_node = control_node
        self.traffic_light = control_node.traffic_light
        self.name = name
        
        # 状态管理
        self.current_phase = SignalPhase.NS_GREEN
        self.phase_timer = 0.0
        self.min_green_time = 10.0    # 最小绿灯时间
        self.max_green_time = 60.0    # 最大绿灯时间
        self.yellow_time = 5.0        # 黄灯时间
        self.all_red_time = 2.0       # 全红灯过渡时间
        
        # 检测范围
        self.detection_range = 100.0
        
        # 历史数据（用于LLM决策）
        self.history: list[dict] = []
        self.max_history = 10
        
        # 上次决策时间
        self.last_decision_time = 0.0
        self.decision_cooldown = 5.0  # 决策冷却时间

    def __repr__(self) -> str:
        return f"TrafficLightAgent({self.name}, phase={self.current_phase.name}, timer={self.phase_timer:.1f}s)"

    def perceive(self) -> dict[str, Any]:
        """
        感知交叉口各方向交通状况。
        
        Returns:
            包含各方向车辆数、排队长度、平均速度等信息
        """
        perception = {
            'node_id': self.control_node.node_id,
            'node_name': self.control_node.name,
            'current_phase': self.current_phase.name,
            'phase_timer': self.phase_timer,
            'current_light_state': self.traffic_light.state.name if self.traffic_light else 'UNKNOWN',
            'directions': {},
            'total_vehicles': 0,
            'suggested_action': None
        }

        if not self.environment:
            return perception

        # 检测四个方向的车辆
        directions = {
            'NORTH': {'incoming_edges': [], 'opposite': 'SOUTH'},
            'SOUTH': {'incoming_edges': [], 'opposite': 'NORTH'},
            'EAST': {'incoming_edges': [], 'opposite': 'WEST'},
            'WEST': {'incoming_edges': [], 'opposite': 'EAST'},
        }

        # 收集进入交叉口的所有路段
        for edge in self.control_node.incoming_edges:
            from_node = edge.from_node
            dx = self.control_node.position.x - from_node.position.x
            dy = self.control_node.position.y - from_node.position.y
            
            # 判断方向（简化版）
            if abs(dx) > abs(dy):
                direction = 'EAST' if dx > 0 else 'WEST'
            else:
                direction = 'NORTH' if dy > 0 else 'SOUTH'
            
            directions[direction]['incoming_edges'].append(edge)

        # 统计各方向车辆
        ns_count = 0
        ew_count = 0
        
        for direction_name, direction_data in directions.items():
            vehicle_count = 0
            queue_length = 0
            avg_speed = 0.0
            waiting_vehicles = 0
            
            for edge in direction_data['incoming_edges']:
                for lane in edge.lanes:
                    for vehicle in lane.vehicles:
                        # 只统计检测范围内的车辆
                        dist_to_intersection = edge.length - vehicle.distance_on_edge
                        if dist_to_intersection < self.detection_range:
                            vehicle_count += 1
                            avg_speed += vehicle.velocity
                            
                            # 判断是否排队（距离路口小于30m且速度低）
                            if dist_to_intersection < 30 and vehicle.velocity < 2:
                                queue_length += 1
                                waiting_vehicles += 1
            
            if vehicle_count > 0:
                avg_speed /= vehicle_count
            
            direction_data['vehicle_count'] = vehicle_count
            direction_data['queue_length'] = queue_length
            direction_data['avg_speed'] = round(avg_speed, 2)
            direction_data['waiting_vehicles'] = waiting_vehicles
            
            perception['directions'][direction_name] = {
                'vehicle_count': vehicle_count,
                'queue_length': queue_length,
                'avg_speed': round(avg_speed, 2),
                'waiting_vehicles': waiting_vehicles
            }
            
            # 统计南北/东西总流量
            if direction_name in ['NORTH', 'SOUTH']:
                ns_count += vehicle_count
            else:
                ew_count += vehicle_count
            
            perception['total_vehicles'] += vehicle_count

        # 计算流量比，给出建议
        if ns_count + ew_count > 0:
            ns_ratio = ns_count / (ns_count + ew_count)
            ew_ratio = ew_count / (ns_count + ew_count)
            
            perception['ns_ratio'] = round(ns_ratio, 2)
            perception['ew_ratio'] = round(ew_ratio, 2)
            
            # 双相位系统建议
            current_is_ns = self.current_phase in [SignalPhase.NS_GREEN, SignalPhase.NS_YELLOW]
            current_is_ew = self.current_phase in [SignalPhase.EW_GREEN, SignalPhase.EW_YELLOW]
            
            if current_is_ns and ew_count > ns_count * 1.5:
                perception['suggested_action'] = 'switch_to_ew'  # 切换到横向相位
            elif current_is_ew and ns_count > ew_count * 1.5:
                perception['suggested_action'] = 'switch_to_ns'  # 切换到纵向相位
            elif queue_length > 5:
                perception['suggested_action'] = 'switch_phase'
            else:
                perception['suggested_action'] = 'maintain'
        
        # 添加双相位系统状态
        perception['active_direction'] = 'NS' if self.current_phase in [SignalPhase.NS_GREEN, SignalPhase.NS_YELLOW] else 'EW' if self.current_phase in [SignalPhase.EW_GREEN, SignalPhase.EW_YELLOW] else 'NONE'
        perception['is_green'] = 'GREEN' in self.current_phase.name

        return perception

    def decide(self) -> dict[str, Any]:
        """
        决定信号灯动作 - 全LLM智能模式。
        
        策略：
        - 只要检测到路口有车辆，就使用LLM智能决策
        - 无车辆时使用固定周期
        - 所有车辆智能体都通过LLM做决策
        """
        current_time = self.environment.current_time if self.environment else 0
        if int(current_time) % 5 == 0:
            self.record_perception(self.perceive(), importance=2.0)
        
        # 决策冷却（但如果有车辆等待可能需要立即决策）
        if current_time - self.last_decision_time < self.decision_cooldown:
            # 检查是否有车辆在等待
            perception = self.perceive()
            total_vehicles = perception.get('total_vehicles', 0)
            if total_vehicles == 0:
                return {'action': 'maintain', 'reason': '冷却中且无车辆', 'mode': 'fixed_cycle'}
            # 有车辆时继续，尝试做决策
        else:
            perception = self.perceive()
            total_vehicles = perception.get('total_vehicles', 0)
        
        # 检查是否需要强制切换（如最大绿灯时间）
        if self.current_phase in [SignalPhase.NS_GREEN, SignalPhase.EW_GREEN]:
            if self.phase_timer > self.max_green_time:
                return {'action': 'force_switch', 'reason': '达到最大绿灯时间', 'mode': 'fixed_cycle'}
        
        # 检查是否可以切换（最小绿灯时间）
        if self.current_phase in [SignalPhase.NS_GREEN, SignalPhase.EW_GREEN]:
            if self.phase_timer < self.min_green_time:
                return {'action': 'maintain', 'reason': '未达到最小绿灯时间', 'mode': 'fixed_cycle'}
        
        # 全LLM模式：只要有车辆就使用LLM决策
        llm_interface = self.get_llm_interface()
        if total_vehicles > 0 and self.use_llm and llm_interface:
            try:
                llm_decision = llm_interface.get_llm_decision(perception)
                if llm_decision:
                    # 验证决策合法性
                    action = llm_decision.get('action', 'maintain')
                    if action in ['maintain', 'switch_phase', 'extend_current', 'force_switch']:
                        self.last_decision_time = current_time
                        
                        # 保存历史
                        self.history.append({
                            'time': current_time,
                            'perception': perception,
                            'decision': llm_decision
                        })
                        if len(self.history) > self.max_history:
                            self.history.pop(0)
                        
                        # 标记为LLM决策模式
                        llm_decision['mode'] = 'llm_optimized'
                        llm_decision['vehicle_detected'] = total_vehicles
                        print(f"[红绿灯 {self.name}] LLM决策: {action} (车辆{total_vehicles}辆)")
                        return llm_decision
            except Exception as e:
                print(f"[TrafficLightAgent {self.name}] LLM决策失败: {e}")
        
        # 无车辆或LLM失败时，使用固定周期规则
        return self._fixed_cycle_decision(perception)

    def _fixed_cycle_decision(self, perception: dict) -> dict[str, Any]:
        """
        固定周期配时决策。
        
        无视交通流量，按预设时间周期切换信号灯。
        适用于无车辆或低交通量情况。
        """
        total_vehicles = perception.get('total_vehicles', 0)
        
        # 绿灯阶段：检查是否达到标准绿灯时间
        if self.current_phase == SignalPhase.NS_GREEN:
            if self.phase_timer >= 30:  # 南北绿灯固定30秒
                return {
                    'action': 'switch_phase', 
                    'reason': f'固定周期切换 (无车辆)' if total_vehicles == 0 else f'固定周期切换 (车辆{total_vehicles}辆)',
                    'mode': 'fixed_cycle',
                    'vehicle_count': total_vehicles
                }
        
        elif self.current_phase == SignalPhase.EW_GREEN:
            if self.phase_timer >= 30:  # 东西绿灯固定30秒
                return {
                    'action': 'switch_phase', 
                    'reason': f'固定周期切换 (无车辆)' if total_vehicles == 0 else f'固定周期切换 (车辆{total_vehicles}辆)',
                    'mode': 'fixed_cycle',
                    'vehicle_count': total_vehicles
                }
        
        # 其他阶段（黄灯、全红）保持自动转换
        return {
            'action': 'maintain', 
            'reason': f'固定周期维持 (无车辆等待)' if total_vehicles == 0 else f'固定周期维持 (车辆{total_vehicles}辆)',
            'mode': 'fixed_cycle',
            'vehicle_count': total_vehicles
        }
    
    def _rule_based_decision(self, perception: dict) -> dict[str, Any]:
        """基于规则的智能决策（有车辆时备用）。"""
        ns_count = sum(
            perception['directions'].get(d, {}).get('vehicle_count', 0)
            for d in ['NORTH', 'SOUTH']
        )
        ew_count = sum(
            perception['directions'].get(d, {}).get('vehicle_count', 0)
            for d in ['EAST', 'WEST']
        )
        
        # 当前是南北绿灯，且东西车多，切换
        if self.current_phase == SignalPhase.NS_GREEN and ew_count > ns_count * 1.5:
            return {'action': 'switch_phase', 'reason': '东西方向车流量大'}
        
        # 当前是东西绿灯，且南北车多，切换
        if self.current_phase == SignalPhase.EW_GREEN and ns_count > ew_count * 1.5:
            return {'action': 'switch_phase', 'reason': '南北方向车流量大'}
        
        # 默认保持
        return {'action': 'maintain', 'reason': '当前相位合理'}

    def act(self, decision: dict[str, Any]) -> None:
        """执行信号灯控制动作。"""
        action = decision.get('action', 'maintain')
        
        if action == 'switch_phase' or action == 'force_switch':
            self._switch_phase()
        elif action == 'extend_current':
            # 延长当前相位（不操作，让计时器继续）
            pass
        # maintain: 什么都不做

    def _switch_phase(self) -> None:
        """切换到下一个相位 - 双相位系统。"""
        # 双相位循环: NS_GREEN -> NS_YELLOW -> ALL_RED_1 -> EW_GREEN -> EW_YELLOW -> ALL_RED_2 -> ...
        phase_transition = {
            SignalPhase.NS_GREEN: SignalPhase.NS_YELLOW,
            SignalPhase.NS_YELLOW: SignalPhase.ALL_RED_1,
            SignalPhase.ALL_RED_1: SignalPhase.EW_GREEN,
            SignalPhase.EW_GREEN: SignalPhase.EW_YELLOW,
            SignalPhase.EW_YELLOW: SignalPhase.ALL_RED_2,
            SignalPhase.ALL_RED_2: SignalPhase.NS_GREEN,
        }
        
        if self.current_phase in phase_transition:
            old_phase = self.current_phase
            self.current_phase = phase_transition[self.current_phase]
            self.phase_timer = 0.0
            
            print(f"[TrafficLightAgent {self.name}] 相位切换: {old_phase.name} -> {self.current_phase.name}")

    def update(self, dt: float) -> None:
        """?????????????"""
        if self.state != AgentState.ACTIVE:
            return
        
        # ???????????
        self.phase_timer += dt
        
        # ?????????
        self._auto_phase_transition()
        
        # ?????????????????
        if self.traffic_light:
            if self.current_phase in [SignalPhase.NS_GREEN, SignalPhase.EW_GREEN]:
                self.traffic_light.state = TrafficLightState.GREEN
            elif self.current_phase in [SignalPhase.NS_YELLOW, SignalPhase.EW_YELLOW]:
                self.traffic_light.state = TrafficLightState.YELLOW
            else:
                self.traffic_light.state = TrafficLightState.RED

    def _auto_phase_transition(self) -> None:
        """根据计时器自动转换相位 - 双相位系统。"""
        # 黄灯时间到，转全红（清空路口）
        if self.current_phase in [SignalPhase.NS_YELLOW, SignalPhase.EW_YELLOW]:
            if self.phase_timer >= self.yellow_time:
                self._switch_phase()
        
        # 全红时间到，转下一个绿灯
        elif self.current_phase in [SignalPhase.ALL_RED_1, SignalPhase.ALL_RED_2]:
            if self.phase_timer >= self.all_red_time:
                self._switch_phase()

    def get_status(self) -> dict[str, Any]:
        """获取智能体状态。"""
        return {
            'name': self.name,
            'node_id': self.control_node.node_id,
            'current_phase': self.current_phase.name,
            'phase_timer': round(self.phase_timer, 1),
            'light_state': self.traffic_light.state.name if self.traffic_light else 'UNKNOWN',
            'total_vehicles': self.perceive().get('total_vehicles', 0)
        }
