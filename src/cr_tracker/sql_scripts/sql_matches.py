import json
import time

async def insert_matches_bulk(conn, match_rows):
    if not match_rows:
        return
    # start = time.perf_counter()
    await conn.executemany("""
        INSERT INTO matches (
            clantag, player_name, opponent_player_name, playertag, opponent_playertag, player_deck_id, opponent_deck_id, player_card_levels,
            opponent_card_levels, battle_type, duel_round, match_result, clan_league, elixir_leaked, 
            battle_time, season, week, current_day, is_void
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
        ON CONFLICT (playertag, battle_time, duel_round) DO NOTHING
    """, match_rows)
    # print(f'[Timing] Inserting bulk matches took {time.perf_counter() - start:.3f}s')

async def get_match_count(pool):
    async with pool.acquire() as conn:
        matchCount = await conn.fetchval(f"""
        SELECT * from matches where season IS NULL AND week IS NULL""")
        return matchCount