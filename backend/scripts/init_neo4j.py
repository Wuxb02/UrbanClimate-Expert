"""
Neo4j 初始化脚本

功能:
- 从现有 GraphML 文件全量导入 Neo4j
- 验证迁移完整性
- 提供清空和重新导入选项

使用方式:
    "D:\\anaconda\\python.exe" "c:\\Users\\wxb55\\Desktop\\urban_climate_expert\\backend\\scripts\\init_neo4j.py"
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logger import logger
from app.services.neo4j_service import get_neo4j_service


async def main():
    """从 GraphML 初始化 Neo4j"""
    logger.info("=" * 60)
    logger.info("Neo4j 初始化脚本启动")
    logger.info("=" * 60)

    # 1. 检查 GraphML 文件是否存在
    graphml_path = settings.lightrag_workspace_path / "graph_chunk_entity_relation.graphml"
    if not graphml_path.exists():
        logger.error(f"GraphML 文件不存在 | 路径: {graphml_path}")
        logger.error("请先运行应用并上传文档，生成 GraphML 文件")
        return

    logger.info(f"找到 GraphML 文件 | 路径: {graphml_path}")
    logger.info(f"文件大小: {graphml_path.stat().st_size / 1024:.2f} KB")

    # 2. 获取 Neo4j 服务实例
    try:
        logger.info("连接 Neo4j 数据库...")
        neo4j_service = get_neo4j_service()
        logger.info("Neo4j 连接成功")
    except Exception as e:
        logger.error(f"Neo4j 连接失败 | 错误: {e}")
        logger.error("请确保 Neo4j 已启动，并检查 .env 中的配置")
        return

    # 3. 询问是否清空现有数据
    print("\n" + "=" * 60)
    print("注意: 此操作将清空 Neo4j 中的现有数据!")
    print("=" * 60)
    user_input = input("是否清空现有 Neo4j 数据? (yes/no): ").strip().lower()

    if user_input in ["yes", "y"]:
        logger.info("开始清空 Neo4j 数据库...")
        count = await asyncio.to_thread(neo4j_service.clear_all)
        logger.info(f"已删除 {count} 个节点")
    else:
        logger.info("跳过清空步骤，将执行增量同步")

    # 4. 全量同步
    logger.info("\n开始从 GraphML 同步数据到 Neo4j...")
    print("=" * 60)

    try:
        stats = await asyncio.to_thread(neo4j_service.sync_from_graphml, None)

        logger.info("\n" + "=" * 60)
        logger.info("Neo4j 初始化完成!")
        logger.info("=" * 60)
        logger.info(f"✓ 节点同步数量: {stats['nodes_synced']}")
        logger.info(f"✓ 边同步数量: {stats['edges_synced']}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\nNeo4j 同步失败 | 错误: {e}")
        return

    # 5. 验证数据
    logger.info("\n正在验证 Neo4j 数据...")
    try:
        with neo4j_service.driver.session(database=settings.neo4j_database) as session:
            # 查询节点总数
            result = session.run("MATCH (n:Entity) RETURN count(n) AS count")
            node_count = result.single()["count"]

            # 查询边总数
            result = session.run("MATCH ()-[r:RELATED_TO]->() RETURN count(r) AS count")
            edge_count = result.single()["count"]

            logger.info(f"Neo4j 节点数: {node_count}")
            logger.info(f"Neo4j 边数: {edge_count}")

            # 对比 GraphML 和 Neo4j 的数据
            if node_count == stats['nodes_synced'] and edge_count == stats['edges_synced']:
                logger.info("✓ 数据验证通过，迁移完整")
            else:
                logger.warning(
                    f"! 数据不一致 | "
                    f"同步节点: {stats['nodes_synced']}, 实际节点: {node_count} | "
                    f"同步边: {stats['edges_synced']}, 实际边: {edge_count}"
                )

    except Exception as e:
        logger.error(f"数据验证失败 | 错误: {e}")

    # 6. 关闭连接
    logger.info("\n关闭 Neo4j 连接...")
    neo4j_service.close()

    logger.info("\n" + "=" * 60)
    logger.info("初始化脚本执行完毕")
    logger.info("=" * 60)
    print("\n提示:")
    print("- 可以访问 http://localhost:7474 查看 Neo4j Browser")
    print("- 使用 Cypher 查询: MATCH (n:Entity) RETURN n LIMIT 50")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
