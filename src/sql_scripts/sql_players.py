import json
import time
# Insert player to SQL
async def insert_player(pool, playertag, is_tracked=False):
    # start = time.perf_counter()
    async with pool.acquire() as conn:
        result = await conn.execute("""
        INSERT INTO players (playertag, is_tracked)
        VALUES ($1, $2)
        ON CONFLICT (playertag) DO NOTHING
        """, playertag, is_tracked)
    await log_event_success(pool, result, event_type="insert_player", context=playertag, message='Insert 1 player to players table', success=True)
    # print(f'[Timing] insert single player took {time.perf_counter() - start:.3f}s')

async def insert_players(pool, playertags, is_tracked=False):
    # start = time.perf_counter()
    rows_to_insert = [(tag, is_tracked) for tag in playertags]

    async with pool.acquire() as conn:
        beforeCount = await conn.fetchval("SELECT COUNT(*) FROM players")
        result = await conn.executemany("""
        INSERT INTO players (playertag, is_tracked)
        VALUES ($1, $2)
        ON CONFLICT (playertag) DO NOTHING
        """, rows_to_insert) # Create tuple needed for executemany
        afterCount = await conn.fetchval("SELECT COUNT(*) FROM players")
    inserted = afterCount - beforeCount
    await log_event_success(pool, result, event_type="insert_players", context=json.dumps(playertags), message=f'Insert {inserted} players to players table', success=True)
    # print(f'[Timing] insert {inserted} players took {time.perf_counter() - start:.3f}s')

# Insert bulk players if is_tracked will be different
async def insert_bulk_players(conn, rows):
    if not rows:
        return
    start = time.perf_counter()
    await conn.executemany("""
        INSERT INTO players (playertag, player_name, is_tracked)
        VALUES ($1, $2, $3) 
        ON CONFLICT (playertag) DO UPDATE
        SET player_name = EXCLUDED.player_name
    """, rows)
    # print(f'[Timing] insert bulk playertags took {time.perf_counter() - start:.3f}s')
    # -- tag, tracked, name


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

async def get_players_count(pool):
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) from players where is_tracked = True")

async def get_all_players_count(pool):
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) from players")

async def get_all_valid_players(pool, current_day):
    async with pool.acquire() as conn:
        return await conn.fetch(f"""
                                SELECT * from players
                                where is_tracked = True
                                AND COALESCE(day{current_day}_battles, 0) < 4""")

async def get_entire_players(pool):
    async with pool.acquire() as conn:
        return await conn.fetch(f"SELECT * from players")

async def get_player(pool, playertag, current_day):
    async with pool.acquire() as conn:
        return await conn.fetch(f"""
                                SELECT * from players
                                where is_tracked = True
                                AND COALESCE(day{current_day}_battles, 0) < 4
                                AND playertag = '{playertag}'""")


async def update_player_tracking(pool, playertag, is_tracked):
    # start = time.time()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE players
            SET is_tracked = $2
            WHERE playertag = $1
        """, playertag, is_tracked)
    # print(f'[Timing] Updating player to tracked = TRUE took {time.perf_counter() - start:.3f}s')

async def update_player_stats(pool, player_name, playertag, season, week, exp_level, acc_wins, acc_losses, trophy_road, classic_wins, grand_wins, clan_war_wins, current_uc_medals, last_uc_medals, last_uc_rank, best_uc_medals, best_uc_rank, badges):
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO player_weekly_stats (
            player_name, playertag, season, week, exp_level, acc_wins, acc_losses, trophy_road_trophies, classic_wins, grand_wins, clan_war_wins, current_uc_medals, last_uc_medals, last_uc_rank, best_uc_medals, best_uc_rank, important_badges)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            ON CONFLICT (playertag, season, week) DO NOTHING
        """, player_name, playertag, season, week, exp_level, acc_wins, acc_losses, trophy_road, classic_wins, grand_wins, clan_war_wins, current_uc_medals, last_uc_medals, last_uc_rank, best_uc_medals, best_uc_rank, badges)


