import asyncio

import asyncpg
import pytest_asyncio
# from src.utils.path_helper import build_path
import os
from src.utils.pool import init_pool
os.environ["ENV"] = "test"
import src.config as config
config.load_env()


@pytest_asyncio.fixture()
def event_loop():
    # Needed to make asyncio work properly with pytest
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope='function')
async def pool():
    return await init_pool()

@pytest_asyncio.fixture(scope='function', autouse=True)
async def database_setup(pool):

    async with pool.acquire() as conn:
        # Drop and recreate schema or truncate
        await conn.execute("""TRUNCATE players, clans, logs RESTART IDENTITY CASCADE""")

        # Later, recreate schema if needed

    yield # This is where tests run
    async with pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE players, clans, logs
            RESTART IDENTITY CASCADE;
        """)

@pytest_asyncio.fixture
async def db_pool(pool):
    pool = await init_pool()
    print(pool)
    yield pool
    await pool.close()
