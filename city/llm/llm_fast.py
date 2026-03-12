"""
快速LLM决策 - 批量处理优化。

使用异步IO和批量请求提高吞吐量。
"""

from __future__ import annotations

import asyncio
import aiohttp
import json
from typing import Any
from dataclasses import dataclass
import time


@dataclass
class LLMRequest:
    """LLM请求。"""
    agent_id: str
    perception: dict
    system_prompt: str
    timestamp: float


class FastLLMClient:
    """
    快速LLM客户端 - 使用异步IO。
    
    特点：
    - 异步并发请求
    - 连接池复用
    - 批量处理
    """
    
    def __init__(self, api_keys: list[str], base_url: str, model: str):
        self.api_keys = api_keys
        self.base_url = base_url
        self.model = model
        self.current_key_index = 0
        self.session: aiohttp.ClientSession | None = None
        self.request_queue: list[LLMRequest] = []
        self.results: dict[str, dict] = {}
        
    async def __aenter__(self):
        """异步上下文管理器入口。"""
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.api_keys[0]}"}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口。"""
        if self.session:
            await self.session.close()
            
    def _get_next_api_key(self) -> str:
        """轮询获取下一个API Key。"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
        
    async def request_decision(self, agent_id: str, perception: dict, system_prompt: str = "") -> dict:
        """
        请求LLM决策。
        
        使用异步IO发送请求，不阻塞主线程。
        """
        if not self.session:
            return {"action": "maintain", "reason": "LLM未初始化", "confidence": 0.5}
        
        api_key = self._get_next_api_key()
        
        prompt = f"""当前交通状况：
{json.dumps(perception, ensure_ascii=False)}

请提供决策（以JSON格式）：
{{"action": "动作(accelerate/decelerate/maintain/stop/proceed)", "reason": "原因", "confidence": 0.9}}"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or "你是车辆驾驶专家，提供安全的驾驶决策。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500,
            "response_format": {"type": "json_object"}
        }
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    try:
                        result = json.loads(content)
                        return result
                    except:
                        return {"action": "maintain", "reason": content[:100], "confidence": 0.5}
                else:
                    return {"action": "maintain", "reason": f"API错误: {response.status}", "confidence": 0.3}
                    
        except asyncio.TimeoutError:
            return {"action": "maintain", "reason": "LLM请求超时", "confidence": 0.3}
        except Exception as e:
            return {"action": "maintain", "reason": f"LLM错误: {str(e)[:50]}", "confidence": 0.3}


class SimpleLLMCache:
    """
    简单的LLM结果缓存。
    
    缓存相似的感知输入，避免重复请求。
    """
    
    def __init__(self, max_size: int = 1000, ttl: float = 5.0):
        self.cache: dict[str, tuple[dict, float]] = {}
        self.max_size = max_size
        self.ttl = ttl  # 缓存生存时间（秒）
        
    def _make_key(self, perception: dict) -> str:
        """生成缓存键。"""
        # 简化感知信息用于缓存键
        key_parts = [
            perception.get('traffic_light', {}).get('state', 'unknown'),
            str(int(perception.get('front_vehicle', {}).get('distance', 999) / 10)),  # 距离分桶
            str(int(perception.get('self', {}).get('velocity', 0) / 2)),  # 速度分桶
        ]
        return '|'.join(key_parts)
        
    def get(self, perception: dict) -> dict | None:
        """获取缓存结果。"""
        key = self._make_key(perception)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self.cache[key]
        return None
        
    def set(self, perception: dict, result: dict) -> None:
        """设置缓存结果。"""
        if len(self.cache) >= self.max_size:
            # 移除最旧的条目
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
            
        key = self._make_key(perception)
        self.cache[key] = (result, time.time())
        
    def clear(self) -> None:
        """清除过期缓存。"""
        now = time.time()
        expired_keys = [k for k, (_, ts) in self.cache.items() if now - ts > self.ttl]
        for k in expired_keys:
            del self.cache[k]
