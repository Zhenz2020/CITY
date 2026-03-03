"""
LLM 决策管理器 - 支持多车并行决策。

使用线程池并发处理多个 LLM 请求，避免阻塞仿真循环。
"""

from __future__ import annotations

import threading
import queue
import concurrent.futures
from typing import Any, Callable
from city.llm.agent_llm_interface import AgentLLMInterface


class LLMManager:
    """
    LLM 决策管理器。
    
    管理多个智能体的 LLM 决策请求，支持并发处理。
    """
    
    def __init__(self, max_workers: int = 5) -> None:
        """
        初始化 LLM 管理器。
        
        Args:
            max_workers: 最大并发线程数
        """
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.pending_decisions: dict[str, concurrent.futures.Future] = {}
        self.results: dict[str, dict] = {}
        self.lock = threading.Lock()
    
    def request_decision(self, agent_id: str, llm_interface: AgentLLMInterface, perception: dict[str, Any]) -> bool:
        """
        请求 LLM 决策（非阻塞）。
        
        Args:
            agent_id: 智能体ID
            llm_interface: LLM接口
            perception: 感知数据
            
        Returns:
            是否成功提交请求
        """
        with self.lock:
            # 如果已有 pending 的请求，跳过
            if agent_id in self.pending_decisions and not self.pending_decisions[agent_id].done():
                return False
            
            # 提交异步任务
            future = self.executor.submit(self._get_decision, llm_interface, perception, agent_id)
            self.pending_decisions[agent_id] = future
            return True
    
    def _get_decision(self, llm_interface: AgentLLMInterface, perception: dict, agent_id: str) -> dict:
        """在后台线程中获取 LLM 决策。"""
        try:
            result = llm_interface.get_llm_decision(perception)
            with self.lock:
                self.results[agent_id] = result
            print(f"[LLMManager] {agent_id} 决策完成: {result.get('action', 'unknown')}")
            return result
        except Exception as e:
            print(f"[LLMManager] {agent_id} 决策失败: {e}")
            with self.lock:
                self.results[agent_id] = {"action": "maintain", "reason": "LLM失败", "confidence": 0.3}
            return self.results[agent_id]
    
    def get_result(self, agent_id: str) -> dict | None:
        """
        获取决策结果（非阻塞）。
        
        Args:
            agent_id: 智能体ID
            
        Returns:
            决策结果，如果没有则返回 None
        """
        with self.lock:
            # 检查是否有完成的 future
            if agent_id in self.pending_decisions:
                future = self.pending_decisions[agent_id]
                if future.done():
                    try:
                        result = future.result(timeout=0.1)
                        self.results[agent_id] = result
                        del self.pending_decisions[agent_id]
                        return result
                    except:
                        del self.pending_decisions[agent_id]
            
            # 返回缓存的结果
            return self.results.get(agent_id)
    
    def has_pending(self, agent_id: str) -> bool:
        """检查是否有 pending 的决策请求。"""
        with self.lock:
            if agent_id in self.pending_decisions:
                return not self.pending_decisions[agent_id].done()
            return False
    
    def clear_result(self, agent_id: str) -> None:
        """清除结果。"""
        with self.lock:
            self.results.pop(agent_id, None)
            if agent_id in self.pending_decisions:
                future = self.pending_decisions.pop(agent_id)
                if not future.done():
                    future.cancel()
    
    def shutdown(self) -> None:
        """关闭管理器。"""
        self.executor.shutdown(wait=False)


# 全局 LLM 管理器实例
_global_llm_manager: LLMManager | None = None


def get_llm_manager() -> LLMManager:
    """获取全局 LLM 管理器实例。"""
    global _global_llm_manager
    if _global_llm_manager is None:
        _global_llm_manager = LLMManager(max_workers=5)
    return _global_llm_manager


def set_llm_manager(manager: LLMManager) -> None:
    """设置全局 LLM 管理器实例。"""
    global _global_llm_manager
    _global_llm_manager = manager
