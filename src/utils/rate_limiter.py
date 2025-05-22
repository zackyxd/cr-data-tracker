import datetime
from asyncpg.pool import Pool
import asyncio
from aiolimiter import AsyncLimiter

# RATE_LIMIT = 65
# WINDOW_SECONDS = 1

async def wait_and_record_api_call(pool: Pool, rate_limit: int, group_id: str, max_wait=5.0, check_interval=0.05) -> bool:
    waited = 0
    while waited < max_wait:
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                INSERT INTO api_calls_count (called_at, group_id)
                SELECT NOW(), $2
                WHERE (
                    SELECT COUNT(*) FROM api_calls_count
                    WHERE called_at >= (NOW() - INTERVAL '1 second')
                    AND group_id = $2
                ) < $1
                RETURNING called_at;
            """, rate_limit, group_id)  # Use rate_limit as group_id for simplicity

            if result:
                return True
            await asyncio.sleep(1)

        await asyncio.sleep(check_interval)
        waited += check_interval

    return False

# For fast requests (e.g., fetch_player)
async def wait_and_record_fast_call(pool: Pool, max_wait=10.0, check_interval=0.05) -> bool:
    return await wait_and_record_api_call(pool, rate_limit=50, group_id='fast', max_wait=max_wait, check_interval=check_interval)

# For slower or less frequent ones
async def wait_and_record_slow_call(pool: Pool, max_wait=10.0, check_interval=0.05) -> bool:
    return await wait_and_record_api_call(pool, rate_limit=70, group_id='slow', max_wait=max_wait, check_interval=check_interval)


"""
Create global limiter for API that makes sure
I stay under API limit
Call like:
    for attempt in range(retries):
        if await under_rate_limit(pool):
            await record_api_call(pool)
            async with aiohttp.ClientSession() as session:
                url = f'https://proxy.royaleapi.dev/v1/players/{encoded_tag}'
                async with session.get(url, headers=HEADERS) as resp:
                    print(f"Status: {resp.status} for {clantag}")
                    data = await resp.json()
                    return data
        else:
            # print(f"[Rate Limited] {clantag} - Retry {attempt + 1}/{retries}")
            await asyncio.sleep(delay)

    # print(f"[Failed] {clantag} after {retries} retries due to rate limiting.")
    return None
"""