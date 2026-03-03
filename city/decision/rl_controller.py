"""
强化学习控制器。

用于训练交通信号控制等决策任务。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from enum import Enum

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.environment.road_network import TrafficLight


class RLAction(Enum):
    """RL动作空间。"""
    INCREASE_GREEN = 0
    DECREASE_GREEN = 1
    KEEP_CURRENT = 2


class RLState:
    """RL状态表示。"""

    def __init__(
        self,
        queue_lengths: list[float],
        avg_speeds: list[float],
        current_phase: int,
        elapsed_time: float
    ) -> None:
        self.queue_lengths = queue_lengths
        self.avg_speeds = avg_speeds
        self.current_phase = current_phase
        self.elapsed_time = elapsed_time

    def to_array(self) -> list[float]:
        """转换为数组表示。"""
        return self.queue_lengths + self.avg_speeds + [self.current_phase, self.elapsed_time]


class TrafficSignalRLController:
    """
    交通信号灯强化学习控制器。

    使用简单的Q-learning算法优化信号灯配时。

    Attributes:
        traffic_light: 控制的交通信号灯
        learning_rate: 学习率
        discount_factor: 折扣因子
        epsilon: 探索率
        q_table: Q值表
    """

    def __init__(
        self,
        traffic_light: TrafficLight,
        learning_rate: float = 0.1,
        discount_factor: float = 0.9,
        epsilon: float = 0.1
    ) -> None:
        self.traffic_light = traffic_light
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon

        # 简化的Q表（实际应用中需要更复杂的表示）
        self.q_table: dict[tuple, list[float]] = {}

        # 上次状态和动作
        self.last_state: RLState | None = None
        self.last_action: RLAction | None = None

    def get_state(self, environment: SimulationEnvironment) -> RLState:
        """获取当前状态。"""
        # 收集相关交通数据
        queue_lengths = [0.0, 0.0, 0.0, 0.0]  # 简化：四个方向的排队长度
        avg_speeds = [10.0, 10.0, 10.0, 10.0]  # 简化：四个方向的平均速度

        # 映射信号灯状态到相位
        phase_map = {
            'RED': 0,
            'YELLOW': 1,
            'GREEN': 2
        }
        current_phase = phase_map.get(self.traffic_light.state.name, 0)

        return RLState(
            queue_lengths=queue_lengths,
            avg_speeds=avg_speeds,
            current_phase=current_phase,
            elapsed_time=self.traffic_light.current_phase_time
        )

    def select_action(self, state: RLState) -> RLAction:
        """选择动作（epsilon-贪婪策略）。"""
        import random

        state_key = tuple(state.to_array())

        # 初始化Q值
        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0, 0.0, 0.0]

        # epsilon-贪婪
        if random.random() < self.epsilon:
            return random.choice(list(RLAction))
        else:
            q_values = self.q_table[state_key]
            return RLAction(q_values.index(max(q_values)))

    def calculate_reward(self, state: RLState) -> float:
        """计算奖励。"""
        # 基于平均速度的奖励
        avg_speed = sum(state.avg_speeds) / len(state.avg_speeds) if state.avg_speeds else 0
        # 惩罚排队长度
        total_queue = sum(state.queue_lengths)

        return avg_speed - total_queue * 0.1

    def update_q_table(
        self,
        state: RLState,
        action: RLAction,
        reward: float,
        next_state: RLState
    ) -> None:
        """更新Q表。"""
        state_key = tuple(state.to_array())
        next_state_key = tuple(next_state.to_array())

        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0, 0.0, 0.0]
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = [0.0, 0.0, 0.0]

        # Q-learning更新
        current_q = self.q_table[state_key][action.value]
        max_next_q = max(self.q_table[next_state_key])
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        self.q_table[state_key][action.value] = new_q

    def apply_action(self, action: RLAction) -> None:
        """应用动作到信号灯。"""
        if action == RLAction.INCREASE_GREEN:
            self.traffic_light.green_duration = min(
                self.traffic_light.green_duration + 5,
                60
            )
        elif action == RLAction.DECREASE_GREEN:
            self.traffic_light.green_duration = max(
                self.traffic_light.green_duration - 5,
                10
            )
        # KEEP_CURRENT: 不操作

    def step(self, environment: SimulationEnvironment) -> None:
        """执行一个RL步。"""
        # 获取当前状态
        current_state = self.get_state(environment)

        # 如果有上次的经验，更新Q表
        if self.last_state is not None and self.last_action is not None:
            reward = self.calculate_reward(current_state)
            self.update_q_table(
                self.last_state,
                self.last_action,
                reward,
                current_state
            )

        # 选择并执行动作
        action = self.select_action(current_state)
        self.apply_action(action)

        # 保存当前经验
        self.last_state = current_state
        self.last_action = action

    def get_policy(self) -> dict[str, Any]:
        """获取当前策略信息。"""
        return {
            'q_table_size': len(self.q_table),
            'learning_rate': self.learning_rate,
            'epsilon': self.epsilon,
            'current_green_duration': self.traffic_light.green_duration
        }
