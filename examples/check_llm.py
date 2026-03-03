"""
LLM 连接诊断工具。

检查 LLM 配置和连接状态。
"""

import sys
import os
sys.path.insert(0, '..')

from city.llm.llm_client import LLMClient, LLMConfig, LLMProvider


def check_env_variables():
    """检查环境变量。"""
    print("=" * 70)
    print("环境变量检查")
    print("=" * 70)
    
    # 检查 SiliconFlow
    print("\n【SiliconFlow 配置】")
    sf_key = os.getenv("SILICONFLOW_API_KEY")
    sf_url = os.getenv("SILICONFLOW_BASE_URL")
    sf_model = os.getenv("SILICONFLOW_MODEL")
    
    if sf_key:
        print(f"[OK] SILICONFLOW_API_KEY: {sf_key[:10]}...{sf_key[-4:]}")
    else:
        print("[MISSING] SILICONFLOW_API_KEY: 未设置")
    
    if sf_url:
        print(f"[OK] SILICONFLOW_BASE_URL: {sf_url}")
    else:
        print("[MISSING] SILICONFLOW_BASE_URL: 未设置 (将使用默认值)")
    
    if sf_model:
        print(f"[OK] SILICONFLOW_MODEL: {sf_model}")
    else:
        print("[MISSING] SILICONFLOW_MODEL: 未设置 (将使用默认值 Qwen/Qwen3-14B)")
    
    # 检查 OpenAI
    print("\n【OpenAI 配置】")
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print(f"[OK] OPENAI_API_KEY: {openai_key[:10]}...{openai_key[-4:]}")
    else:
        print("[MISSING] OPENAI_API_KEY: 未设置")
    
    return sf_key or openai_key


def test_siliconflow():
    """测试 SiliconFlow 连接。"""
    print("\n" + "=" * 70)
    print("SiliconFlow 连接测试")
    print("=" * 70)
    
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        print("\n[FAIL] 跳过: SILICONFLOW_API_KEY 未设置")
        return False
    
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-14B")
    
    print(f"\n配置:")
    print(f"  Provider: SILICONFLOW")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        config = LLMConfig(
            provider=LLMProvider.SILICONFLOW,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.7,
            max_tokens=100
        )
        
        client = LLMClient(config)
        
        print(f"\n客户端状态:")
        print(f"  _client 对象: {'已创建' if client._client else '未创建'}")
        print(f"  is_available(): {client.is_available()}")
        
        if not client.is_available():
            print("\n[FAIL] 客户端不可用，请检查:")
            print("  1. API Key 是否正确")
            print("  2. openai 包是否已安装 (pip install openai)")
            return False
        
        # 测试简单请求
        print("\n发送测试请求...")
        response = client.chat(
            "你好，请回复'连接成功'",
            system_prompt="你是一个测试助手",
            max_tokens=50
        )
        
        print(f"\n[OK] 响应: {response[:100]}...")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 请求失败: {e}")
        print(f"\n详细错误:")
        import traceback
        traceback.print_exc()
        return False


def test_openai():
    """测试 OpenAI 连接。"""
    print("\n" + "=" * 70)
    print("OpenAI 连接测试")
    print("=" * 70)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n[FAIL] 跳过: OPENAI_API_KEY 未设置")
        return False
    
    print(f"\n配置:")
    print(f"  Provider: OPENAI")
    print(f"  API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key=api_key,
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=100
        )
        
        client = LLMClient(config)
        
        print(f"\n客户端状态:")
        print(f"  _client 对象: {'已创建' if client._client else '未创建'}")
        print(f"  is_available(): {client.is_available()}")
        
        if not client.is_available():
            print("\n[FAIL] 客户端不可用")
            return False
        
        print("\n发送测试请求...")
        response = client.chat(
            "Hello",
            system_prompt="You are a helpful assistant",
            max_tokens=50
        )
        
        print(f"\n[OK] 响应: {response[:100]}...")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 请求失败: {e}")
        return False


def test_mock():
    """测试 Mock LLM。"""
    print("\n" + "=" * 70)
    print("Mock LLM 测试")
    print("=" * 70)
    
    from city.llm.llm_client import MockLLMClient
    
    mock_client = MockLLMClient({
        "测试": '{"action": "test", "result": "success"}'
    })
    
    print(f"\nMockClient 状态:")
    print(f"  is_available(): {mock_client.is_available()}")
    
    response = mock_client.chat("这是一个测试")
    print(f"\n[OK] 响应: {response}")
    return True


def diagnose():
    """运行完整诊断。"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "LLM 连接诊断工具" + " " * 30 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # 检查环境变量
    has_config = check_env_variables()
    
    if not has_config:
        print("\n" + "!" * 70)
        print("警告: 未检测到任何 LLM API 配置!")
        print("!" * 70)
        print("\n请设置以下环境变量之一:")
        print("\n  【SiliconFlow】(推荐，国内可用)")
        print("    $env:SILICONFLOW_API_KEY='your-key'")
        print("    $env:SILICONFLOW_BASE_URL='https://api.siliconflow.cn/v1'")
        print("    $env:SILICONFLOW_MODEL='Qwen/Qwen3-14B'")
        print("\n  【OpenAI】")
        print("    $env:OPENAI_API_KEY='your-key'")
        print("\n" + "!" * 70)
    
    # 测试连接
    results = []
    
    if os.getenv("SILICONFLOW_API_KEY"):
        results.append(("SiliconFlow", test_siliconflow()))
    
    if os.getenv("OPENAI_API_KEY"):
        results.append(("OpenAI", test_openai()))
    
    results.append(("Mock", test_mock()))
    
    # 总结
    print("\n" + "=" * 70)
    print("诊断总结")
    print("=" * 70)
    
    for name, success in results:
        status = "[OK] 可用" if success else "[FAIL] 失败"
        print(f"  {name}: {status}")
    
    print("\n" + "=" * 70)
    
    # 提供建议
    if not any(success for _, success in results[:-1]):  # 除了Mock都失败
        print("\n故障排除建议:")
        print("  1. 确认环境变量已正确设置")
        print("     检查: Get-ChildItem Env: | Where-Object {$_.Name -like '*API_KEY*'}")
        print("  2. 确认已安装 openai 包")
        print("     运行: pip install openai")
        print("  3. 确认 API Key 有效且未过期")
        print("  4. 检查网络连接是否能访问 API 服务器")
        print("  5. 查看详细错误信息（上面的堆栈跟踪）")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    diagnose()
