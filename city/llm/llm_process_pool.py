"""
LLM 多进程池 - 真正利用多核CPU。

使用 multiprocessing 替代 threading，绕过Python GIL限制。
"""

from __future__ import annotations

import multiprocessing as mp
from multiprocessing import Pool, Manager
from typing import Any, Callable
import time
import os


# 全局变量，在每个进程初始化时设置
_process_llm_client = None


def init_worker(config_dict: dict):
    """
    进程池worker初始化函数。
    在每个子进程启动时调用，创建独立的LLM客户端。
    """
    global _process_llm_client
    try:
        from city.llm.llm_client import LLMClient, LLMConfig, LLMProvider
        
        provider_name = config_dict.get('provider', 'SILICONFLOW')
        provider = LLMProvider[provider_name]
        
        config = LLMConfig(
            provider=provider,
            api_key=config_dict.get('api_key'),
            base_url=config_dict.get('base_url'),
            model=config_dict.get('model', 'Qwen/Qwen3-14B'),
            temperature=config_dict.get('temperature', 0.7),
            max_tokens=config_dict.get('max_tokens', 500),
            timeout=config_dict.get('timeout', 30.0)
        )
        
        _process_llm_client = LLMClient(config)
        print(f"[Process {os.getpid()}] LLM客户端初始化完成")
    except Exception as e:
        print(f"[Process {os.getpid()}] LLM客户端初始化失败: {e}")
        _process_llm_client = None


def process_llm_request(task: dict) -> dict:
    """
    在子进程中执行LLM请求。
    
    Args:
        task: 包含agent_id, perception, system_prompt的字典
        
    Returns:
        包含agent_id, decision, error的结果字典
    """
    global _process_llm_client
    
    agent_id = task.get('agent_id', 'unknown')
    perception = task.get('perception', {})
    system_prompt = task.get('system_prompt', '')
    
    try:
        if _process_llm_client is None or not _process_llm_client.is_available():
            return {
                'agent_id': agent_id,
                'error': 'LLM客户端不可用',
                'decision': {'action': 'maintain', 'reason': 'LLM不可用', 'confidence': 0.5}
            }
        
        # 构建提示词
        prompt = f"""当前交通状况：
{perception}

请提供决策（以JSON格式）：
{{"action": "动作", "reason": "原因", "confidence": 0.9}}"""
        
        # 调用LLM
        response = _process_llm_client.structured_chat(prompt, system_prompt)
        
        if isinstance(response, dict):
            return {
                'agent_id': agent_id,
                'decision': response,
                'error': None
            }
        else:
            return {
                'agent_id': agent_id,
                'decision': {'action': 'maintain', 'reason': str(response), 'confidence': 0.5},
                'error': None
            }
            
    except Exception as e:
        return {
            'agent_id': agent_id,
            'error': str(e),
            'decision': {'action': 'maintain', 'reason': f'LLM错误: {str(e)[:50]}', 'confidence': 0.3}
        }


class LLMProcessPool:
    """
    LLM多进程池 - 真正利用多核CPU。
    
    每个进程有独立的LLM客户端，并行处理请求。
    """
    
    def __init__(self, num_processes: int | None = None) -> None:
        """
        初始化多进程池。
        
        Args:
            num_processes: 进程数，默认为CPU核心数
        """
        self.num_processes = num_processes or max(2, mp.cpu_count() - 1)
        self.pool: Pool | None = None
        self.config_dict: dict = {}
        self.manager = Manager()
        self.results = self.manager.dict()
        self.pending_tasks = self.manager.dict()
        
    def initialize(self, api_keys: list[str], base_url: str, model: str, **kwargs) -> None:
        """
        初始化进程池。
        
        Args:
            api_keys: API Key列表，每个进程使用不同的Key
            base_url: API基础URL
            model: 模型名称
        """
        if not api_keys:
            print("[LLMProcessPool] 错误: 没有API Key")
            return
            
        # 为每个进程分配一个API Key（循环使用）
        self.config_dict = {
            'api_keys': api_keys,
            'base_url': base_url,
            'model': model,
            'provider': kwargs.get('provider', 'SILICONFLOW'),
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 500),
            'timeout': kwargs.get('timeout', 30.0),
        }
        
        # 创建进程池
        # 注意：multiprocessing在Windows上需要使用spawn模式
        if os.name == 'nt':  # Windows
            mp.set_start_method('spawn', force=True)
        
        # 为每个进程准备配置
        process_configs = []
        for i in range(self.num_processes):
            config = self.config_dict.copy()
            config['api_key'] = api_keys[i % len(api_keys)]
            process_configs.append(config)
        
        self.pool = Pool(
            processes=self.num_processes,
            initializer=init_worker,
            initargs=(process_configs[0],)  # 简化：所有进程用相同配置
        )
        
        print(f"[LLMProcessPool] 已启动 {self.num_processes} 个进程，使用 {len(api_keys)} 个API Key")
    
    def submit(self, agent_id: str, perception: dict, system_prompt: str = '') -> None:
        """
        提交LLM请求（异步）。
        
        Args:
            agent_id: 智能体ID
            perception: 感知信息
            system_prompt: 系统提示词
        """
        if self.pool is None:
            return
            
        task = {
            'agent_id': agent_id,
            'perception': perception,
            'system_prompt': system_prompt
        }
        
        # 异步提交任务
        result = self.pool.apply_async(process_llm_request, args=(task,))
        self.pending_tasks[agent_id] = result
    
    def get_result(self, agent_id: str) -> dict | None:
        """
        获取决策结果（非阻塞）。
        
        Args:
            agent_id: 智能体ID
            
        Returns:
            决策结果，如果没有则返回None
        """
        if agent_id not in self.pending_tasks:
            return None
            
        result = self.pending_tasks[agent_id]
        
        if result.ready():
            try:
                decision = result.get(timeout=0.1)
                del self.pending_tasks[agent_id]
                return decision
            except Exception as e:
                print(f"[LLMProcessPool] 获取结果失败: {e}")
                del self.pending_tasks[agent_id]
                return None
        
        return None
    
    def has_pending(self, agent_id: str) -> bool:
        """检查是否有pending的请求。"""
        return agent_id in self.pending_tasks
    
    def shutdown(self) -> None:
        """关闭进程池。"""
        if self.pool:
            self.pool.close()
            self.pool.join()
            print("[LLMProcessPool] 进程池已关闭")


# 全局进程池实例
_global_process_pool: LLMProcessPool | None = None


def get_process_pool() -> LLMProcessPool:
    """获取全局进程池。"""
    global _global_process_pool
    if _global_process_pool is None:
        _global_process_pool = LLMProcessPool()
    return _global_process_pool


def init_process_pool_from_config(config_path: str = "config/siliconflow_config.json") -> LLMProcessPool:
    """
    从配置文件初始化进程池。
    """
    import json
    
    pool = get_process_pool()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            api_keys = config.get('api_key', [])
            if isinstance(api_keys, str):
                api_keys = [api_keys]
                
            pool.initialize(
                api_keys=api_keys,
                base_url=config.get('base_url', 'https://api.siliconflow.cn/v1'),
                model=config.get('model', 'Qwen/Qwen3-14B'),
                temperature=config.get('temperature', 0.7),
                max_tokens=config.get('max_tokens', 500),
            )
        except Exception as e:
            print(f"[LLMProcessPool] 初始化失败: {e}")
    
    return pool
