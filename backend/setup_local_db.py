"""
本地数据库初始化脚本

用于创建 MySQL 数据库和表
"""
import asyncio
import sys

import aiomysql
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.models import Base


async def create_database():
    """创建数据库(如果不存在)"""
    # 从 DSN 中提取连接信息
    # 格式: mysql+aiomysql://user:password@host:port/database
    dsn = settings.mysql_dsn
    parts = dsn.replace("mysql+aiomysql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    user = user_pass[0]
    password = user_pass[1]
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 3306
    database = host_db[1]

    print(f"📊 连接信息:")
    print(f"   主机: {host}:{port}")
    print(f"   用户: {user}")
    print(f"   数据库: {database}")
    print()

    try:
        # 连接到 MySQL 服务器(不指定数据库)
        print("🔌 连接到 MySQL 服务器...")
        connection = await aiomysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
        )

        async with connection.cursor() as cursor:
            # 检查数据库是否存在
            await cursor.execute(
                f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{database}'"
            )
            result = await cursor.fetchone()

            if result:
                print(f"✅ 数据库 '{database}' 已存在")
            else:
                # 创建数据库
                print(f"🔨 创建数据库 '{database}'...")
                await cursor.execute(
                    f"CREATE DATABASE {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                print(f"✅ 数据库 '{database}' 创建成功")

        connection.close()
        return True

    except aiomysql.Error as e:
        print(f"❌ 数据库操作失败: {e}")
        print("\n💡 请检查:")
        print("   1. MySQL 服务是否正在运行")
        print("   2. .env 文件中的用户名和密码是否正确")
        print("   3. 用户是否有创建数据库的权限")
        return False


async def create_tables():
    """创建数据表"""
    try:
        print("\n🔨 创建数据表...")
        engine = create_async_engine(
            settings.mysql_dsn,
            echo=True,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await engine.dispose()
        print("\n✅ 数据表创建成功!")
        return True

    except Exception as e:
        print(f"\n❌ 创建数据表失败: {e}")
        return False


async def verify_connection():
    """验证数据库连接"""
    try:
        print("\n🔍 验证数据库连接...")
        engine = create_async_engine(settings.mysql_dsn, echo=False)

        async with engine.connect() as conn:
            result = await conn.execute("SELECT VERSION()")
            version = result.scalar()
            print(f"✅ 连接成功! MySQL 版本: {version}")

        await engine.dispose()
        return True

    except Exception as e:
        print(f"❌ 连接验证失败: {e}")
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("UrbanClimate-Expert 本地数据库初始化")
    print("=" * 60)
    print()

    # 1. 创建数据库
    if not await create_database():
        sys.exit(1)

    # 2. 创建数据表
    if not await create_tables():
        sys.exit(1)

    # 3. 验证连接
    if not await verify_connection():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ 数据库初始化完成!")
    print("=" * 60)
    print("\n下一步:")
    print("1. 启动后端服务:")
    print('   "D:\\anaconda\\python.exe" -m uvicorn app.main:app --reload')
    print()
    print("2. 访问 API 文档:")
    print("   http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    asyncio.run(main())
