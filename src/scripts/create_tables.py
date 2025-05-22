from dotenv import load_dotenv
# import psycopg2
import os
import asyncio
import asyncpg
from aiolimiter import AsyncLimiter
from src.utils.path_helper import build_path
# import src.config as config
# config.load_env()


async def create_schema():
    conn = await asyncpg.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv("DB_NAME"),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )

    with open(build_path("schema", "init_schema.sql"), "r") as f:
        schema_sql = f.read()

    try:
        await conn.execute(schema_sql)
        print("✅ Schema created successfully.")
    except Exception as e:
        print("❌ Failed to create schema:", e)
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(create_schema())
