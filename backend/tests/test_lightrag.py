"""
LightRAG 功能验证测试脚本

功能:
1. 测试文档插入功能
2. 验证知识图谱文件生成
3. 测试 4 种查询模式 (naive, local, global, hybrid)
4. 测试流式查询功能
5. 输出详细的性能指标

运行方式:
    "D:\\anaconda\\python.exe" "c:\\Users\\wxb55\\Desktop\\urban_climate_expert\\backend\\tests\\test_lightrag.py"

注意事项:
- 运行前确保 .env 文件配置正确
- 确保 backend/data/test.txt 文件存在
- 首次运行需要初始化向量数据库,可能需要 1-3 分钟
- 如使用 Ollama,需确保服务已启动
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.rag_service import get_rag_service


def print_section(title: str) -> None:
    """打印章节标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def check_prerequisites() -> tuple[bool, Path]:
    """检查前置条件"""
    print_section("前置检查")

    # 检查配置
    print(f"[配置信息]")
    print(f"  LLM 类型: {settings.llm_type}")
    print(f"  工作区路径: {settings.lightrag_workspace_path}")

    # 检查测试文本文件
    test_text_path = settings.lightrag_workspace_path / "test.txt"
    print(f"\n[文件检查]")
    print(f"  测试文本路径: {test_text_path}")

    if not test_text_path.exists():
        print(f"  [ERROR] 测试文本不存在")
        print(f"\n错误: 请先创建测试文本文件")
        print(f"路径: {test_text_path}")
        print(f"内容: 300-500 字的城市气候相关文本")
        return False, test_text_path

    file_size = test_text_path.stat().st_size
    print(f"  [OK] 测试文本存在 ({file_size} 字节)")

    # 检查工作区目录
    workspace = settings.lightrag_workspace_path
    if not workspace.exists():
        print(f"  [WARN] 工作区目录不存在,将自动创建")
        workspace.mkdir(parents=True, exist_ok=True)
    else:
        print(f"  [OK] 工作区目录存在")

    print(f"\n[OK] 前置检查通过")
    return True, test_text_path


async def test_document_insert(test_text_path: Path) -> bool:
    """测试文档插入功能"""
    print_section("测试 1: 文档插入")

    try:
        # 读取测试文本
        print(f"[读取文本] 从 {test_text_path.name}")
        test_text = test_text_path.read_text(encoding="utf-8")
        text_length = len(test_text)
        print(f"  文本长度: {text_length} 字符")
        print(f"  预览 (前100字符): {test_text[:100]}...")

        # 初始化 RAG 服务
        print(f"\n[初始化] 创建 LightRAG 服务...")
        print(f"  提示: 首次运行可能需要 1-3 分钟初始化向量数据库")
        rag_service = await get_rag_service()
        print(f"  [OK] RAG 服务创建成功")

        # 插入文档
        print(f"\n[插入文档] 开始处理...")
        start_time = time.time()

        await rag_service.insert_document(
            text=test_text,
            metadata={"source": "test.txt", "type": "verification", "phase": "phase1"}
        )

        elapsed = time.time() - start_time
        print(f"  [OK] 文档插入完成")
        print(f"  耗时: {elapsed:.2f} 秒")
        print(f"  处理速度: {text_length / elapsed:.0f} 字符/秒")

        return True

    except Exception as e:
        print(f"\n[ERROR] 文档插入失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


def check_generated_files() -> None:
    """检查生成的文件"""
    print_section("检查生成文件")

    workspace = settings.lightrag_workspace_path
    # LightRAG-HKU 使用的文件名
    expected_files = [
        "vdb_chunks.json",
        "vdb_entities.json",
        "vdb_relationships.json",
        "graph_chunk_entity_relation.graphml",
        "kv_store_full_docs.json",
        "kv_store_text_chunks.json",
        "kv_store_full_entities.json",
        "kv_store_full_relations.json",
    ]

    print(f"[工作区] {workspace}\n")

    total_size = 0
    for filename in expected_files:
        filepath = workspace / filename
        if filepath.exists():
            size_bytes = filepath.stat().st_size
            size_kb = size_bytes / 1024
            total_size += size_bytes
            print(f"  [OK] {filename:<40} {size_kb:>8.2f} KB")
        else:
            print(f"  [WARN] {filename:<40} 未生成")

    total_size_mb = total_size / (1024 * 1024)
    print(f"\n  总计: {total_size_mb:.2f} MB")


async def test_query_modes() -> bool:
    """测试不同查询模式"""
    print_section("测试 2: 查询模式")

    try:
        rag_service = await get_rag_service()
        test_question = "什么是城市热岛效应?"

        modes = ["naive", "local", "global", "hybrid"]
        results = []

        for mode in modes:
            print(f"\n[模式: {mode}]")
            print(f"  问题: {test_question}")

            start_time = time.time()
            result = await rag_service.query(test_question, mode=mode)
            elapsed = time.time() - start_time

            result_str = str(result)
            result_length = len(result_str)

            print(f"  耗时: {elapsed:.2f} 秒")
            print(f"  结果长度: {result_length} 字符")
            print(f"  结果预览 (前150字符):")
            print(f"    {result_str[:150]}...")

            results.append({
                "mode": mode,
                "elapsed": elapsed,
                "length": result_length
            })

        # 输出性能对比
        print(f"\n[性能对比]")
        print(f"  {'模式':<10} {'耗时(秒)':<12} {'结果长度':<12}")
        print(f"  {'-' * 34}")
        for r in results:
            print(f"  {r['mode']:<10} {r['elapsed']:<12.2f} {r['length']:<12}")

        print(f"\n[SUCCESS] 查询模式测试通过")
        return True

    except Exception as e:
        print(f"\n[ERROR] 查询模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_stream_query() -> bool:
    """测试流式查询"""
    print_section("测试 3: 流式查询")

    try:
        rag_service = await get_rag_service()
        test_question = "城市绿地如何缓解热岛效应?"

        print(f"[流式查询]")
        print(f"  问题: {test_question}")
        print(f"  模式: hybrid")
        print(f"\n[接收流式数据]\n")

        chunk_count = 0
        total_length = 0
        start_time = time.time()

        async for chunk in rag_service.stream_query(test_question, mode="hybrid"):
            chunk_count += 1
            chunk_length = len(chunk)
            total_length += chunk_length
            print(f"  Chunk {chunk_count}: {chunk_length} 字符")

            # 显示前两个 chunk 的内容
            if chunk_count <= 2:
                print(f"    内容: {chunk[:80]}...")

        elapsed = time.time() - start_time

        print(f"\n[流式统计]")
        print(f"  总 chunk 数: {chunk_count}")
        print(f"  总字符数: {total_length}")
        print(f"  总耗时: {elapsed:.2f} 秒")
        print(f"  平均速度: {total_length / elapsed:.0f} 字符/秒")

        print(f"\n[SUCCESS] 流式查询测试通过")
        return True

    except Exception as e:
        print(f"\n[ERROR] 流式查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multiple_queries() -> bool:
    """测试多个不同问题的查询"""
    print_section("测试 4: 多样化查询")

    questions = [
        "城市热岛效应的主要成因是什么?",
        "热岛效应对城市居民有哪些影响?",
        "如何通过城市规划缓解热岛效应?"
    ]

    try:
        rag_service = await get_rag_service()

        for i, question in enumerate(questions, 1):
            print(f"\n[问题 {i}] {question}")

            start_time = time.time()
            result = await rag_service.query(question, mode="hybrid")
            elapsed = time.time() - start_time

            result_str = str(result)[:200]
            print(f"  耗时: {elapsed:.2f} 秒")
            print(f"  回答: {result_str}...")

        print(f"\n[SUCCESS] 多样化查询测试通过")
        return True

    except Exception as e:
        print(f"\n[ERROR] 多样化查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main() -> None:
    """主测试流程"""
    print_section("UrbanClimate-Expert LightRAG 测试")

    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python 版本: {sys.version}")
    print(f"工作目录: {Path.cwd()}")

    # 前置检查
    check_passed, test_text_path = check_prerequisites()
    if not check_passed:
        return

    # 测试 1: 文档插入
    result1 = await test_document_insert(test_text_path)
    if not result1:
        print("\n[WARN] 文档插入失败,跳过后续测试")
        return

    # 检查生成的文件
    check_generated_files()

    # 测试 2: 查询模式
    result2 = await test_query_modes()

    # 测试 3: 流式查询
    result3 = await test_stream_query()

    # 测试 4: 多样化查询
    result4 = await test_multiple_queries()

    # 输出测试总结
    print_section("测试总结")

    results = [
        ("文档插入", result1),
        ("查询模式", result2),
        ("流式查询", result3),
        ("多样化查询", result4)
    ]

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[SUCCESS] 通过" if result else "[ERROR] 失败"
        print(f"  {status}  {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过! LightRAG 工作正常。")
        print("\n[后续步骤]")
        print("  1. 查看生成的知识图谱文件")
        print(f"     路径: {settings.lightrag_workspace}")
        print("  2. 可使用 Gephi 等工具可视化 graph.graphml")
        print("  3. 进入 Phase 2 开发 (PDF 解析和数据库集成)")
    else:
        print("\n[WARN] 部分测试失败,请检查:")
        print("  - LLM 服务是否正常运行")
        print("  - 网络连接是否正常")
        print("  - 配置文件是否正确")


if __name__ == "__main__":
    asyncio.run(main())
