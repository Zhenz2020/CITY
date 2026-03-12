"""
车辆代理模块 - 优化版。

增强感知能力、智能决策和死锁恢复机制。
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from city.agents.base import BaseAgent, AgentType, AgentState
from city.utils.vector import Vector2D
from city.llm.llm_manager import get_llm_manager

if TYPE_CHECKING:
    from city.environment.road_network import RoadNetwork, Node, Edge, Lane
    from city.simulation.environment import SimulationEnvironment


class VehicleType(Enum):
    """车辆类型。"""
    CAR = auto()          # 私家车
    BUS = auto()          # 公交车
    TRUCK = auto()        # 卡车
    EMERGENCY = auto()    # 应急车辆
    MOTORCYCLE = auto()   # 摩托车
    BICYCLE = auto()      # 自行车


class VehicleAction(Enum):
    """车辆动作。"""
    ACCELERATE = auto()       # 加速
    DECELERATE = auto()       # 减速
    MAINTAIN_SPEED = auto()   # 保持速度
    CHANGE_LANE_LEFT = auto() # 向左变道
    CHANGE_LANE_RIGHT = auto()# 向右变道
    STOP = auto()             # 停车
    PROCEED = auto()          # 继续行驶
    EMERGENCY_BRAKE = auto()  # 紧急制动


class VehicleState(Enum):
    """车辆行驶状态（用于死锁检测）。"""
    CRUISING = auto()         # 巡航
    FOLLOWING = auto()        # 跟车
    STOPPED = auto()          # 已停止
    ACCELERATING = auto()     # 加速中
    DECELERATING = auto()     # 减速中
    WAITING_LIGHT = auto()    # 等红灯
    QUEUED = auto()           # 排队中
    DEADLOCKED = auto()       # 死锁（需要恢复）


class Vehicle(BaseAgent):
    """
    车辆代理 - 智能优化版。

    Attributes:
        vehicle_type: 车辆类型
        position: 当前位置
        velocity: 当前速度（标量）
        direction: 行驶方向（向量）
        max_speed: 最大速度
        acceleration: 加速度
        deceleration: 减速度
        length: 车长
        width: 车宽
        current_edge: 当前所在路段
        current_lane: 当前所在车道
        route: 规划路线
    """

    # 车辆类型默认参数
    TYPE_PARAMS = {
        VehicleType.CAR: {
            'max_speed': 33.33,       # 120 km/h
            'acceleration': 2.5,      # m/s^2
            'deceleration': 4.5,      # m/s^2
            'length': 4.5,
            'width': 1.8,
            'min_gap': 2.0,           # 最小车距
            'reaction_time': 1.0      # 反应时间
        },
        VehicleType.BUS: {
            'max_speed': 22.22,
            'acceleration': 1.5,
            'deceleration': 3.0,
            'length': 12.0,
            'width': 2.5,
            'min_gap': 3.0,
            'reaction_time': 1.2
        },
        VehicleType.TRUCK: {
            'max_speed': 25.0,
            'acceleration': 1.2,
            'deceleration': 3.5,
            'length': 16.0,
            'width': 2.5,
            'min_gap': 4.0,
            'reaction_time': 1.5
        },
        VehicleType.EMERGENCY: {
            'max_speed': 41.67,
            'acceleration': 4.0,
            'deceleration': 6.0,
            'length': 5.0,
            'width': 2.0,
            'min_gap': 1.5,
            'reaction_time': 0.5
        },
        VehicleType.MOTORCYCLE: {
            'max_speed': 27.78,
            'acceleration': 3.5,
            'deceleration': 5.0,
            'length': 2.0,
            'width': 0.8,
            'min_gap': 1.0,
            'reaction_time': 0.8
        },
        VehicleType.BICYCLE: {
            'max_speed': 5.56,
            'acceleration': 1.0,
            'deceleration': 2.0,
            'length': 1.8,
            'width': 0.6,
            'min_gap': 0.5,
            'reaction_time': 1.0
        }
    }

    def __init__(
        self,
        vehicle_type: VehicleType = VehicleType.CAR,
        environment: SimulationEnvironment | None = None,
        start_node: Node | None = None,
        end_node: Node | None = None,
        use_llm: bool = False
    ) -> None:
        super().__init__(AgentType.VEHICLE, environment, use_llm)
        self.vehicle_type = vehicle_type

        # 获取车辆参数
        params = self.TYPE_PARAMS[vehicle_type]
        self.max_speed = params['max_speed']
        self.acceleration = params['acceleration']
        self.deceleration = params['deceleration']
        self.length = params['length']
        self.width = params['width']
        self.min_gap = params['min_gap']
        self.reaction_time = params['reaction_time']

        # 动态状态
        self.position = Vector2D()
        self.velocity = 0.0
        self.direction = Vector2D(1, 0)

        # 路径相关
        self.start_node = start_node
        self.end_node = end_node
        self.current_edge: Edge | None = None
        self.current_lane: Lane | None = None
        self.distance_on_edge = 0.0
        self.route: list[Node] = []
        self.route_index = 0

        # 行为状态
        self.is_stopped = False
        self.target_speed = self.max_speed
        self.vehicle_state = VehicleState.CRUISING
        self.state_timer = 0.0  # 状态持续时间（用于死锁检测）
        self.stop_timer = 0.0   # 停止计时器
        
        # 历史状态（用于死锁检测）
        self.position_history: list[tuple[float, float]] = []
        self.history_max_size = 30  # 保存30帧历史
        
        # 决策相关
        self.current_action = VehicleAction.MAINTAIN_SPEED
        self.last_decision_time = 0.0
        self.decision_cooldown = 5.0  # 决策冷却时间（5秒）
        self.front_vehicle_distance = float('inf')
        self.is_emergency = False

    def __repr__(self) -> str:
        return f"Vehicle({self.agent_id}, type={self.vehicle_type.name}, pos={self.position}, v={self.velocity:.2f}, state={self.vehicle_state.name})"

    def set_route(self, route: list[Node]) -> None:
        """设置行驶路线。"""
        self.route = route
        self.route_index = 0
        if route:
            self.start_node = route[0]
            self.end_node = route[-1]
            self.position = route[0].position.copy()

    def plan_route(self, start: Node, end: Node) -> bool:
        """规划从起点到终点的路线。"""
        if self.environment is None or self.environment.road_network is None:
            return False

        route = self.environment.road_network.find_shortest_path(start, end)
        if route:
            self.set_route(route)
            return True
        return False

    def perceive(self) -> dict[str, Any]:
        """
        感知周围环境 - 增强版。
        
        Returns:
            感知信息字典，包含：
            - 自身状态
            - 前方车辆信息（多车道）
            - 后方车辆信息
            - 相邻车道车辆
            - 交通信号灯状态
            - 路口排队情况
            - 道路条件
        """
        perception = {
            'self': {
                'id': self.agent_id,
                'type': self.vehicle_type.name,
                'position': [round(self.position.x, 2), round(self.position.y, 2)],
                'velocity': round(self.velocity, 2),
                'max_speed': round(self.max_speed, 2),
                'acceleration': round(self.acceleration, 2),
                'deceleration': round(self.deceleration, 2),
                'state': self.vehicle_state.name,
                'direction': [round(self.direction.x, 2), round(self.direction.y, 2)],
            },
            'route': {
                'current_edge': str(self.current_edge) if self.current_edge else None,
                'distance_on_edge': round(self.distance_on_edge, 2),
                'edge_length': round(self.current_edge.length, 2) if self.current_edge else 0,
                'progress_ratio': round(self.distance_on_edge / self.current_edge.length, 2) if self.current_edge else 0,
                'remaining_nodes': len(self.route) - self.route_index - 1 if self.route else 0,
            },
            'front_vehicle': None,
            'rear_vehicle': None,
            'left_lane_vehicle': None,
            'right_lane_vehicle': None,
            'traffic_light': None,
            'intersection_queue': None,
            'surroundings': [],
            'road_conditions': 'normal',
            'is_deadlocked': self.vehicle_state == VehicleState.DEADLOCKED,
        }

        # 检测各方向车辆
        perception['front_vehicle'] = self._detect_front_vehicle_detailed()
        perception['rear_vehicle'] = self._detect_rear_vehicle()
        perception['left_lane_vehicle'] = self._detect_adjacent_vehicle('left')
        perception['right_lane_vehicle'] = self._detect_adjacent_vehicle('right')
        
        # 获取周边所有车辆（用于LLM全面理解）
        perception['surroundings'] = self._detect_all_nearby_vehicles()

        # 检测交通信号灯和路口情况
        if self.current_edge:
            next_node = self.current_edge.to_node
            distance_to_intersection = self.current_edge.length - self.distance_on_edge
            
            if next_node.is_intersection:
                # 判断车辆行驶方向（相对于路口）
                # 根据路线判断是纵向还是横向接近路口
                approach_direction = self._get_approach_direction(next_node)
                
                # 信号灯状态
                if next_node.traffic_light:
                    tl = next_node.traffic_light
                    tl_state = tl.state.name if hasattr(tl.state, 'name') else str(tl.state)
                    
                    # 检查是否有红绿灯智能体（双相位系统）
                    is_my_direction_green = True  # 默认允许通行
                    traffic_light_agent = None
                    
                    if self.environment:
                        for agent in self.environment.agents.values():
                            if hasattr(agent, 'control_node') and agent.control_node == next_node:
                                traffic_light_agent = agent
                                break
                    
                    if traffic_light_agent:
                        # 双相位系统：判断当前相位是否允许本方向通行
                        try:
                            current_phase = traffic_light_agent.current_phase
                            phase_name = current_phase.name if hasattr(current_phase, 'name') else str(current_phase)
                            
                            # 判断本车方向
                            is_ns = approach_direction in ['NORTH', 'SOUTH']
                            is_ew = approach_direction in ['EAST', 'WEST']
                            
                            # 检查当前相位
                            is_ns_green = 'NS_GREEN' in phase_name
                            is_ew_green = 'EW_GREEN' in phase_name
                            is_yellow = 'YELLOW' in phase_name
                            is_all_red = 'ALL_RED' in phase_name
                            
                            if is_all_red:
                                # 全红灯，所有人必须停
                                is_my_direction_green = False
                                tl_state = 'RED'
                            elif is_ns and is_ns_green:
                                is_my_direction_green = True
                                tl_state = 'GREEN'
                            elif is_ew and is_ew_green:
                                is_my_direction_green = True
                                tl_state = 'GREEN'
                            elif is_ns and is_ew_green:
                                is_my_direction_green = False
                                tl_state = 'RED'
                            elif is_ew and is_ns_green:
                                is_my_direction_green = False
                                tl_state = 'RED'
                            elif is_yellow:
                                # 黄灯：如果是本方向的黄灯，可以视为绿灯（准备通过）
                                # 如果不是本方向的黄灯，视为红灯
                                if is_ns and 'NS_YELLOW' in phase_name:
                                    is_my_direction_green = True
                                    tl_state = 'YELLOW'  # 黄灯但可以走
                                elif is_ew and 'EW_YELLOW' in phase_name:
                                    is_my_direction_green = True
                                    tl_state = 'YELLOW'
                                else:
                                    is_my_direction_green = False
                                    tl_state = 'RED'
                            else:
                                # 其他情况，保守处理为红灯
                                is_my_direction_green = False
                                tl_state = 'RED'
                            
                            # 调试输出
                            if distance_to_intersection < 50:
                                print(f"[Vehicle {self.agent_id}] 信号灯检测: 方向={approach_direction}, 相位={phase_name}, 状态={tl_state}, 距离={distance_to_intersection:.1f}m")
                        except Exception as e:
                            print(f"[Vehicle {self.agent_id}] 信号灯检测失败: {e}")
                            # 出错时默认允许通行（避免卡住）
                            is_my_direction_green = True
                            tl_state = 'GREEN'
                    
                    perception['traffic_light'] = {
                        'state': tl_state,
                        'distance': round(distance_to_intersection, 2),
                        'time_to_reach': round(distance_to_intersection / max(self.velocity, 1), 2) if self.velocity > 0 else float('inf'),
                        'approach_direction': approach_direction,
                        'is_my_direction_green': is_my_direction_green,
                    }
                
                # 路口排队情况
                queue_length = self._detect_intersection_queue(next_node)
                perception['intersection_queue'] = {
                    'length': queue_length,
                    'distance_to_intersection': round(distance_to_intersection, 2),
                    'is_blocked': queue_length > 0 and distance_to_intersection < queue_length * (self.length + self.min_gap),
                }

        # 检测是否被堵住（死锁）
        if self._is_blocked():
            perception['road_conditions'] = 'blocked'

        return perception

    def _get_approach_direction(self, intersection_node: Any) -> str:
        """
        判断车辆接近路口的方向。
        
        Args:
            intersection_node: 路口节点
            
        Returns:
            方向字符串: 'NORTH', 'SOUTH', 'EAST', 'WEST'
        """
        if not self.current_edge:
            return 'UNKNOWN'
        
        from_pos = self.current_edge.from_node.position
        to_pos = intersection_node.position
        
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        
        # 根据来路方向判断
        if abs(dx) > abs(dy):
            # 主要是东西方向
            return 'EAST' if dx > 0 else 'WEST'
        else:
            # 主要是南北方向
            return 'NORTH' if dy > 0 else 'SOUTH'

    def _detect_front_vehicle_detailed(self) -> dict[str, Any] | None:
        """详细检测前方车辆信息。"""
        if not self.current_edge:
            return None

        closest_vehicle = None
        closest_distance = float('inf')
        closest_velocity = 0

        # 在当前车道搜索
        if self.current_lane:
            for vehicle in self.current_lane.vehicles:
                if vehicle is self or vehicle.agent_id == self.agent_id:
                    continue
                if vehicle.distance_on_edge > self.distance_on_edge:
                    dist = vehicle.distance_on_edge - self.distance_on_edge - vehicle.length
                    if dist < closest_distance:
                        closest_distance = dist
                        closest_vehicle = vehicle
                        closest_velocity = vehicle.velocity

        # 如果没找到，检查下一路段
        if closest_vehicle is None and self.route_index < len(self.route) - 1:
            next_node = self.current_edge.to_node
            next_next_node = self.route[self.route_index + 1]
            
            for edge in next_node.outgoing_edges:
                if edge.to_node == next_next_node:
                    for lane in edge.lanes:
                        for vehicle in lane.vehicles:
                            remaining_dist = self.current_edge.length - self.distance_on_edge
                            dist_on_next = vehicle.distance_on_edge
                            total_dist = remaining_dist + dist_on_next - vehicle.length
                            if total_dist < closest_distance:
                                closest_distance = total_dist
                                closest_vehicle = vehicle
                                closest_velocity = vehicle.velocity
                    break

        if closest_vehicle:
            self.front_vehicle_distance = closest_distance
            time_to_collision = self._calculate_ttc(closest_distance, closest_velocity)
            
            return {
                'id': closest_vehicle.agent_id,
                'distance': round(closest_distance, 2),
                'velocity': round(closest_velocity, 2),
                'relative_velocity': round(self.velocity - closest_velocity, 2),
                'time_to_collision': round(time_to_collision, 2),
                'type': closest_vehicle.vehicle_type.name,
                'is_stopped': closest_vehicle.velocity < 0.5,
            }
        
        self.front_vehicle_distance = float('inf')
        return None

    def _detect_rear_vehicle(self) -> dict[str, Any] | None:
        """检测后方车辆。"""
        if not self.current_lane:
            return None

        closest_vehicle = None
        closest_distance = float('inf')

        for vehicle in self.current_lane.vehicles:
            if vehicle is self or vehicle.agent_id == self.agent_id:
                continue
            if vehicle.distance_on_edge < self.distance_on_edge:
                dist = self.distance_on_edge - vehicle.distance_on_edge - self.length
                if dist < closest_distance and dist < 50:  # 只关心50米内的
                    closest_distance = dist
                    closest_vehicle = vehicle

        if closest_vehicle:
            return {
                'id': closest_vehicle.agent_id,
                'distance': round(closest_distance, 2),
                'velocity': round(closest_vehicle.velocity, 2),
                'approaching_speed': round(closest_vehicle.velocity - self.velocity, 2),
            }
        return None

    def _detect_adjacent_vehicle(self, side: str) -> dict[str, Any] | None:
        """检测相邻车道车辆。"""
        if not self.current_edge or not self.current_lane:
            return None

        current_lane_idx = self.current_edge.lanes.index(self.current_lane)
        target_lane_idx = current_lane_idx + (-1 if side == 'left' else 1)

        if target_lane_idx < 0 or target_lane_idx >= len(self.current_edge.lanes):
            return None

        target_lane = self.current_edge.lanes[target_lane_idx]
        
        # 寻找相邻车道中距离最近的车辆（前后30米范围内）
        closest_vehicle = None
        closest_distance = float('inf')
        is_front = True

        for vehicle in target_lane.vehicles:
            dist = vehicle.distance_on_edge - self.distance_on_edge
            abs_dist = abs(dist)
            if abs_dist < 30 and abs_dist < closest_distance:
                closest_distance = abs_dist
                closest_vehicle = vehicle
                is_front = dist > 0

        if closest_vehicle:
            return {
                'id': closest_vehicle.agent_id,
                'distance': round(closest_distance, 2),
                'is_front': is_front,
                'velocity': round(closest_vehicle.velocity, 2),
                'type': closest_vehicle.vehicle_type.name,
            }
        return None

    def _detect_all_nearby_vehicles(self) -> list[dict[str, Any]]:
        """检测周边所有车辆（用于LLM全面理解）。"""
        nearby = []
        if not self.current_edge:
            return nearby

        search_range = 100  # 100米范围

        # 当前路段所有车辆
        for lane in self.current_edge.lanes:
            for vehicle in lane.vehicles:
                if vehicle is self:
                    continue
                dist = abs(vehicle.distance_on_edge - self.distance_on_edge)
                if dist < search_range:
                    nearby.append({
                        'id': vehicle.agent_id,
                        'distance': round(dist, 2),
                        'is_front': vehicle.distance_on_edge > self.distance_on_edge,
                        'velocity': round(vehicle.velocity, 2),
                        'lane': self.current_edge.lanes.index(lane),
                    })

        return nearby

    def _detect_intersection_queue(self, intersection_node) -> int:
        """检测路口排队车辆数。"""
        queue_count = 0
        for edge in intersection_node.incoming_edges:
            for lane in edge.lanes:
                for vehicle in lane.vehicles:
                    dist_to_intersection = edge.length - vehicle.distance_on_edge
                    if dist_to_intersection < 30:  # 30米内算排队
                        queue_count += 1
        return queue_count

    def _calculate_ttc(self, distance: float, front_velocity: float) -> float:
        """计算碰撞时间 (Time To Collision)。"""
        relative_speed = self.velocity - front_velocity
        if relative_speed <= 0:
            return float('inf')
        return distance / relative_speed

    def _is_blocked(self) -> bool:
        """检测是否被完全堵住。"""
        return self.vehicle_state == VehicleState.DEADLOCKED

    def decide(self) -> VehicleAction:
        """
        决策 - 增强版（带安全检查）。
        
        使用LLM进行智能决策，但会进行安全验证。
        安全规则（如红灯停车）具有最高优先级，不可被LLM覆盖。
        """
        current_time = self.environment.current_time if self.environment else 0
        
        # 决策冷却
        if current_time - self.last_decision_time < self.decision_cooldown:
            return self.current_action
        
        self.last_decision_time = current_time
        
        # 首先检测死锁
        if self._check_deadlock():
            self.vehicle_state = VehicleState.DEADLOCKED
            return self._deadlock_recovery()

        # ========== 安全层：强制安全规则（最高优先级）==========
        perception = self.perceive()
        safety_action = self._safety_check(perception)
        
        # 无论安全规则是否触发，都要尝试提交LLM决策请求（异步）
        # 这样可以确保LLM持续决策，但安全规则可以覆盖LLM的结果
        if self.use_llm and current_time > 2.0:
            try:
                llm_manager = get_llm_manager()
                llm_interface = self.get_llm_interface()
                
                if llm_interface:
                    # 检查是否有已完成的决策结果
                    result = llm_manager.get_result(self.agent_id)
                    if result:
                        # 解析LLM决策
                        llm_action = self._parse_llm_decision(result)
                        if llm_action:
                            print(f"[Vehicle {self.agent_id}] LLM决策(缓存): {result.get('action')}, 安全规则: {safety_action is not None}")
                            llm_manager.clear_result(self.agent_id)
                            # 提交新的决策请求（为下次使用）
                            llm_manager.request_decision(self.agent_id, llm_interface, perception)
                            
                            # 如果安全规则没有触发，使用LLM决策
                            if safety_action is None:
                                self.current_action = llm_action
                                return llm_action
                            # 如果安全规则触发了，仍然使用安全动作，但LLM决策已记录
                    
                    # 如果没有 pending 请求，提交一个
                    if not llm_manager.has_pending(self.agent_id):
                        llm_manager.request_decision(self.agent_id, llm_interface, perception)
                        if not hasattr(self, '_llm_request_logged'):
                            print(f"[Vehicle {self.agent_id}] 提交LLM决策请求")
                            self._llm_request_logged = True
            except Exception as e:
                print(f"[Vehicle {self.agent_id}] LLM决策失败: {e}")
        
        # 如果安全规则触发，优先使用安全动作
        if safety_action:
            self.current_action = safety_action
            return safety_action

        # 规则决策作为fallback
        return self._rule_based_decide()
    
    def _safety_check(self, perception: dict) -> VehicleAction | None:
        """
        安全检查 - 最高优先级规则。
        
        这些规则不可被LLM覆盖，必须强制执行。
        
        Returns:
            如果触发安全规则，返回对应动作；否则返回None
        """
        traffic_light = perception.get('traffic_light')
        front_vehicle = perception.get('front_vehicle')
        
        # 1. 信号灯处理
        if traffic_light:
            tl_state = traffic_light.get('state', '')
            distance = traffic_light.get('distance', float('inf'))
            
            # 绿灯：可以通行，不触发安全规则（让LLM处理）
            if 'GREEN' in tl_state:
                # 绿灯时，只检查是否需要减速（如果车速很快且接近路口）
                if distance < 10 and self.velocity > 10:
                    return VehicleAction.DECELERATE
                # 绿灯不触发安全限制，让LLM决策
                pass
            
            # 黄灯：如果能安全停车就停，否则通过
            elif 'YELLOW' in tl_state:
                stop_distance = (self.velocity ** 2) / (2 * self.deceleration)
                # 如果无法安全停车，允许通过（视为绿灯）
                if stop_distance >= distance:
                    # 无法停车，通过
                    pass
                else:
                    # 可以安全停车
                    if distance < 15:
                        if self.velocity < 0.5:
                            return VehicleAction.STOP
                        else:
                            return VehicleAction.DECELERATE
            
            # 红灯：必须停车
            elif 'RED' in tl_state:
                # 计算制动距离
                stop_distance = (self.velocity ** 2) / (2 * self.deceleration)
                SAFE_STOP_DISTANCE = 15.0  # 在路口前15米停车
                
                # 红灯时必须停车
                if distance <= SAFE_STOP_DISTANCE + 5:  # 在停车线附近
                    if self.velocity < 0.5:
                        self.velocity = 0
                        self.vehicle_state = VehicleState.WAITING_LIGHT
                        return VehicleAction.STOP
                    else:
                        self.vehicle_state = VehicleState.DECELERATING
                        return VehicleAction.DECELERATE
                elif stop_distance >= distance - SAFE_STOP_DISTANCE:
                    # 需要开始减速
                    self.vehicle_state = VehicleState.DECELERATING
                    return VehicleAction.DECELERATE
        
        # 2. 前方车辆碰撞风险
        if front_vehicle:
            ttc = front_vehicle.get('time_to_collision', float('inf'))
            distance = front_vehicle.get('distance', float('inf'))
            
            if ttc < 2.0 and distance < 10:  # 即将碰撞
                return VehicleAction.EMERGENCY_BRAKE
            if ttc < 3.0:  # 碰撞风险
                return VehicleAction.DECELERATE
        
        # 安全检查通过，返回None让上层决策
        return None

    def _parse_llm_decision(self, llm_response: dict) -> VehicleAction | None:
        """解析LLM决策响应。"""
        action_map = {
            'accelerate': VehicleAction.ACCELERATE,
            'decelerate': VehicleAction.DECELERATE,
            'maintain': VehicleAction.MAINTAIN_SPEED,
            'stop': VehicleAction.STOP,
            'proceed': VehicleAction.PROCEED,
            'change_lane_left': VehicleAction.CHANGE_LANE_LEFT,
            'change_lane_right': VehicleAction.CHANGE_LANE_RIGHT,
            'emergency_brake': VehicleAction.EMERGENCY_BRAKE,
        }
        
        action_str = llm_response.get('action', '').lower()
        return action_map.get(action_str)

    def _rule_based_decide(self) -> VehicleAction:
        """基于规则的决策逻辑。"""
        perception = self.perceive()
        front_vehicle = perception.get('front_vehicle')
        traffic_light = perception.get('traffic_light')
        intersection_queue = perception.get('intersection_queue')

        # 1. 紧急制动判断
        if front_vehicle:
            ttc = front_vehicle.get('time_to_collision', float('inf'))
            if ttc < 2.0 and ttc > 0:  # 2秒内碰撞
                self.is_emergency = True
                self.vehicle_state = VehicleState.DECELERATING
                return VehicleAction.EMERGENCY_BRAKE

        # 2. 前车跟随逻辑（IDM简化版）
        if front_vehicle:
            distance = front_vehicle['distance']
            front_v = front_vehicle['velocity']
            
            # 安全距离 = 静止车距 + 速度相关距离
            safe_distance = self.min_gap + self.velocity * self.reaction_time
            
            if distance < safe_distance * 0.5:
                self.vehicle_state = VehicleState.FOLLOWING
                if self.velocity > front_v:
                    return VehicleAction.DECELERATE
                elif front_v > self.velocity + 1:
                    return VehicleAction.ACCELERATE
                return VehicleAction.MAINTAIN_SPEED
            
            elif distance < safe_distance:
                if self.velocity > front_v + 2:
                    return VehicleAction.DECELERATE
                return VehicleAction.MAINTAIN_SPEED

        # 3. 交通信号灯处理
        if traffic_light:
            tl_state = traffic_light.get('state', '')
            distance = traffic_light.get('distance', float('inf'))
            time_to_reach = traffic_light.get('time_to_reach', float('inf'))
            
            if 'RED' in tl_state or 'YELLOW' in tl_state:
                # 计算能否通过
                if distance < 10:  # 已经非常接近
                    if self.velocity < 1:
                        self.vehicle_state = VehicleState.WAITING_LIGHT
                        return VehicleAction.STOP
                    return VehicleAction.DECELERATE
                
                # 判断是否能安全停车
                stop_distance = (self.velocity ** 2) / (2 * self.deceleration)
                
                if stop_distance < distance * 0.8:  # 可以安全停车
                    if distance < 30:
                        self.vehicle_state = VehicleState.DECELERATING
                        return VehicleAction.DECELERATE
                else:  # 无法停车，通过
                    if 'YELLOW' in tl_state and time_to_reach < 3:
                        return VehicleAction.PROCEED

        # 4. 路口排队处理
        if intersection_queue and intersection_queue.get('is_blocked'):
            self.vehicle_state = VehicleState.QUEUED
            return VehicleAction.DECELERATE

        # 5. 速度控制
        target = min(self.target_speed, self.current_lane.max_speed if self.current_lane else self.max_speed)
        
        if self.velocity < target - 2:
            self.vehicle_state = VehicleState.ACCELERATING
            return VehicleAction.ACCELERATE
        elif self.velocity > target + 1:
            return VehicleAction.DECELERATE

        self.vehicle_state = VehicleState.CRUISING
        return VehicleAction.MAINTAIN_SPEED

    def _check_deadlock(self) -> bool:
        """??????????????????"""
        dt = 0.1
        if self.environment and hasattr(self.environment, "config"):
            dt = self.environment.config.time_step

        if self.vehicle_state == VehicleState.DEADLOCKED:
            # 如果速度已经恢复，说明死锁已解除
            if self.velocity > 1.0:
                print(f"[Vehicle {self.agent_id}] 死锁已解除，恢复正常行驶")
                self.vehicle_state = VehicleState.CRUISING
                self.stop_timer = 0.0
                self.position_history = []
                return False
            # 还在恢复中，继续尝试恢复
            return True
        
        # 如果已经停止超过5秒，可能是死锁
        if self.velocity < 0.5:
            self.stop_timer += dt  # ?????????
            
            # 记录位置历史
            self.position_history.append((self.position.x, self.position.y))
            if len(self.position_history) > self.history_max_size:
                self.position_history.pop(0)
            
            # 检测是否长时间没有移动
            if self.stop_timer > 5.0 and len(self.position_history) >= 10:
                # 检查最后10个位置是否基本不变
                recent_positions = self.position_history[-10:]
                max_movement = max(
                    ((p[0] - recent_positions[0][0])**2 + (p[1] - recent_positions[0][1])**2)**0.5
                    for p in recent_positions
                )
                if max_movement < 1.0:  # 1米内移动
                    print(f"[Vehicle {self.agent_id}] 检测到死锁！停止时间: {self.stop_timer:.1f}s")
                    return True
        else:
            self.stop_timer = 0.0
            self.position_history = []

        return False

    def _deadlock_recovery(self) -> VehicleAction:
        """死锁恢复策略 - 改进版，支持多车交替通行。"""
        print(f"[Vehicle {self.agent_id}] 死锁恢复中...")
        
        # 获取感知信息
        perception = self.perceive()
        front = perception.get('front_vehicle')
        
        # 策略1: 如果前方没有车辆或距离足够远，缓慢前进
        if not front or front.get('distance', 0) > self.length * 2.5:
            print(f"[Vehicle {self.agent_id}] 死锁恢复: 前方空旷，缓慢前进")
            self.velocity = 1.5  # 给一个适中的速度
            self.vehicle_state = VehicleState.CRUISING
            self.stop_timer = 0.0
            self.position_history = []
            return VehicleAction.PROCEED
        
        # 策略2: 如果前车也在死锁状态，尝试交替通行（ID小的先走）
        if front:
            front_id = front.get('id', '')
            front_dist = front.get('distance', 0)
            
            # 基于ID的优先级：ID小的先走
            try:
                my_priority = int(self.agent_id.split('_')[-1]) if '_' in self.agent_id else 0
                front_priority = int(front_id.split('_')[-1]) if front_id and '_' in front_id else 999
            except:
                my_priority = 0
                front_priority = 999
            
            # 如果前车很近（小于2倍车长），且我优先级高，尝试缓慢前进
            if front_dist < self.length * 2.5 and my_priority < front_priority:
                print(f"[Vehicle {self.agent_id}] 死锁恢复: 优先级高({my_priority} < {front_priority})，强制缓慢前进")
                self.velocity = 0.8  # 给一个小速度，慢慢挤过去
                self.vehicle_state = VehicleState.CRUISING
                return VehicleAction.PROCEED
            
            # 如果前车有点距离，正常前进
            if front_dist >= self.length * 2.5:
                print(f"[Vehicle {self.agent_id}] 死锁恢复: 前车距离足够({front_dist:.1f}m)，正常前进")
                self.velocity = 1.0
                self.vehicle_state = VehicleState.CRUISING
                return VehicleAction.PROCEED
            
            # 优先级低，但也不要完全停止，给一个很小的速度
            if my_priority >= front_priority:
                print(f"[Vehicle {self.agent_id}] 死锁恢复: 优先级低，等待但保持微小移动")
                self.velocity = 0.3  # 不完全停止，保持微小移动
                return VehicleAction.PROCEED
        
        # 策略3: 尝试变道（简化版）
        left = perception.get('left_lane_vehicle')
        right = perception.get('right_lane_vehicle')
        
        if not left:
            print(f"[Vehicle {self.agent_id}] 死锁恢复: 向左变道")
            self.vehicle_state = VehicleState.CRUISING
            return VehicleAction.CHANGE_LANE_LEFT
        if not right:
            print(f"[Vehicle {self.agent_id}] 死锁恢复: 向右变道")
            self.vehicle_state = VehicleState.CRUISING
            return VehicleAction.CHANGE_LANE_RIGHT
        
        # 策略4: 最后手段，强制微小移动（不停下）
        print(f"[Vehicle {self.agent_id}] 死锁恢复: 强制微小移动")
        self.velocity = 0.5  # 保持一定速度，不完全停止
        self.vehicle_state = VehicleState.CRUISING
        return VehicleAction.PROCEED

    def act(self, action: VehicleAction) -> None:
        """执行驾驶动作 - 增强版。"""
        dt = 0.1  # 时间步长
        
        if action == VehicleAction.ACCELERATE:
            self.velocity = min(
                self.velocity + self.acceleration * dt,
                self.max_speed,
                self.current_lane.max_speed if self.current_lane else self.max_speed
            )
            self.is_stopped = False
            
        elif action == VehicleAction.DECELERATE:
            new_velocity = self.velocity - self.deceleration * dt
            if new_velocity < 0.5:
                self.velocity = 0
                self.is_stopped = True
            else:
                self.velocity = new_velocity
                self.is_stopped = False
                
        elif action == VehicleAction.EMERGENCY_BRAKE:
            new_velocity = self.velocity - self.deceleration * 2 * dt
            self.velocity = max(0, new_velocity)
            self.is_stopped = self.velocity < 0.5
            self.is_emergency = False
            
        elif action == VehicleAction.STOP:
            new_velocity = self.velocity - self.deceleration * 1.5 * dt
            self.velocity = max(0, new_velocity)
            self.is_stopped = self.velocity < 0.1
            
        elif action == VehicleAction.PROCEED:
            # 继续行驶（从停止状态恢复）
            if self.velocity < 2:
                self.velocity = min(self.velocity + self.acceleration * dt * 2, 5)
            self.is_stopped = False
            
        elif action == VehicleAction.CHANGE_LANE_LEFT:
            self._attempt_lane_change('left')
            
        elif action == VehicleAction.CHANGE_LANE_RIGHT:
            self._attempt_lane_change('right')
            
        # MAINTAIN_SPEED 不执行任何操作

        self.current_action = action

    def _attempt_lane_change(self, direction: str) -> bool:
        """尝试变道。"""
        if not self.current_edge or not self.current_lane:
            return False

        current_idx = self.current_edge.lanes.index(self.current_lane)
        target_idx = current_idx + (-1 if direction == 'left' else 1)

        if target_idx < 0 or target_idx >= len(self.current_edge.lanes):
            return False

        target_lane = self.current_edge.lanes[target_idx]

        # 检查目标车道是否有足够空间
        for vehicle in target_lane.vehicles:
            dist = abs(vehicle.distance_on_edge - self.distance_on_edge)
            if dist < (self.length + vehicle.length) * 1.5:
                return False

        # 执行变道
        self.current_lane.remove_vehicle(self)
        self.current_lane = target_lane
        self.current_lane.add_vehicle(self)
        return True

    def update(self, dt: float) -> None:
        """更新车辆状态 - 增强版。"""
        if self.state != AgentState.ACTIVE:
            return

        # 更新状态计时器
        self.state_timer += dt

        # 执行决策-行动循环

        # 更新位置
        if self.current_edge and self.velocity > 0.01:  # 降低阈值，确保低速也能移动
            move_distance = self.velocity * dt
            
            # 硬限制：红灯时不能越过停止线（距离路口15米处）
            next_node = self.current_edge.to_node
            if next_node.is_intersection and next_node.traffic_light:
                perception = self.perceive()
                traffic_light = perception.get('traffic_light')
                if traffic_light and 'RED' in traffic_light.get('state', ''):
                    distance_to_intersection = self.current_edge.length - self.distance_on_edge
                    SAFE_STOP_DISTANCE = 15.0
                    if distance_to_intersection <= SAFE_STOP_DISTANCE and distance_to_intersection > 0:
                        # 红灯且在停止线附近，不允许前进
                        self.velocity = 0
                        self.distance_on_edge = self.current_edge.length - SAFE_STOP_DISTANCE
                        self._update_position()
                        self.vehicle_state = VehicleState.WAITING_LIGHT
                        # 跳过这次位置更新
                        if self.route_index >= len(self.route) - 1 and self.current_edge is None:
                            self.complete()
                        continue_update = False
                    else:
                        continue_update = True
                else:
                    continue_update = True
            else:
                continue_update = True
            
            if continue_update:
                self.distance_on_edge += move_distance

                # 检查是否到达路段终点
                if self.distance_on_edge >= self.current_edge.length:
                    self._handle_edge_completion()
                else:
                    self._update_position()
                    
                # 死锁恢复期间，定期打印状态
                if self.vehicle_state == VehicleState.DEADLOCKED and self.state_timer % 1.0 < dt:
                    print(f"[Vehicle {self.agent_id}] 死锁恢复中: v={self.velocity:.2f}, d={self.distance_on_edge:.1f}")

        # 检查是否到达目的地
        if self.route_index >= len(self.route) - 1 and self.current_edge is None:
            self.complete()

    def _update_position(self) -> None:
        """根据当前路段和距离更新位置坐标（包含车道偏移）。"""
        if not self.current_edge:
            return

        start_pos = self.current_edge.from_node.position
        end_pos = self.current_edge.to_node.position

        ratio = min(self.distance_on_edge / self.current_edge.length, 1.0)
        
        # 计算道路中心线位置
        base_position = Vector2D(
            start_pos.x + (end_pos.x - start_pos.x) * ratio,
            start_pos.y + (end_pos.y - start_pos.y) * ratio
        )
        
        # 计算车道偏移
        lane_offset = self._get_lane_offset()
        if lane_offset != 0:
            # 计算垂直于道路方向的偏移向量
            road_dir = (end_pos - start_pos).normalize()
            # 垂直方向（顺时针旋转90度）
            perp_dir = Vector2D(-road_dir.y, road_dir.x)
            # 应用偏移
            base_position = base_position + perp_dir * lane_offset
        
        self.position = base_position
        self.direction = (end_pos - start_pos).normalize()
    
    def _get_lane_offset(self) -> float:
        """
        获取车道横向偏移量。
        
        Returns:
            相对于道路中心线的横向偏移距离（米）
        """
        if not self.current_edge or not self.current_lane:
            return 0.0
        
        try:
            lane_index = self.current_edge.lanes.index(self.current_lane)
            num_lanes = len(self.current_edge.lanes)
            lane_width = 3.5  # 标准车道宽度3.5米
            
            # 计算偏移：双车道时，车道0在左侧偏移-1.75m，车道1在右侧偏移+1.75m
            if num_lanes == 1:
                return 0.0
            elif num_lanes == 2:
                # 双车道：index 0 在左(-1.75)，index 1 在右(+1.75)
                return (lane_index - 0.5) * lane_width
            else:
                # 多车道通用公式
                center_offset = (num_lanes - 1) / 2.0
                return (lane_index - center_offset) * lane_width
        except ValueError:
            return 0.0

    def _handle_edge_completion(self) -> None:
        """处理到达路段终点的情况。"""
        if not self.current_edge:
            return

        if self.current_lane:
            self.current_lane.remove_vehicle(self)

        current_node = self.current_edge.to_node

        if self.route_index < len(self.route) - 1:
            next_node = self.route[self.route_index + 1]

            for edge in current_node.outgoing_edges:
                if edge.to_node == next_node:
                    self.current_edge = edge
                    self.current_lane = edge.get_free_lane()
                    if self.current_lane:
                        self.current_lane.add_vehicle(self)
                    self.distance_on_edge = 0.0
                    self.route_index += 1
                    self.vehicle_state = VehicleState.CRUISING
                    return

        self.complete()

    def spawn_on_edge(self, edge: Edge, lane_index: int = 0) -> None:
        """在指定路段上生成车辆（考虑车道位置）。"""
        self.current_edge = edge
        if 0 <= lane_index < len(edge.lanes):
            self.current_lane = edge.lanes[lane_index]
            self.current_lane.add_vehicle(self)
        self.distance_on_edge = 0.0
        
        # 计算初始位置（考虑车道偏移）
        start_pos = edge.from_node.position
        end_pos = edge.to_node.position
        road_dir = (end_pos - start_pos).normalize()
        
        # 计算车道偏移
        lane_width = 3.5
        num_lanes = len(edge.lanes)
        if num_lanes == 2:
            lane_offset = (lane_index - 0.5) * lane_width
        else:
            center_offset = (num_lanes - 1) / 2.0
            lane_offset = (lane_index - center_offset) * lane_width
        
        # 应用偏移（垂直于道路方向）
        perp_dir = Vector2D(-road_dir.y, road_dir.x)
        self.position = start_pos + perp_dir * lane_offset
        
        self.direction = road_dir
        self.vehicle_state = VehicleState.CRUISING
        self.activate()
