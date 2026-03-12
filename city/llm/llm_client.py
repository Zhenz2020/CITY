"""
大语言模型客户端。

封装各种LLM API的调用，支持OpenAI、Azure等。
"""

from __future__ import annotations

import os
import json
from typing import Any
from dataclasses import dataclass
from enum import Enum, auto


class LLMProvider(Enum):
    """LLM服务提供商。"""
    OPENAI = auto()
    AZURE = auto()
    ANTHROPIC = auto()
    SILICONFLOW = auto()  # SiliconFlow (国内API平台)
    LOCAL = auto()  # 本地模型


@dataclass
class LLMConfig:
    """LLM配置。"""
    provider: LLMProvider = LLMProvider.OPENAI
    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 500
    timeout: float = 30.0

    def __post_init__(self):
        """从环境变量读取API密钥（如果未提供）。"""
        if self.api_key is None:
            if self.provider == LLMProvider.OPENAI:
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == LLMProvider.AZURE:
                self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
            elif self.provider == LLMProvider.ANTHROPIC:
                self.api_key = os.getenv("ANTHROPIC_API_KEY")
            elif self.provider == LLMProvider.SILICONFLOW:
                self.api_key = os.getenv("SILICONFLOW_API_KEY")
        
        # 从环境变量读取base_url（如果未提供）
        if self.base_url is None:
            if self.provider == LLMProvider.SILICONFLOW:
                self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")


class LLMClient:
    """
    大语言模型客户端。

    封装LLM API调用，提供统一的接口。

    Attributes:
        config: LLM配置
        conversation_history: 对话历史（用于上下文）
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self.conversation_history: list[dict[str, str]] = []
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """初始化具体的LLM客户端。"""
        if self.config.provider in [LLMProvider.OPENAI, LLMProvider.SILICONFLOW]:
            # SiliconFlow 兼容 OpenAI API 格式
            self._init_openai()
        elif self.config.provider == LLMProvider.LOCAL:
            self._init_local()

    def _init_openai(self) -> None:
        """初始化OpenAI客户端。"""
        try:
            import openai
            self._client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url
            )
        except ImportError:
            print("警告: OpenAI SDK未安装，LLM功能不可用")
            print("请运行: pip install openai")
            self._client = None
        except Exception as e:
            print(f"OpenAI客户端初始化失败: {e}")
            self._client = None

    def _init_local(self) -> None:
        """初始化本地模型客户端。"""
        self._client = None

    def is_available(self) -> bool:
        """检查LLM服务是否可用。"""
        return self._client is not None and self.config.api_key is not None

    def chat(
        self,
        message: str,
        system_prompt: str | None = None,
        use_history: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None
    ) -> str:
        """
        发送对话消息并获取回复。

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            use_history: 是否使用对话历史
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            LLM的回复文本
        """
        if not self.is_available():
            return self._fallback_response(message)

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if use_history:
            messages.extend(self.conversation_history)

        messages.append({"role": "user", "content": message})

        try:
            if self.config.provider in [LLMProvider.OPENAI, LLMProvider.SILICONFLOW]:
                return self._call_openai(
                    messages,
                    temperature or self.config.temperature,
                    max_tokens or self.config.max_tokens
                )
            else:
                return self._fallback_response(message)
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return self._fallback_response(message)

    def _call_openai(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int
    ) -> str:
        """调用OpenAI API。"""
        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        content = response.choices[0].message.content

        # 更新历史
        self.conversation_history.append(messages[-1])
        self.conversation_history.append({"role": "assistant", "content": content})

        # 限制历史长度
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        return content

    def _fallback_response(self, message: str) -> str:
        """当LLM不可用时返回的默认响应。"""
        return json.dumps({
            "action": "maintain",
            "reason": "LLM服务不可用，使用默认策略"
        })

    def clear_history(self) -> None:
        """清空对话历史。"""
        self.conversation_history.clear()

    def structured_chat(
        self,
        message: str,
        system_prompt: str | None = None
    ) -> dict[str, Any] | str:
        """
        获取结构化的JSON响应。

        Args:
            message: 用户消息
            system_prompt: 系统提示词

        Returns:
            解析后的JSON字典或原始字符串
        """
        json_prompt = f"{message}\n\n请以JSON格式回复。"
        response = self.chat(json_prompt, system_prompt)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return response


class MockLLMClient(LLMClient):
    """
    模拟LLM客户端（用于测试）。

    不调用真实API，返回预设响应。
    """

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self.conversation_history = []
        self.config = LLMConfig()
        self._client = None

    def is_available(self) -> bool:
        return True

    def chat(
        self,
        message: str,
        system_prompt: str | None = None,
        use_history: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None
    ) -> str:
        """返回模拟响应。"""
        for key, response in self.responses.items():
            if key in message.lower():
                return response

        return json.dumps({
            "action": "proceed",
            "reason": "模拟响应：继续行驶"
        })


def load_llm_from_config(config_path: str) -> LLMClient:
    """
    从JSON配置文件加载LLM客户端。

    Args:
        config_path: 配置文件路径

    Returns:
        配置好的LLMClient实例

    Example:
        client = load_llm_from_config("config/siliconflow_config.json")
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)

    # 获取provider
    provider_name = config_data.get('provider', 'OPENAI').upper()
    provider = LLMProvider[provider_name]

    # 获取API密钥（支持单key字符串或多key数组）
    api_key = config_data.get('api_key')
    
    # 如果是数组，取第一个作为默认client，其余的会由LLMClientPool处理
    api_keys = []
    if isinstance(api_key, list):
        api_keys = api_key
        api_key = api_keys[0] if api_keys else None
    elif api_key:
        api_keys = [api_key]
    
    # 如果配置文件中没有，尝试环境变量
    if not api_keys:
        if provider == LLMProvider.SILICONFLOW:
            env_key = os.getenv('SILICONFLOW_API_KEY')
            if env_key:
                api_keys = [env_key]
                api_key = env_key
        elif provider == LLMProvider.OPENAI:
            env_key = os.getenv('OPENAI_API_KEY')
            if env_key:
                api_keys = [env_key]
                api_key = env_key

    # 获取base_url（优先使用配置文件，否则尝试环境变量，最后使用默认值）
    base_url = config_data.get('base_url')
    if base_url is None:
        if provider == LLMProvider.SILICONFLOW:
            base_url = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')

    # 获取模型名称
    model = config_data.get('model', 'gpt-3.5-turbo')
    if provider == LLMProvider.SILICONFLOW and model == 'gpt-3.5-turbo':
        model = 'Qwen/Qwen3-14B'  # SiliconFlow默认模型

    # 初始化LLMClientPool（只要有API Key就初始化）
    if len(api_keys) >= 1:
        try:
            from city.llm.llm_pool import get_llm_pool
            pool = get_llm_pool()
            pool.add_api_keys(api_keys, base_url=base_url, model=model, provider=provider)
            print(f"[LLM] 已加载 {len(api_keys)} 个API Key到客户端池")
        except Exception as e:
            print(f"[LLM] 初始化客户端池失败: {e}")

    config = LLMConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=config_data.get('temperature', 0.7),
        max_tokens=config_data.get('max_tokens', 500),
        timeout=config_data.get('timeout', 30.0)
    )

    return LLMClient(config)


def load_siliconflow_config(config_dir: str = "config") -> LLMClient:
    """
    快速加载SiliconFlow配置。

    自动查找 config/siliconflow_config.json 文件。

    Args:
        config_dir: 配置文件目录

    Returns:
        配置好的LLMClient实例
    """
    # 可能的配置文件路径
    possible_paths = [
        os.path.join(config_dir, "siliconflow_config.json"),
        os.path.join(config_dir, "llm_config.json"),
        "siliconflow_config.json",
        "config/siliconflow_config.json",
        "config/llm_config.json",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"加载配置文件: {path}")
            return load_llm_from_config(path)

    raise FileNotFoundError(
        f"找不到SiliconFlow配置文件。请确保以下文件之一存在:\n" +
        "\n".join(f"  - {p}" for p in possible_paths)
    )
