"""
智能体基类。

所有交通仿真智能体的抽象基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from city.environment.road_network import RoadNetwork, Node, Edge, Lane
    from city.simulation.environment import SimulationEnvironment
    from city.llm.agent_llm_interface import AgentLLMInterface


class AgentState(Enum):
    """智能体状态。"""
    IDLE = auto()        # 空闲
    ACTIVE = auto()      # 活动
    PAUSED = auto()      # 暂停
    COMPLETED = auto()   # 完成


class AgentType(Enum):
    """智能体类型。"""
    VEHICLE = auto()
    PEDESTRIAN = auto()
    TRAFFIC_MANAGER = auto()
    TRAFFIC_PLANNER = auto()
    TRAFFIC_ENGINEER = auto()
    URBAN_PLANNER = auto()


class BaseAgent(ABC):
    """
    智能体基类。

    所有交通仿真智能体的抽象基类，定义通用接口。

    Attributes:
        agent_id: 智能体唯一标识
        agent_type: 智能体类型
        state: 当前状态
        environment: 所属仿真环境
        llm_interface: LLM接口（可选）
        use_llm: 是否使用LLM进行决策
    """

    _id_counter = 0

    def __init__(
        self,
        agent_type: AgentType,
        environment: SimulationEnvironment | None = None,
        use_llm: bool = False
    ) -> None:
        BaseAgent._id_counter += 1
        self.agent_id = f"{agent_type.name.lower()}_{BaseAgent._id_counter}"
        self.agent_type = agent_type
        self.state = AgentState.IDLE
        self.environment = environment
        self.use_llm = use_llm

        # LLM接口（延迟初始化）
        self._llm_interface: AgentLLMInterface | None = None

        # 仿真相关
        self.creation_time = 0.0
        self.lifetime = 0.0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.agent_id}, state={self.state.name})"

    @abstractmethod
    def update(self, dt: float) -> None:
        """
        更新智能体状态。

        Args:
            dt: 时间步长（秒）
        """
        pass

    @abstractmethod
    def perceive(self) -> dict[str, Any]:
        """
        感知环境，获取当前状态信息。

        Returns:
            包含感知信息的字典
        """
        pass

    @abstractmethod
    def decide(self) -> Any:
        """
        根据感知信息做出决策。

        Returns:
            决策结果
        """
        pass

    @abstractmethod
    def act(self, action: Any) -> None:
        """
        执行决策动作。

        Args:
            action: 要执行的动作
        """
        pass

    def step(self, dt: float) -> None:
        """
        智能体的一个完整决策-行动循环。

        Args:
            dt: 时间步长（秒）
        """
        if self.state != AgentState.ACTIVE:
            return

        # 感知 -> 决策 -> 行动
        perception = self.perceive()
        decision = self.decide()
        self.act(decision)

        # 更新状态和生命周期
        self.update(dt)
        self.lifetime += dt

    def set_state(self, state: AgentState) -> None:
        """设置智能体状态。"""
        self.state = state

    def activate(self) -> None:
        """激活智能体。"""
        self.state = AgentState.ACTIVE

    def pause(self) -> None:
        """暂停智能体。"""
        self.state = AgentState.PAUSED

    def complete(self) -> None:
        """标记智能体完成。"""
        self.state = AgentState.COMPLETED

    def set_environment(self, environment: SimulationEnvironment) -> None:
        """设置所属仿真环境。"""
        self.environment = environment

    def get_llm_interface(self) -> AgentLLMInterface | None:
        """获取LLM接口（惰性初始化）。"""
        if self.use_llm and self._llm_interface is None:
            from city.llm.agent_llm_interface import AgentLLMInterface, get_global_llm_client
            self._llm_interface = AgentLLMInterface(
                agent=self,
                llm_client=get_global_llm_client(),
                use_llm=True
            )
        return self._llm_interface

    def llm_decide(self, perception: dict[str, Any]) -> dict[str, Any] | None:
        """
        使用LLM进行决策。

        Args:
            perception: 感知信息

        Returns:
            LLM的决策建议，如果未启用LLM则返回None
        """
        if not self.use_llm:
            return None

        llm_interface = self.get_llm_interface()
        if llm_interface:
            return llm_interface.get_llm_decision(perception)
        return None
