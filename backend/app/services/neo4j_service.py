"""
Neo4j 服务层

功能:
- 管理 Neo4j 驱动连接池
- 增量同步 GraphML 数据到 Neo4j
- 直接从 LightRAG JSON 文件同步到 Neo4j (推荐)
- 提供节点/关系的 UPSERT 操作
- 支持全量和增量同步模式
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import networkx as nx
from neo4j import GraphDatabase, Driver, Session

from app.core.config import settings
from app.core.logger import logger


class Neo4jService:
    """
    Neo4j 服务类

    职责:
    - 管理 Neo4j 驱动连接池
    - 增量同步 GraphML 数据到 Neo4j
    - 提供节点/关系的 UPSERT 操作
    """

    def __init__(self) -> None:
        """初始化 Neo4j 驱动"""
        logger.info(
            f"初始化 Neo4j 驱动 | "
            f"URI: {settings.neo4j_uri} | "
            f"用户: {settings.neo4j_user} | "
            f"数据库: {settings.neo4j_database}"
        )

        try:
            self.driver: Driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_lifetime=3600,  # 1小时连接回收
                max_connection_pool_size=50,
                connection_acquisition_timeout=30.0,
            )

            # 测试连接
            self.driver.verify_connectivity()
            logger.info("Neo4j 连接验证成功")

        except Exception as e:
            logger.error(f"Neo4j 连接失败 | 错误: {e}")
            raise RuntimeError(f"Neo4j 连接失败: {e}")

    def close(self) -> None:
        """关闭驱动连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j 驱动已关闭")

    def _get_graphml_path(self) -> Path:
        """获取 GraphML 文件路径"""
        return settings.lightrag_workspace_path / "graph_chunk_entity_relation.graphml"

    def _normalize_entity_type(self, entity_type: str) -> str:
        """
        规范化实体类型为 Neo4j 标签格式

        例如: method → Method, location → Location
        """
        if not entity_type or entity_type == "unknown":
            return "Unknown"
        return entity_type.capitalize()

    def _parse_sep_list(self, value: str) -> list[str]:
        """
        解析 <SEP> 分隔的字符串为列表

        Args:
            value: 形如 "a<SEP>b<SEP>c" 的字符串

        Returns:
            ["a", "b", "c"]
        """
        if not value:
            return []
        return [item.strip() for item in value.split("<SEP>") if item.strip()]

    def upsert_entity(
        self, session: Session, node_id: str, data: dict[str, Any]
    ) -> None:
        """
        UPSERT 实体节点 (存在则更新,不存在则创建)

        Args:
            session: Neo4j 会话
            node_id: 节点 ID
            data: 节点属性字典
        """
        # 解析描述 (多个描述用 \n\n 连接)
        description = data.get("description", "")
        if "<SEP>" in description:
            desc_list = self._parse_sep_list(description)
            description = "\n\n".join(desc_list)

        # 解析 source_ids
        source_ids = self._parse_sep_list(data.get("source_id", ""))

        # 规范化实体类型
        entity_type = data.get("entity_type", "unknown")
        label = self._normalize_entity_type(entity_type)

        # 构建 MERGE 查询
        query = f"""
        MERGE (n:Entity:{label} {{name: $name}})
        ON CREATE SET
            n.entity_id = $entity_id,
            n.entity_type = $entity_type,
            n.description = $description,
            n.source_ids = $source_ids,
            n.file_path = $file_path,
            n.created_at = $created_at
        ON MATCH SET
            n.description = $description,
            n.source_ids = $source_ids
        RETURN n.name AS name
        """

        params = {
            "name": node_id,
            "entity_id": data.get("entity_id", node_id),
            "entity_type": entity_type,
            "description": description,
            "source_ids": source_ids,
            "file_path": data.get("file_path", "unknown_source"),
            "created_at": int(data.get("created_at", time.time())),
        }

        try:
            session.run(query, params)
        except Exception as e:
            logger.error(
                f"节点 UPSERT 失败 | node_id: {node_id} | 错误: {e}"
            )
            raise

    def upsert_relationship(
        self,
        session: Session,
        source: str,
        target: str,
        data: dict[str, Any],
    ) -> None:
        """
        UPSERT 关系 (存在则更新,不存在则创建)

        Args:
            session: Neo4j 会话
            source: 源节点 ID
            target: 目标节点 ID
            data: 关系属性字典
        """
        # 解析 source_ids
        source_ids = self._parse_sep_list(data.get("source_id", ""))

        query = """
        MATCH (a:Entity {name: $source})
        MATCH (b:Entity {name: $target})
        MERGE (a)-[r:RELATED_TO]->(b)
        ON CREATE SET
            r.description = $description,
            r.weight = $weight,
            r.keywords = $keywords,
            r.source_ids = $source_ids,
            r.file_path = $file_path,
            r.created_at = $created_at
        ON MATCH SET
            r.description = $description,
            r.weight = $weight,
            r.source_ids = $source_ids
        RETURN r
        """

        params = {
            "source": source,
            "target": target,
            "description": data.get("description", "related_to"),
            "weight": float(data.get("weight", 1.0)),
            "keywords": data.get("keywords", ""),
            "source_ids": source_ids,
            "file_path": data.get("file_path", "unknown_source"),
            "created_at": int(data.get("created_at", time.time())),
        }

        try:
            session.run(query, params)
        except Exception as e:
            logger.error(
                f"关系 UPSERT 失败 | {source} -> {target} | 错误: {e}"
            )
            raise

    def sync_from_graphml(
        self, doc_id: int | None = None
    ) -> dict[str, int]:
        """
        从 GraphML 同步数据到 Neo4j (备用方法)

        注意: 推荐使用 sync_from_json() 方法，此方法仅在需要时使用

        Args:
            doc_id: 文档 ID (用于日志追踪,实际同步时处理所有变更)

        Returns:
            统计信息 {"nodes_synced": int, "edges_synced": int}
        """
        logger.warning(
            "使用 GraphML 同步方法（不推荐），建议使用 sync_from_json()"
        )

        graphml_path = self._get_graphml_path()
        if not graphml_path.exists():
            logger.warning(
                f"GraphML 文件不存在 | 路径: {graphml_path}"
            )
            return {"nodes_synced": 0, "edges_synced": 0}

        logger.info(
            f"开始同步 GraphML → Neo4j | "
            f"doc_id: {doc_id or 'full_sync'} | 文件: {graphml_path.name}"
        )
        start_time = time.perf_counter()

        try:
            # 1. 加载 GraphML
            graph = nx.read_graphml(str(graphml_path))
            node_count = graph.number_of_nodes()
            edge_count = graph.number_of_edges()

            logger.debug(
                f"GraphML 加载完成 | 节点数: {node_count} | 边数: {edge_count}"
            )

            # 2. 批量同步节点和关系
            with self.driver.session(database=settings.neo4j_database) as session:
                # 2.1 同步节点 (UPSERT)
                nodes_synced = 0
                for node_id, data in graph.nodes(data=True):
                    try:
                        self.upsert_entity(session, node_id, data)
                        nodes_synced += 1
                    except Exception as e:
                        logger.error(
                            f"节点同步失败 | node_id: {node_id} | 错误: {e}"
                        )

                # 2.2 同步关系 (UPSERT)
                edges_synced = 0
                for source, target, data in graph.edges(data=True):
                    try:
                        self.upsert_relationship(session, source, target, data)
                        edges_synced += 1
                    except Exception as e:
                        logger.error(
                            f"关系同步失败 | {source} -> {target} | 错误: {e}"
                        )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Neo4j 同步完成 | doc_id: {doc_id or 'full_sync'} | "
                f"节点: {nodes_synced}/{node_count} | "
                f"边: {edges_synced}/{edge_count} | "
                f"耗时: {elapsed_ms:.2f}ms"
            )

            return {"nodes_synced": nodes_synced, "edges_synced": edges_synced}

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Neo4j 同步失败 | doc_id: {doc_id or 'full_sync'} | "
                f"耗时: {elapsed_ms:.2f}ms | 错误: {e}"
            )
            raise

    def _extract_entity_type_from_json(self, entity_data: dict[str, Any]) -> str:
        """
        从 LightRAG JSON 实体数据中提取实体类型

        Args:
            entity_data: 实体数据字典

        Returns:
            实体类型字符串（如果不存在返回 "unknown"）
        """
        # LightRAG JSON 格式中，实体类型可能在 entity_type 或 content 中
        entity_type = entity_data.get("entity_type", "unknown")
        if entity_type != "unknown":
            return entity_type

        # 如果 entity_type 不存在，尝试从 content 解析
        # LightRAG 格式: "entity_name: xxx\nentity_type: location\n..."
        content = entity_data.get("content", "")
        for line in content.split("\n"):
            if line.strip().startswith("entity_type:"):
                entity_type = line.split(":", 1)[1].strip()
                break

        return entity_type if entity_type else "unknown"

    def sync_from_json(
        self,
        doc_id: int | None = None,
        incremental: bool = True,
        last_sync_timestamp: int | None = None,
    ) -> dict[str, int]:
        """
        直接从 LightRAG JSON 文件同步到 Neo4j (推荐方法)

        Args:
            doc_id: 文档 ID (用于日志追踪)
            incremental: 是否增量同步（仅同步新增数据）
            last_sync_timestamp: 上次同步时间戳（Unix time，秒）

        Returns:
            统计信息 {"nodes_synced": int, "edges_synced": int}

        流程:
        1. 读取 kv_store_full_entities.json
        2. 读取 kv_store_full_relations.json
        3. 过滤新增数据（based on __created_at__）
        4. UPSERT 到 Neo4j
        """
        entities_file = settings.lightrag_workspace_path / "kv_store_full_entities.json"
        relations_file = settings.lightrag_workspace_path / "kv_store_full_relations.json"

        # 检查文件是否存在
        if not entities_file.exists():
            logger.warning(f"实体 JSON 文件不存在 | 路径: {entities_file}")
            return {"nodes_synced": 0, "edges_synced": 0}

        if not relations_file.exists():
            logger.warning(f"关系 JSON 文件不存在 | 路径: {relations_file}")
            # 只同步实体，关系数为 0
            pass

        logger.info(
            f"开始同步 JSON → Neo4j | "
            f"doc_id: {doc_id or 'full_sync'} | "
            f"模式: {'增量' if incremental else '全量'} | "
            f"时间戳: {last_sync_timestamp or 0}"
        )
        start_time = time.perf_counter()

        try:
            # 1. 读取实体 JSON
            with open(entities_file, "r", encoding="utf-8") as f:
                entities = json.load(f)

            # 2. 增量过滤（基于 __created_at__ 时间戳）
            total_entities = len(entities)
            if incremental and last_sync_timestamp:
                entities = {
                    eid: data
                    for eid, data in entities.items()
                    if data.get("__created_at__", 0) > last_sync_timestamp
                }
                logger.debug(
                    f"增量过滤完成 | "
                    f"总数: {total_entities} | 新增: {len(entities)}"
                )

            # 3. 读取关系 JSON
            relations = {}
            if relations_file.exists():
                with open(relations_file, "r", encoding="utf-8") as f:
                    relations = json.load(f)

                # 增量过滤关系
                total_relations = len(relations)
                if incremental and last_sync_timestamp:
                    relations = {
                        rid: data
                        for rid, data in relations.items()
                        if data.get("__created_at__", 0) > last_sync_timestamp
                    }
                    logger.debug(
                        f"关系增量过滤完成 | "
                        f"总数: {total_relations} | 新增: {len(relations)}"
                    )

            # 4. 同步到 Neo4j
            with self.driver.session(database=settings.neo4j_database) as session:
                # 4.1 同步实体节点
                nodes_synced = 0
                for entity_id, entity_data in entities.items():
                    try:
                        # 提取实体信息
                        entity_name = entity_data.get("entity_name", entity_id)
                        entity_type = self._extract_entity_type_from_json(
                            entity_data
                        )
                        description = entity_data.get("content", "")
                        source_id = entity_data.get("source_id", "")
                        created_at = entity_data.get("__created_at__", 0)

                        # 构建节点数据
                        node_data = {
                            "name": entity_name,
                            "entity_id": entity_id,
                            "entity_type": entity_type,
                            "description": description,
                            "source_id": source_id,
                            "file_path": "lightrag_json",
                            "created_at": int(created_at),
                        }

                        # UPSERT 节点
                        self.upsert_entity(session, entity_name, node_data)
                        nodes_synced += 1

                    except Exception as e:
                        logger.error(
                            f"实体同步失败 | entity_id: {entity_id} | 错误: {e}"
                        )

                # 4.2 同步关系
                edges_synced = 0
                for relation_id, relation_data in relations.items():
                    try:
                        # 提取关系信息
                        src_id = relation_data.get("src_id", "")
                        tgt_id = relation_data.get("tgt_id", "")

                        if not src_id or not tgt_id:
                            logger.warning(
                                f"关系缺少源或目标节点 | relation_id: {relation_id}"
                            )
                            continue

                        description = relation_data.get("content", "related_to")
                        weight = relation_data.get("weight", 1.0)
                        keywords = relation_data.get("keywords", "")
                        source_id = relation_data.get("source_id", "")
                        created_at = relation_data.get("__created_at__", 0)

                        # 构建关系数据
                        rel_data = {
                            "description": description,
                            "weight": float(weight),
                            "keywords": keywords,
                            "source_id": source_id,
                            "file_path": "lightrag_json",
                            "created_at": int(created_at),
                        }

                        # UPSERT 关系
                        self.upsert_relationship(session, src_id, tgt_id, rel_data)
                        edges_synced += 1

                    except Exception as e:
                        logger.error(
                            f"关系同步失败 | relation_id: {relation_id} | 错误: {e}"
                        )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"JSON 同步完成 | doc_id: {doc_id or 'full_sync'} | "
                f"节点: {nodes_synced} | 边: {edges_synced} | "
                f"耗时: {elapsed_ms:.2f}ms"
            )

            return {"nodes_synced": nodes_synced, "edges_synced": edges_synced}

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"JSON 同步失败 | doc_id: {doc_id or 'full_sync'} | "
                f"耗时: {elapsed_ms:.2f}ms | 错误: {e}"
            )
            raise

    def get_last_sync_timestamp(self) -> int:
        """
        获取上次同步时间戳（从 Neo4j 元数据节点）

        Returns:
            Unix 时间戳（秒），如果不存在返回 0
        """
        query = """
        MATCH (m:_SyncMetadata {key: 'last_sync_timestamp'})
        RETURN m.value AS timestamp
        """

        try:
            with self.driver.session(database=settings.neo4j_database) as session:
                result = session.run(query)
                record = result.single()

                if record:
                    timestamp = record["timestamp"]
                    logger.debug(f"读取上次同步时间戳: {timestamp}")
                    return int(timestamp)
                else:
                    logger.debug("未找到同步时间戳，返回 0")
                    return 0

        except Exception as e:
            logger.warning(f"读取同步时间戳失败 | 错误: {e}")
            return 0

    def update_sync_timestamp(self, timestamp: int) -> None:
        """
        更新同步时间戳到 Neo4j 元数据节点

        Args:
            timestamp: Unix 时间戳（秒）
        """
        query = """
        MERGE (m:_SyncMetadata {key: 'last_sync_timestamp'})
        SET m.value = $timestamp, m.updated_at = timestamp()
        """

        try:
            with self.driver.session(database=settings.neo4j_database) as session:
                session.run(query, {"timestamp": timestamp})
                logger.debug(f"更新同步时间戳: {timestamp}")

        except Exception as e:
            logger.error(f"更新同步时间戳失败 | 错误: {e}")
            raise

    def create_indexes(self) -> None:
        """
        创建 Neo4j 索引 (提升查询性能)

        在首次初始化时调用
        """
        logger.info("开始创建 Neo4j 索引...")

        index_queries = [
            # 在 Entity.name 上创建唯一索引 (用于 MERGE)
            "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS "
            "FOR (n:Entity) REQUIRE n.name IS UNIQUE",
            # 在 entity_type 上创建索引 (用于类型过滤)
            "CREATE INDEX entity_type_idx IF NOT EXISTS "
            "FOR (n:Entity) ON (n.entity_type)",
            # 在 description 上创建全文索引 (用于关键词搜索)
            "CREATE FULLTEXT INDEX entity_description_fulltext IF NOT EXISTS "
            "FOR (n:Entity) ON EACH [n.description]",
        ]

        with self.driver.session(database=settings.neo4j_database) as session:
            for query in index_queries:
                try:
                    session.run(query)
                    logger.debug(f"索引创建成功: {query[:60]}...")
                except Exception as e:
                    logger.warning(f"索引创建失败 | 查询: {query[:60]}... | 错误: {e}")

        logger.info("Neo4j 索引创建完成")

    def clear_all(self) -> int:
        """
        清空 Neo4j 中的所有节点和关系 (慎用!)

        Returns:
            删除的节点数量
        """
        logger.warning("开始清空 Neo4j 数据库 | 这是危险操作!")

        with self.driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                "MATCH (n) DETACH DELETE n RETURN count(n) AS count"
            )
            count = result.single()["count"]

        logger.info(f"Neo4j 数据库已清空 | 删除节点数: {count}")
        return count


# 全局单例
_neo4j_service: Neo4jService | None = None


def get_neo4j_service() -> Neo4jService:
    """获取 Neo4j 服务单例"""
    global _neo4j_service
    if _neo4j_service is None:
        logger.info("首次创建 Neo4j 服务实例...")
        _neo4j_service = Neo4jService()
        _neo4j_service.create_indexes()
        logger.info("Neo4j 服务实例创建完成")
    return _neo4j_service
