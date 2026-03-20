"""
智能体记忆模块。

为每个智能体提供独立的记忆存储，支持短期记忆和长期记忆。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from typing import Any, TYPE_CHECKING
from collections import deque

if TYPE_CHECKING:
    from city.agents.base import BaseAgent


@dataclass
class MemoryEntry:
    """记忆条目。"""
    timestamp: float          # 仿真时间戳
    real_time: float          # 真实时间戳
    memory_type: str          # 记忆类型: perception, decision, action, event, interaction
    content: dict[str, Any]   # 记忆内容
    importance: float = 1.0   # 重要性评分 (0-10)
    tags: list[str] | None = None  # 标签
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "timestamp": self.timestamp,
            "real_time": self.real_time,
            "memory_type": self.memory_type,
            "content": self.content,
            "importance": self.importance,
            "tags": self.tags or []
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """从字典创建。"""
        return cls(
            timestamp=data["timestamp"],
            real_time=data["real_time"],
            memory_type=data["memory_type"],
            content=data["content"],
            importance=data.get("importance", 1.0),
            tags=data.get("tags", [])
        )


class AgentMemory:
    """
    智能体记忆系统。
    
    为每个智能体提供独立的记忆存储，支持：
    - 短期记忆：最近的事件（有限容量）
    - 长期记忆：重要事件的持久化存储
    - 记忆检索：按类型、时间、标签查询
    - 记忆总结：自动总结历史经验
    
    Attributes:
        agent: 所属智能体
        short_term_capacity: 短期记忆容量
        short_term: 短期记忆队列
        long_term: 长期记忆列表
        working_memory: 工作记忆（当前上下文）
    """
    
    def __init__(
        self,
        agent: BaseAgent,
        short_term_capacity: int = 50,
        enable_long_term: bool = True,
        auto_summarize: bool = True
    ):
        self.agent = agent
        self.agent_id = agent.agent_id
        self.short_term_capacity = short_term_capacity
        self.enable_long_term = enable_long_term
        self.auto_summarize = auto_summarize
        
        # 短期记忆：固定容量的双端队列
        self.short_term: deque[MemoryEntry] = deque(maxlen=short_term_capacity)
        
        # 长期记忆：重要事件的列表
        self.long_term: list[MemoryEntry] = []
        
        # 工作记忆：当前会话的上下文
        self.working_memory: dict[str, Any] = {}
        
        # 记忆统计
        self._total_memories = 0
        self._summarized_count = 0
        
        # 记忆摘要（由LLM生成）
        self._memory_summary: str = ""
        self._last_summary_time: float = 0.0
    
    # ==================== 记忆存储 ====================
    
    def add(
        self,
        memory_type: str,
        content: dict[str, Any],
        importance: float = 1.0,
        tags: list[str] | None = None,
        timestamp: float | None = None
    ) -> MemoryEntry:
        """
        添加记忆。
        
        Args:
            memory_type: 记忆类型 (perception/decision/action/event/interaction)
            content: 记忆内容
            importance: 重要性评分 (0-10)
            tags: 标签列表
            timestamp: 时间戳（默认当前仿真时间）
            
        Returns:
            创建的记忆条目
        """
        entry = MemoryEntry(
            timestamp=timestamp or self._get_current_time(),
            real_time=time.time(),
            memory_type=memory_type,
            content=content,
            importance=importance,
            tags=tags or []
        )
        
        # 添加到短期记忆
        self.short_term.append(entry)
        self._total_memories += 1
        
        # 重要记忆同时存入长期记忆
        if self.enable_long_term and importance >= 7.0:
            self.long_term.append(entry)
            
            # 限制长期记忆大小
            if len(self.long_term) > 200:
                # 移除最不重要且最旧的记忆
                self.long_term.sort(key=lambda x: (x.importance, x.timestamp))
                self.long_term.pop(0)
        
        return entry
    
    def add_perception(self, perception: dict[str, Any], importance: float = 3.0) -> MemoryEntry:
        """添加感知记忆。"""
        return self.add(
            memory_type="perception",
            content=perception,
            importance=importance,
            tags=["perception", "environment"]
        )
    
    def add_decision(self, decision: dict[str, Any], context: dict[str, Any] | None = None, importance: float = 5.0) -> MemoryEntry:
        """添加决策记忆。"""
        content = {
            "decision": decision,
            "context": context or {}
        }
        return self.add(
            memory_type="decision",
            content=content,
            importance=importance,
            tags=["decision", "reasoning"]
        )
    
    def add_action(self, action: Any, result: Any | None = None, importance: float = 4.0) -> MemoryEntry:
        """添加行动记忆。"""
        content = {
            "action": action,
            "result": result
        }
        return self.add(
            memory_type="action",
            content=content,
            importance=importance,
            tags=["action", "execution"]
        )
    
    def add_event(self, event: str, details: dict[str, Any] | None = None, importance: float = 6.0) -> MemoryEntry:
        """添加事件记忆。"""
        content = {
            "event": event,
            "details": details or {}
        }
        return self.add(
            memory_type="event",
            content=content,
            importance=importance,
            tags=["event"]
        )
    
    def add_interaction(self, with_agent: str, interaction_type: str, content: dict[str, Any], importance: float = 5.0) -> MemoryEntry:
        """添加交互记忆。"""
        entry_content = {
            "with_agent": with_agent,
            "interaction_type": interaction_type,
            "content": content
        }
        return self.add(
            memory_type="interaction",
            content=entry_content,
            importance=importance,
            tags=["interaction", f"agent_{with_agent}"]
        )
    
    # ==================== 记忆检索 ====================
    
    def get_recent(self, count: int = 10, memory_type: str | None = None) -> list[MemoryEntry]:
        """
        获取最近的记忆。
        
        Args:
            count: 返回数量
            memory_type: 按类型筛选
            
        Returns:
            记忆条目列表
        """
        memories = list(self.short_term)
        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]
        return memories[-count:]
    
    def get_by_type(self, memory_type: str, limit: int = 20) -> list[MemoryEntry]:
        """按类型获取记忆。"""
        memories = [m for m in self.short_term if m.memory_type == memory_type]
        return memories[-limit:]
    
    def get_by_tag(self, tag: str, limit: int = 20) -> list[MemoryEntry]:
        """按标签获取记忆。"""
        memories = [m for m in self.short_term if tag in (m.tags or [])]
        return memories[-limit:]
    
    def get_important(self, min_importance: float = 7.0, limit: int = 20) -> list[MemoryEntry]:
        """获取重要记忆。"""
        memories = [m for m in self.short_term if m.importance >= min_importance]
        memories.sort(key=lambda x: x.importance, reverse=True)
        return memories[:limit]
    
    def get_long_term_memories(self, limit: int = 50) -> list[MemoryEntry]:
        """获取长期记忆。"""
        return self.long_term[-limit:]
    
    def search(self, keyword: str, limit: int = 10) -> list[MemoryEntry]:
        """
        关键词搜索记忆（简单实现）。
        
        Args:
            keyword: 关键词
            limit: 返回数量
            
        Returns:
            匹配的记忆列表
        """
        keyword = keyword.lower()
        results = []
        
        for entry in reversed(self.short_term):
            # 搜索内容中的文本
            content_str = json.dumps(entry.content, default=str).lower()
            if keyword in content_str:
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results
    
    # ==================== 工作记忆 ====================
    
    def set_working_memory(self, key: str, value: Any) -> None:
        """设置工作记忆。"""
        self.working_memory[key] = value
    
    def get_working_memory(self, key: str, default: Any = None) -> Any:
        """获取工作记忆。"""
        return self.working_memory.get(key, default)
    
    def clear_working_memory(self) -> None:
        """清空工作记忆。"""
        self.working_memory.clear()
    
    # ==================== 记忆总结 ====================
    
    def generate_summary(self, use_llm: bool = False) -> str:
        """
        生成记忆摘要。
        
        Args:
            use_llm: 是否使用LLM生成摘要
            
        Returns:
            摘要文本
        """
        if not self.short_term:
            return "暂无记忆"
        
        # 简单的规则摘要
        summary_parts = []
        
        # 统计各类型记忆
        type_counts = {}
        for entry in self.short_term:
            type_counts[entry.memory_type] = type_counts.get(entry.memory_type, 0) + 1
        
        summary_parts.append(f"记忆总数: {len(self.short_term)} (短期) / {len(self.long_term)} (长期)")
        summary_parts.append(f"记忆类型: {', '.join(f'{k}:{v}' for k, v in type_counts.items())}")
        
        # 重要事件
        important = self.get_important(min_importance=8.0, limit=3)
        if important:
            summary_parts.append(f"重要事件: {len(important)} 件")
        
        self._memory_summary = " | ".join(summary_parts)
        self._last_summary_time = self._get_current_time()
        
        return self._memory_summary
    
    def get_context_for_llm(self, max_entries: int = 10) -> str:
        """
        获取适合LLM使用的上下文记忆。
        
        Args:
            max_entries: 最大条目数
            
        Returns:
            格式化的记忆文本
        """
        memories = self.get_recent(count=max_entries)
        if not memories:
            return "暂无历史记忆"
        
        lines = ["## 历史记忆", ""]
        
        for entry in memories:
            time_str = f"[{entry.timestamp:.1f}s]"
            if entry.memory_type == "perception":
                lines.append(f"{time_str} 感知: {entry.content.get('summary', '环境状态')}")
            elif entry.memory_type == "decision":
                decision = entry.content.get("decision", {})
                lines.append(f"{time_str} 决策: {decision.get('action', '做出决策')}")
            elif entry.memory_type == "action":
                action = entry.content.get("action", "执行动作")
                lines.append(f"{time_str} 行动: {action}")
            elif entry.memory_type == "event":
                event = entry.content.get("event", "事件发生")
                lines.append(f"{time_str} 事件: {event}")
            elif entry.memory_type == "interaction":
                with_agent = entry.content.get("with_agent", "其他智能体")
                lines.append(f"{time_str} 交互: 与 {with_agent}")
        
        return "\n".join(lines)
    
    # ==================== 序列化 ====================
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent.agent_type.name.lower() if hasattr(self.agent, "agent_type") else "unknown",
            "short_term": [m.to_dict() for m in self.short_term],
            "long_term": [m.to_dict() for m in self.long_term],
            "working_memory": self.working_memory,
            "statistics": {
                "total_memories": self._total_memories,
                "short_term_count": len(self.short_term),
                "long_term_count": len(self.long_term),
                "summarized_count": self._summarized_count
            }
        }
    
    def save_to_file(self, filepath: str) -> None:
        """保存到文件。"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2, default=str)
    
    @classmethod
    def load_from_file(cls, agent: BaseAgent, filepath: str) -> AgentMemory:
        """从文件加载。"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        memory = cls(agent, short_term_capacity=len(data.get("short_term", [])))
        
        for entry_data in data.get("short_term", []):
            memory.short_term.append(MemoryEntry.from_dict(entry_data))
        
        for entry_data in data.get("long_term", []):
            memory.long_term.append(MemoryEntry.from_dict(entry_data))
        
        memory.working_memory = data.get("working_memory", {})
        memory._total_memories = data.get("statistics", {}).get("total_memories", 0)
        
        return memory
    
    # ==================== 内部方法 ====================
    
    def _get_current_time(self) -> float:
        """获取当前仿真时间。"""
        if self.agent and self.agent.environment:
            return self.agent.environment.current_time
        return 0.0
    
    def __len__(self) -> int:
        """返回记忆总数。"""
        return len(self.short_term) + len(self.long_term)
    
    def __repr__(self) -> str:
        return f"AgentMemory({self.agent_id}, short={len(self.short_term)}, long={len(self.long_term)})"
