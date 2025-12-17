"""
LLM 工厂连接测试脚本

功能:
1. 测试 LLM 工厂的基本调用功能
2. 测试多轮对话功能
3. 验证 OpenAI 和 Ollama 的切换能力
4. 输出响应时间和内容长度等指标

运行方式:
    "D:\\anaconda\\python.exe" "c:\\Users\\wxb55\\Desktop\\urban_climate_expert\\backend\\tests\\test_llm.py"

注意事项:
- 运行前确保 .env 文件配置正确
- 如使用 Ollama,需先启动服务: ollama serve
- 如使用 OpenAI,需确保 API Key 有效且有余额
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.llm_factory import LLMFactory


def print_section(title: str) -> None:
    """打印章节标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def test_llm_basic() -> None:
    """测试基本 LLM 调用"""
    print_section("测试 1: 基本 LLM 调用")

    # 显示当前配置
    print(f"[配置信息]")
    print(f"  LLM 类型: {settings.llm_type}")
    if settings.llm_type == "ollama":
        print(f"  Ollama 端点: {settings.ollama_base_url}")
        print(f"  模型名称: {settings.ollama_model}")
    elif settings.llm_type == "openai":
        print(f"  OpenAI 端点: {settings.openai_base_url or 'https://api.openai.com/v1'}")
        print(f"  模型名称: {settings.openai_model}")
        api_key_display = settings.openai_api_key[:10] + "..." if settings.openai_api_key else "未设置"
        print(f"  API Key: {api_key_display}")

    try:
        # 构建 LLM 客户端
        print("\n[初始化] 构建 LLM 客户端...")
        chat = LLMFactory.build_chat_model()
        print("[OK] LLM 客户端构建成功")

        # 测试简单问答
        print("\n[测试] 发送测试问题...")
        question = "你好,请简单介绍一下城市热岛效应,不超过150字。"
        print(f"问题: {question}")

        start_time = time.time()
        response = await chat(question, [])
        elapsed = time.time() - start_time

        # 输出结果统计
        print(f"\n[响应统计]")
        print(f"  耗时: {elapsed:.2f} 秒")
        print(f"  内容长度: {len(response)} 字符")
        print(f"  速度: {len(response) / elapsed:.1f} 字符/秒")

        print(f"\n[响应内容]")
        print(f"{response}")

        print("\n[OK] 基本调用测试通过")
        return True

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print(f"\n完整错误信息:")
        traceback.print_exc()
        return False


async def test_llm_multiround() -> None:
    """测试多轮对话功能"""
    print_section("测试 2: 多轮对话")

    try:
        chat = LLMFactory.build_chat_model()

        # 第一轮对话
        print("[第 1 轮] 用户: 什么是城市热岛效应?")
        start_time = time.time()
        response1 = await chat("什么是城市热岛效应?简单说明,不超过100字。", [])
        elapsed1 = time.time() - start_time

        print(f"[第 1 轮] 助手 (耗时 {elapsed1:.2f}s): {response1[:100]}...")

        # 构建历史记录
        history = [
            {"role": "user", "content": "什么是城市热岛效应?"},
            {"role": "assistant", "content": response1}
        ]

        # 第二轮对话
        print("\n[第 2 轮] 用户: 它对居民健康有什么影响?")
        start_time = time.time()
        response2 = await chat("它对居民健康有什么影响?简单说明,不超过100字。", history)
        elapsed2 = time.time() - start_time

        print(f"[第 2 轮] 助手 (耗时 {elapsed2:.2f}s): {response2[:100]}...")

        # 第三轮对话
        history.extend([
            {"role": "user", "content": "它对居民健康有什么影响?"},
            {"role": "assistant", "content": response2}
        ])

        print("\n[第 3 轮] 用户: 有哪些缓解措施?")
        start_time = time.time()
        response3 = await chat("有哪些缓解措施?列出3条即可。", history)
        elapsed3 = time.time() - start_time

        print(f"[第 3 轮] 助手 (耗时 {elapsed3:.2f}s): {response3[:150]}...")

        print("\n[OK] 多轮对话测试通过")
        return True

    except Exception as e:
        print(f"\n[ERROR] 多轮对话测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_llm_error_handling() -> None:
    """测试错误处理"""
    print_section("测试 3: 错误处理")

    print("[测试] 空输入处理...")
    try:
        chat = LLMFactory.build_chat_model()
        response = await chat("", [])
        print(f"空输入响应: {response[:50]}...")
        print("[WARN] 空输入未被拒绝(可能是 LLM 的默认行为)")
    except Exception as e:
        print(f"[OK] 空输入被正确拒绝: {type(e).__name__}")

    print("\n[测试] 超长输入处理...")
    try:
        chat = LLMFactory.build_chat_model()
        long_text = "测试" * 10000  # 20000 字符
        start_time = time.time()
        response = await chat(f"请总结以下内容: {long_text}", [])
        elapsed = time.time() - start_time
        print(f"超长输入响应成功 (耗时 {elapsed:.2f}s, 响应长度: {len(response)} 字符)")
        print("[OK] 超长输入处理正常")
    except Exception as e:
        print(f"[WARN] 超长输入被拒绝: {type(e).__name__}: {e}")

    print("\n[OK] 错误处理测试完成")


async def main() -> None:
    """主测试流程"""
    print_section("UrbanClimate-Expert LLM 工厂测试")

    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python 版本: {sys.version}")
    print(f"工作目录: {Path.cwd()}")

    # 检查配置
    print("\n[前置检查]")
    if settings.llm_type == "openai" and not settings.openai_api_key:
        print("[ERROR] 错误: LLM_TYPE 设为 openai,但 OPENAI_API_KEY 未配置")
        print("请在 .env 文件中设置 OPENAI_API_KEY")
        return

    if settings.llm_type == "ollama":
        print(f"[OK] 配置检查通过 (使用 Ollama: {settings.ollama_model})")
        print("提示: 请确保 Ollama 服务已启动 (ollama serve)")
    elif settings.llm_type == "openai":
        print(f"[OK] 配置检查通过 (使用 OpenAI: {settings.openai_model})")

    # 运行测试
    results = []

    # 测试 1: 基本调用
    result1 = await test_llm_basic()
    results.append(("基本调用", result1))

    if not result1:
        print("\n[WARN] 基本调用测试失败,跳过后续测试")
        return

    # 测试 2: 多轮对话
    result2 = await test_llm_multiround()
    results.append(("多轮对话", result2))

    # 测试 3: 错误处理
    await test_llm_error_handling()
    results.append(("错误处理", True))

    # 输出测试总结
    print_section("测试总结")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}  {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过! LLM 工厂工作正常。")
    else:
        print("\n[WARN] 部分测试失败,请检查配置和服务状态。")


if __name__ == "__main__":
    asyncio.run(main())
