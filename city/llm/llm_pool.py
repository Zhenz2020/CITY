"""
LLM 客户端池 - 支持多API Key轮询。

用于高并发场景，多个API Key可以同时处理更多请求。
"""

from __future__ import annotations

import threading
from typing import Any
from city.llm.llm_client import LLMClient, LLMConfig, LLMProvider


class LLMClientPool:
    """
    LLM 客户端池。
    
    管理多个LLM客户端，支持API Key轮询和负载均衡。
    
    Attributes:
        clients: LLM客户端列表
        current_index: 当前使用的客户端索引
        lock: 线程锁
    """
    
    def __init__(self) -> None:
        self.clients: list[LLMClient] = []
        self.current_index = 0
        self.lock = threading.Lock()
    
    def add_client(self, client: LLMClient) -> None:
        """添加一个LLM客户端。"""
        with self.lock:
            self.clients.append(client)
            print(f"[LLMPool] 添加客户端 #{len(self.clients)}, 当前总数: {len(self.clients)}")
    
    def add_api_keys(self, api_keys: list[str], base_url: str | None = None, 
                     model: str = "Qwen/Qwen3-14B", provider: LLMProvider = LLMProvider.SILICONFLOW) -> None:
        """
        批量添加API Key。
        
        Args:
            api_keys: API Key列表
            base_url: API基础URL
            model: 模型名称
            provider: LLM提供商
        """
        for i, key in enumerate(api_keys):
            if not key or key.strip() == "":
                print(f"[LLMPool] 跳过空API Key #{i+1}")
                continue
                
            config = LLMConfig(
                provider=provider,
                api_key=key.strip(),
                base_url=base_url,
                model=model,
                temperature=0.7,
                max_tokens=500,
                timeout=30.0
            )
            client = LLMClient(config)
            if client.is_available():
                self.add_client(client)
            else:
                print(f"[LLMPool] API Key #{i+1} 初始化失败")
        
        print(f"[LLMPool] 总共添加 {len(self.clients)} 个客户端")
    
    def get_client(self) -> LLMClient | None:
        """
        获取一个可用的客户端（轮询）。
        
        Returns:
            LLM客户端，如果没有则返回None
        """
        with self.lock:
            if not self.clients:
                return None
            
            # 轮询选择
            client = self.clients[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.clients)
            return client
    
    def get_client_for_agent(self, agent_id: str) -> LLMClient | None:
        """
        为特定智能体分配客户端（一致性哈希）。
        
        确保同一个智能体总是使用相同的API Key，便于追踪和限流控制。
        
        Args:
            agent_id: 智能体ID
            
        Returns:
            LLM客户端
        """
        with self.lock:
            if not self.clients:
                return None
            
            # 基于agent_id计算索引，保证同一agent总是分配到同一client
            index = hash(agent_id) % len(self.clients)
            return self.clients[index]
    
    def is_available(self) -> bool:
        """检查是否有可用的客户端。"""
        return len(self.clients) > 0
    
    def get_stats(self) -> dict[str, Any]:
        """获取池统计信息。"""
        return {
            "total_clients": len(self.clients),
            "available": self.is_available(),
        }


# 全局LLM客户端池
_global_llm_pool: LLMClientPool | None = None


def get_llm_pool() -> LLMClientPool:
    """获取全局LLM客户端池。"""
    global _global_llm_pool
    if _global_llm_pool is None:
        _global_llm_pool = LLMClientPool()
    return _global_llm_pool


def init_llm_pool_from_env() -> LLMClientPool:
    """
    从环境变量初始化LLM客户端池。
    
    支持多个API Key，格式：
    - SILICONFLOW_API_KEY: 主Key
    - SILICONFLOW_API_KEY_1, SILICONFLOW_API_KEY_2, ...: 备用Key
    
    Returns:
        LLM客户端池
    """
    import os
    
    pool = get_llm_pool()
    
    # 收集所有API Key
    api_keys = []
    
    # 主Key
    main_key = os.getenv("SILICONFLOW_API_KEY")
    if main_key:
        api_keys.append(main_key)
    
    # 备用Keys
    for i in range(1, 10):  # 支持最多9个备用Key
        key = os.getenv(f"SILICONFLOW_API_KEY_{i}")
        if key:
            api_keys.append(key)
    
    # 从配置文件中读取（支持JSON数组格式）
    config_path = os.getenv("SILICONFLOW_CONFIG_PATH", "config/siliconflow_config.json")
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if isinstance(config.get("api_key"), list):
                    api_keys.extend(config["api_key"])
                elif config.get("api_key"):
                    api_keys.append(config["api_key"])
                
                base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
                model = config.get("model", "Qwen/Qwen3-14B")
        except Exception as e:
            print(f"[LLMPool] 读取配置文件失败: {e}")
            base_url = "https://api.siliconflow.cn/v1"
            model = "Qwen/Qwen3-14B"
    else:
        base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        model = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-14B")
    
    # 去重
    api_keys = list(dict.fromkeys(api_keys))  # 保持顺序去重
    
    if api_keys:
        pool.add_api_keys(api_keys, base_url=base_url, model=model)
    else:
        print("[LLMPool] 警告: 未找到任何API Key")
    
    return pool
