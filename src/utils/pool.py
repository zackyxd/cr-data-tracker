import asyncpg
import os

# Create pool that can be called so everything is connected
# To the same db
async def init_pool():
    return await asyncpg.create_pool(
        host=os.getenv('DB_HOST'),
        database=os.getenv("DB_NAME"),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT'),
        min_size=10, max_size=50
    )