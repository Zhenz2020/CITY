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
    from city.agents.memory import AgentMemory


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
        use_llm: bool = False,
        enable_memory: bool = True,
        memory_capacity: int = 50
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
        
        # 记忆模块
        self._memory: AgentMemory | None = None
        self._enable_memory = enable_memory
        self._memory_capacity = memory_capacity

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

    # ==================== 记忆模块 ====================
    
    def get_memory(self) -> AgentMemory:
        """
        获取记忆模块（惰性初始化）。
        
        Returns:
            AgentMemory 实例
        """
        if self._memory is None and self._enable_memory:
            from city.agents.memory import AgentMemory
            self._memory = AgentMemory(
                agent=self,
                short_term_capacity=self._memory_capacity,
                enable_long_term=True,
                auto_summarize=True
            )
        return self._memory
    
    def has_memory(self) -> bool:
        """检查是否启用了记忆。"""
        return self._enable_memory
    
    def has_memory_data(self) -> bool:
        """检查是否已经生成可展示的记忆内容。"""
        return (
            self._enable_memory
            and self._memory is not None
            and getattr(self._memory, "_total_memories", 0) > 0
        )

    def record_perception(self, perception: dict[str, Any], importance: float = 3.0) -> None:
        """记录感知到记忆。"""
        if self._enable_memory:
            self.get_memory().add_perception(perception, importance)
    
    def record_decision(self, decision: dict[str, Any], context: dict[str, Any] | None = None, importance: float = 5.0) -> None:
        """记录决策到记忆。"""
        if self._enable_memory:
            self.get_memory().add_decision(decision, context, importance)
    
    def record_action(self, action: Any, result: Any | None = None, importance: float = 4.0) -> None:
        """记录行动到记忆。"""
        if self._enable_memory:
            self.get_memory().add_action(action, result, importance)
    
    def record_event(self, event: str, details: dict[str, Any] | None = None, importance: float = 6.0) -> None:
        """记录事件到记忆。"""
        if self._enable_memory:
            self.get_memory().add_event(event, details, importance)
    
    def get_memory_context(self, max_entries: int = 10) -> str:
        """获取记忆上下文供LLM使用。"""
        if self._enable_memory and self._memory:
            return self._memory.get_context_for_llm(max_entries)
        return ""
    
    def save_memory(self, filepath: str) -> None:
        """保存记忆到文件。"""
        if self._enable_memory and self._memory:
            self._memory.save_to_file(filepath)
