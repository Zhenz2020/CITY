#!/usr/bin/env python3
"""测试所有导入是否正常。"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 测试所有导入
from city.llm.llm_client import LLMClient, MockLLMClient
from city.llm.agent_llm_interface import AgentLLMInterface
from city.agents.vehicle import Vehicle, VehicleType

# 测试 MockLLMClient
mock = MockLLMClient({'test': '{"action": "proceed"}'})
result = mock.chat('test')
print('MockLLMClient.chat result:', result)

# 测试 LLMClient
client = LLMClient()
print('LLMClient available:', client.is_available())

# 测试 structured_chat
result = client.structured_chat('test message')
print('structured_chat result:', result)

print('\nAll tests passed!')
