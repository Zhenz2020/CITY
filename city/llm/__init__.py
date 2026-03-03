"""
大语言模型接口模块。

为智能体提供LLM调用能力，支持智能决策。
"""

from city.llm.llm_client import (
    LLMClient, 
    LLMConfig, 
    LLMProvider, 
    MockLLMClient,
    load_llm_from_config,
    load_siliconflow_config
)
from city.llm.agent_llm_interface import AgentLLMInterface, get_global_llm_client, set_global_llm_client

__all__ = [
    'LLMClient', 
    'LLMConfig', 
    'LLMProvider',
    'MockLLMClient',
    'load_llm_from_config',
    'load_siliconflow_config',
    'AgentLLMInterface',
    'get_global_llm_client',
    'set_global_llm_client'
]
