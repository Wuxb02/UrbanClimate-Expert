"""
测试 LightRAG + Neo4j 原生集成

验证:
1. 环境变量配置是否正确
2. Neo4j 连接是否正常
3. LightRAG 能否正确初始化 Neo4j 存储

使用方式:
    "D:\\anaconda\\python.exe" "c:\\Users\\wxb55\\Desktop\\urban_climate_expert\\backend\\scripts\\test_neo4j_native.py"
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logger import logger


def check_neo4j_env_vars():
    """检查 Neo4j 环境变量配置"""
    logger.info("=" * 60)
    logger.info("检查 Neo4j 环境变量配置")
    logger.info("=" * 60)

    # 优先从 settings 对象读取（会自动加载 .env 文件）
    # 然后设置为环境变量供 LightRAG 使用
    try:
        neo4j_uri = settings.neo4j_uri
        neo4j_username = settings.neo4j_user  # settings 使用 neo4j_user
        neo4j_password = settings.neo4j_password

        # 设置环境变量（LightRAG 需要这些环境变量）
        os.environ["NEO4J_URI"] = neo4j_uri
        os.environ["NEO4J_USERNAME"] = neo4j_username  # LightRAG 使用 NEO4J_USERNAME
        os.environ["NEO4J_PASSWORD"] = neo4j_password

        required_vars = {
            "NEO4J_URI": neo4j_uri,
            "NEO4J_USERNAME": neo4j_username,
            "NEO4J_PASSWORD": neo4j_password,
        }

        logger.info("已从 .env 文件加载配置:")
        all_set = True
        for var_name, var_value in required_vars.items():
            if var_value:
                # 密码部分隐藏显示
                display_value = (
                    var_value
                    if var_name != "NEO4J_PASSWORD"
                    else f"{var_value[:3]}***{var_value[-3:]}"
                )
                logger.info(f"✓ {var_name}: {display_value}")
            else:
                logger.error(f"✗ {var_name}: 未设置")
                all_set = False

        optional_vars = {
            "NEO4J_DATABASE": settings.neo4j_database,
            "NEO4J_WORKSPACE": os.getenv("NEO4J_WORKSPACE", "default"),
        }

        logger.info("\n可选配置:")
        for var_name, var_value in optional_vars.items():
            logger.info(f"  {var_name}: {var_value}")

        return all_set

    except AttributeError as e:
        logger.error(f"✗ 无法从 settings 读取配置: {e}")
        logger.error("请检查 backend/.env 文件是否存在并包含以下配置:")
        logger.error("  NEO4J_URI=neo4j://localhost:7687")
        logger.error("  NEO4J_USER=neo4j")
        logger.error("  NEO4J_PASSWORD=your_password")
        return False


async def test_neo4j_connection():
    """测试 Neo4j 连接"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 Neo4j 连接")
    logger.info("=" * 60)

    try:
        from neo4j import GraphDatabase

        # 从环境变量读取（已在 check_neo4j_env_vars 中设置）
        uri = os.getenv("NEO4J_URI")
        username = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")

        if not all([uri, username, password]):
            logger.error("Neo4j 环境变量未完整配置")
            return False

        logger.info(f"连接到 Neo4j: {uri}")
        driver = GraphDatabase.driver(uri, auth=(username, password))

        # 验证连接
        driver.verify_connectivity()
        logger.info("✓ Neo4j 连接验证成功")

        # 测试查询
        with driver.session() as session:
            result = session.run("RETURN 1 AS number")
            record = result.single()
            logger.info(f"✓ 测试查询成功: {record['number']}")

            # 查询现有节点数量
            result = session.run("MATCH (n) RETURN count(n) AS count")
            count = result.single()["count"]
            logger.info(f"  当前 Neo4j 节点数: {count}")

        driver.close()
        return True

    except Exception as e:
        logger.error(f"✗ Neo4j 连接失败 | 错误: {e}")
        logger.error("请检查:")
        logger.error("  1. Neo4j 是否已启动 (http://localhost:7474)")
        logger.error("  2. URI 协议是否为 neo4j:// (不是 bolt://)")
        logger.error("  3. 用户名密码是否正确")
        return False


async def test_lightrag_initialization():
    """测试 LightRAG 初始化（不实际插入数据）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 LightRAG 初始化")
    logger.info("=" * 60)

    try:
        from app.services.rag_service import LightRAGService

        logger.info("创建 LightRAG 服务实例...")
        rag_service = LightRAGService()

        logger.info("初始化存储（包括 Neo4j）...")
        await rag_service.initialize()

        logger.info("✓ LightRAG 初始化成功")
        logger.info(f"  工作目录: {rag_service.rag.working_dir}")
        logger.info(f"  图存储: Neo4JStorage")

        return True

    except Exception as e:
        logger.error(f"✗ LightRAG 初始化失败 | 错误: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


async def main():
    """主测试流程"""
    logger.info("LightRAG + Neo4j 原生集成测试")
    logger.info("=" * 60)

    # 1. 检查环境变量
    env_ok = check_neo4j_env_vars()
    if not env_ok:
        logger.error("\n环境变量配置不完整，请检查 .env 文件")
        logger.error("必需环境变量:")
        logger.error("  - NEO4J_URI=neo4j://localhost:7687")
        logger.error("  - NEO4J_USERNAME=neo4j")
        logger.error("  - NEO4J_PASSWORD=your_password")
        return

    # 2. 测试 Neo4j 连接
    neo4j_ok = await test_neo4j_connection()
    if not neo4j_ok:
        logger.error("\nNeo4j 连接失败，请检查:")
        logger.error("  1. Neo4j 是否已启动")
        logger.error("  2. 连接信息是否正确")
        logger.error("  3. 防火墙是否阻止连接")
        return

    # 3. 测试 LightRAG 初始化
    lightrag_ok = await test_lightrag_initialization()
    if not lightrag_ok:
        logger.error("\nLightRAG 初始化失败，请检查错误日志")
        return

    # 4. 总结
    logger.info("\n" + "=" * 60)
    logger.info("测试完成!")
    logger.info("=" * 60)
    logger.info("✓ 环境变量配置正确")
    logger.info("✓ Neo4j 连接正常")
    logger.info("✓ LightRAG 初始化成功")
    logger.info("\n系统已准备就绪，可以开始上传文档")
    logger.info("上传的文档将直接写入 Neo4j 图数据库")


if __name__ == "__main__":
    asyncio.run(main())
