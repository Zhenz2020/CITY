"""
仿真环境模块。

管理整个交通仿真系统的运行。
"""

from __future__ import annotations

import time
from typing import Any

from city.environment.road_network import RoadNetwork, Node, Edge, TrafficLight
from city.agents.base import BaseAgent, AgentState
from city.agents.vehicle import Vehicle
from city.agents.pedestrian import Pedestrian
from city.agents.traffic_manager import TrafficManager
from city.agents.traffic_planner import TrafficPlanner


class SimulationConfig:
    """仿真配置。"""

    def __init__(
        self,
        time_step: float = 0.1,           # 仿真时间步长（秒）
        max_simulation_time: float = 3600.0,  # 最大仿真时间（秒）
        real_time_factor: float = 1.0,    # 实时因子（1.0表示实时）
        random_seed: int | None = None,
        enable_visualization: bool = False
    ) -> None:
        self.time_step = time_step
        self.max_simulation_time = max_simulation_time
        self.real_time_factor = real_time_factor
        self.random_seed = random_seed
        self.enable_visualization = enable_visualization


class SimulationEnvironment:
    """
    仿真环境。

    管理整个交通仿真系统的运行，包括：
    - 道路网络
    - 所有智能体
    - 仿真时间
    - 数据收集

    Attributes:
        config: 仿真配置
        road_network: 道路网络
        agents: 所有智能体
        current_time: 当前仿真时间
        is_running: 是否正在运行
    """

    def __init__(
        self,
        road_network: RoadNetwork | None = None,
        config: SimulationConfig | None = None
    ) -> None:
        self.config = config or SimulationConfig()
        self.road_network = road_network or RoadNetwork()

        # 智能体管理
        self.agents: dict[str, BaseAgent] = {}
        self.vehicles: dict[str, Vehicle] = {}
        self.pedestrians: dict[str, Pedestrian] = {}
        self.traffic_managers: dict[str, TrafficManager] = {}
        self.traffic_planners: dict[str, TrafficPlanner] = {}

        # 仿真状态
        self.current_time = 0.0
        self.is_running = False
        self.is_paused = False
        self.step_count = 0

        # 统计数据
        self.statistics = {
            'total_vehicles_spawned': 0,
            'total_vehicles_completed': 0,
            'total_pedestrians_spawned': 0,
            'total_pedestrians_completed': 0,
            'average_travel_time': 0.0,
            'congestion_events': 0
        }

        # 事件日志
        self.event_log: list[dict[str, Any]] = []

    def __repr__(self) -> str:
        return f"SimulationEnvironment(time={self.current_time:.1f}, agents={len(self.agents)}, running={self.is_running})"

    def add_agent(self, agent: BaseAgent) -> None:
        """添加智能体到环境。"""
        agent.set_environment(self)
        agent.creation_time = self.current_time
        self.agents[agent.agent_id] = agent

        # 按类型分类存储
        if isinstance(agent, Vehicle):
            self.vehicles[agent.agent_id] = agent
            self.statistics['total_vehicles_spawned'] += 1
        elif isinstance(agent, Pedestrian):
            self.pedestrians[agent.agent_id] = agent
            self.statistics['total_pedestrians_spawned'] += 1
        elif isinstance(agent, TrafficManager):
            self.traffic_managers[agent.agent_id] = agent
        elif isinstance(agent, TrafficPlanner):
            self.traffic_planners[agent.agent_id] = agent

    def remove_agent(self, agent_id: str) -> bool:
        """从环境中移除智能体。"""
        if agent_id not in self.agents:
            return False

        agent = self.agents[agent_id]

        # 从分类存储中移除
        if isinstance(agent, Vehicle):
            del self.vehicles[agent_id]
            self.statistics['total_vehicles_completed'] += 1
        elif isinstance(agent, Pedestrian):
            del self.pedestrians[agent_id]
            self.statistics['total_pedestrians_completed'] += 1
        elif isinstance(agent, TrafficManager):
            del self.traffic_managers[agent_id]
        elif isinstance(agent, TrafficPlanner):
            del self.traffic_planners[agent_id]

        del self.agents[agent_id]
        return True

    def spawn_vehicle(
        self,
        start_node: Node,
        end_node: Node,
        vehicle_type: Any = None,
        route: list[Node] | None = None
    ) -> Vehicle | None:
        """
        在环境中生成车辆。

        Args:
            start_node: 起点节点
            end_node: 终点节点
            vehicle_type: 车辆类型
            route: 预设路线

        Returns:
            生成的车辆，如果失败返回None
        """
        from city.agents.vehicle import VehicleType

        vehicle = Vehicle(
            vehicle_type=vehicle_type or VehicleType.CAR,
            environment=self,
            start_node=start_node,
            end_node=end_node
        )

        # 规划路线
        if route:
            vehicle.set_route(route)
        else:
            if not vehicle.plan_route(start_node, end_node):
                return None

        # 在第一条路段上生成
        if vehicle.route and len(vehicle.route) >= 2:
            first_edge = None
            for edge in start_node.outgoing_edges:
                if edge.to_node == vehicle.route[1]:
                    first_edge = edge
                    break

            if first_edge:
                vehicle.spawn_on_edge(first_edge)
                self.add_agent(vehicle)
                self._log_event('vehicle_spawned', {
                    'vehicle_id': vehicle.agent_id,
                    'start': start_node.node_id,
                    'end': end_node.node_id
                })
                return vehicle

        return None

    def spawn_pedestrian(
        self,
        start_pos: Any,
        end_pos: Any
    ) -> Pedestrian | None:
        """
        在环境中生成行人。

        Args:
            start_pos: 起点位置
            end_pos: 终点位置

        Returns:
            生成的行人，如果失败返回None
        """
        pedestrian = Pedestrian(
            environment=self,
            start_position=start_pos,
            end_position=end_pos
        )

        pedestrian.plan_route(start_pos, end_pos)
        pedestrian.activate()

        self.add_agent(pedestrian)
        self._log_event('pedestrian_spawned', {
            'pedestrian_id': pedestrian.agent_id
        })

        return pedestrian

    def step(self) -> bool:
        """
        执行一个仿真步。

        Returns:
            是否继续仿真
        """
        if not self.is_running or self.is_paused:
            return False

        # 检查是否达到最大仿真时间
        if self.current_time >= self.config.max_simulation_time:
            self.stop()
            return False

        dt = self.config.time_step

        # 1. 更新交通信号灯
        # 1. ??????????? (????????????????????)
        skip_nodes = set()
        try:
            from city.agents.traffic_light_agent import TrafficLightAgent
            for agent in self.agents.values():
                if isinstance(agent, TrafficLightAgent):
                    skip_nodes.add(agent.control_node.node_id)
        except Exception:
            pass
        self.road_network.update_traffic_lights(dt, skip_nodes=skip_nodes)

        # 2. 更新所有智能体
        completed_agents = []
        for agent in list(self.agents.values()):
            agent.step(dt)

            # 检查是否完成
            if agent.state == AgentState.COMPLETED:
                completed_agents.append(agent.agent_id)

        # 3. 移除已完成的智能体
        for agent_id in completed_agents:
            self.remove_agent(agent_id)

        # 4. 更新仿真时间
        self.current_time += dt
        self.step_count += 1

        # 5. 实时延迟（如果需要）
        if self.config.real_time_factor > 0:
            time.sleep(dt / self.config.real_time_factor)

        return True

    def run(self, num_steps: int | None = None) -> None:
        """
        运行仿真。

        Args:
            num_steps: 运行的步数，None表示运行到最大时间
        """
        self.is_running = True
        self.is_paused = False

        target_steps = num_steps if num_steps else float('inf')
        steps_run = 0

        try:
            while self.is_running and steps_run < target_steps:
                if not self.step():
                    break
                steps_run += 1
        except KeyboardInterrupt:
            print("\n仿真被中断")
            self.pause()

    def start(self) -> None:
        """启动仿真。"""
        self.is_running = True
        self.is_paused = False

    def pause(self) -> None:
        """暂停仿真。"""
        self.is_paused = True

    def resume(self) -> None:
        """恢复仿真。"""
        self.is_paused = False

    def stop(self) -> None:
        """停止仿真。"""
        self.is_running = False
        self.is_paused = False

    def reset(self) -> None:
        """重置仿真环境。"""
        self.stop()
        self.current_time = 0.0
        self.step_count = 0

        # 清空所有智能体
        self.agents.clear()
        self.vehicles.clear()
        self.pedestrians.clear()
        self.traffic_managers.clear()
        self.traffic_planners.clear()

        # 重置统计
        self.statistics = {
            'total_vehicles_spawned': 0,
            'total_vehicles_completed': 0,
            'total_pedestrians_spawned': 0,
            'total_pedestrians_completed': 0,
            'average_travel_time': 0.0,
            'congestion_events': 0
        }

        self.event_log.clear()

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """记录事件。"""
        self.event_log.append({
            'time': self.current_time,
            'type': event_type,
            'data': data
        })

    def get_statistics(self) -> dict[str, Any]:
        """获取仿真统计信息。"""
        stats = self.statistics.copy()
        stats['current_time'] = self.current_time
        stats['active_vehicles'] = len(self.vehicles)
        stats['active_pedestrians'] = len(self.pedestrians)
        stats['total_agents'] = len(self.agents)

        # 计算完成率
        if stats['total_vehicles_spawned'] > 0:
            stats['vehicle_completion_rate'] = stats['total_vehicles_completed'] / stats['total_vehicles_spawned']
        else:
            stats['vehicle_completion_rate'] = 0.0

        return stats

    def get_state(self) -> dict[str, Any]:
        """获取当前环境状态。"""
        return {
            'time': self.current_time,
            'step': self.step_count,
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'num_agents': len(self.agents),
            'num_vehicles': len(self.vehicles),
            'num_pedestrians': len(self.pedestrians)
        }
