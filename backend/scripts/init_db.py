"""
数据库初始化脚本

用于创建所有数据库表结构。

使用方法:
    python init_db.py

或者在 Windows 环境下:
    "D:\\anaconda\\python.exe" "c:\\Users\\wxb55\\Desktop\\urban_climate_expert\\backend\\init_db.py"
"""
import asyncio
import sys
from pathlib import Path

# 将 backend 目录添加到 Python 路径
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logger import logger
from app.db.models import Base
from app.db.session import get_engine, close_db


async def init_database() -> None:
    """
    初始化数据库，创建所有表结构

    该函数会:
    1. 连接到 MySQL 数据库
    2. 创建所有在 models.py 中定义的表
    3. 如果表已存在，不会重复创建（使用 create_all 的默认行为）
    """
    logger.info("=" * 60)
    logger.info("开始数据库初始化")
    logger.info("=" * 60)

    # 解析 DSN 获取数据库信息（隐藏密码）
    try:
        dsn = settings.mysql_dsn
        # 格式: mysql+aiomysql://user:password@host:port/database
        if "@" in dsn:
            prefix, suffix = dsn.split("@", 1)
            user_part = prefix.split("://")[1].split(":")[0]
            host_db = suffix
            logger.info(f"数据库连接信息: 用户={user_part}, 地址={host_db}")
        else:
            logger.info(f"数据库 DSN: {dsn[:30]}...")
    except Exception:
        logger.info("无法解析数据库连接字符串")

    try:
        # 获取数据库引擎
        engine = get_engine()

        # 创建所有表
        logger.info("正在创建数据库表...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 列出创建的表
        table_names = list(Base.metadata.tables.keys())
        logger.info(f"数据库表创建完成，共 {len(table_names)} 个表:")
        for table_name in table_names:
            table = Base.metadata.tables[table_name]
            columns = [col.name for col in table.columns]
            logger.info(f"  - {table_name}: {', '.join(columns)}")

        logger.info("=" * 60)
        logger.info("数据库初始化成功!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

    finally:
        # 关闭数据库连接
        await close_db()


async def drop_all_tables() -> None:
    """
    删除所有表（危险操作，仅用于开发环境重置）

    警告: 此操作会删除所有数据，无法恢复！
    """
    logger.warning("=" * 60)
    logger.warning("警告: 即将删除所有数据库表!")
    logger.warning("=" * 60)

    try:
        engine = get_engine()

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.info("所有表已删除")

    except Exception as e:
        logger.error(f"删除表失败: {e}")
        raise

    finally:
        await close_db()


async def reset_database() -> None:
    """
    重置数据库（删除所有表后重新创建）

    警告: 此操作会删除所有数据，无法恢复！
    """
    logger.warning("=" * 60)
    logger.warning("警告: 即将重置数据库!")
    logger.warning("此操作将删除所有数据，无法恢复!")
    logger.warning("=" * 60)

    try:
        engine = get_engine()

        # 先删除所有表
        logger.info("正在删除所有表...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("所有表已删除")

        # 重新创建所有表
        logger.info("正在重新创建表...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        table_names = list(Base.metadata.tables.keys())
        logger.info(f"数据库重置完成，共 {len(table_names)} 个表")

    except Exception as e:
        logger.error(f"数据库重置失败: {e}")
        raise

    finally:
        await close_db()


def main() -> None:
    """主入口函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="UrbanClimate-Expert 数据库初始化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python init_db.py              # 创建所有表
  python init_db.py --reset      # 重置数据库（删除后重建）
  python init_db.py --drop       # 仅删除所有表

注意:
  --reset 和 --drop 操作会删除所有数据，请谨慎使用！
        """
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="重置数据库（删除所有表后重新创建）"
    )

    parser.add_argument(
        "--drop",
        action="store_true",
        help="删除所有表（危险操作）"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过确认提示（用于自动化脚本）"
    )

    args = parser.parse_args()

    # 危险操作需要确认
    if args.reset or args.drop:
        if not args.yes:
            action = "重置" if args.reset else "删除所有表"
            print(f"\n警告: 您即将{action}，此操作将删除所有数据！")
            confirm = input("请输入 'yes' 确认操作: ")
            if confirm.lower() != "yes":
                print("操作已取消")
                sys.exit(0)

        if args.reset:
            asyncio.run(reset_database())
        elif args.drop:
            asyncio.run(drop_all_tables())
    else:
        # 默认: 仅创建表
        asyncio.run(init_database())


if __name__ == "__main__":
    main()
