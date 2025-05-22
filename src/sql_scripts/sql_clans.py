import time
# Insert clan to SQL
import json
async def insert_clan(pool, clanInfo):
    # start = time.perf_counter()

    async with pool.acquire() as conn:
        result = await conn.execute("""
        INSERT INTO clans (clantag, clan_name, clan_trophy, clan_league)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (clantag) DO NOTHING
        """, clanInfo.get('clantag'), clanInfo.get('clan_name'), clanInfo.get('clan_trophy'), clanInfo.get('clan_league'))
    await log_event_success(pool, result, event_type="insert_clan", context=json.dumps(clanInfo), message='Insert to clans table', success=True)
    # print(f'[Timing] insert single clan took {time.perf_counter() - start:.3f}s')

async def insert_clans(pool, clanInfoList):
    # start = time.perf_counter()
    async with pool.acquire() as conn:
        beforeCount = await conn.fetchval("SELECT COUNT(*) FROM clans")
        result = await conn.executemany("""
        INSERT INTO clans (clantag, clan_name, clan_trophy, clan_league)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (clantag) DO NOTHING
        """, [(clan['clantag'], clan['clan_name'], clan['clan_trophy'], clan['clan_league']) for clan in clanInfoList]) # Tuple needed for executemany
        afterCount = await conn.fetchval("SELECT COUNT(*) FROM clans")
    inserted = afterCount - beforeCount
    await log_event_success(pool, result, event_type="insert_clans", context=json.dumps(clanInfoList), message=f'Insert {inserted} clans to clans table', success=True)
    # print(f'[Timing] inserting {inserted} clans took {time.perf_counter() - start:.3f}s')

async def update_clan_info(pool, clan):
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE clans
        SET clan_trophy = $2, clan_league = $3, last_checked = NOW()
        where clantag = $1
        """, clan['clantag'], clan['clan_trophy'], clan['clan_league'])

async def log_event_success(pool, result, event_type, context, message, success):
    if result is not None and 'INSERT 0 1' in result:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO logs (event_type, message, success, context)
                VALUES ($1, $2, $3, $4)
            """, event_type, message, success, context)
    else:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO logs (event_type, message, success, context)
                VALUES ($1, $2, $3, $4)
            """, event_type, message, success, context)

# async def insert_clan_if_not_exists(pool, clanInfo):
#     async with pool.acquire() as conn:
#         exists = await conn.fetchval("SELECT 1 FROM clans WHERE clantag = $1", clanInfo.get('clantag'))
#         if not exists:
#             await insert_clan(pool, clanInfo)

async def get_clans_count(pool):
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) from clans")

async def get_clans(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * from clans")

async def get_valid_clans(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * from clans where clan_trophy > 3500")

async def get_clan_league(pool, clantag):
    # start = time.perf_counter()
    async with pool.acquire() as conn:
        clan_league = await conn.fetchval("""
        SELECT clan_league 
        FROM clans
        WHERE clantag = $1
        """, clantag)
    # print(f'[Timing] insert single clan took {time.perf_counter() - start:.3f}s')
    return clan_league

async def get_clan_trophy(pool, clantag):
    # start = time.perf_counter()
    async with pool.acquire() as conn:
        clan_trophy = await conn.fetchval("""
        SELECT clan_trophy
        FROM clans
        WHERE clantag = $1
        """, clantag)
    # print(f'[Timing] insert single clan took {time.perf_counter() - start:.3f}s')
    return clan_trophy


