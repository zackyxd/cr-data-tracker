import asyncio
import time

from src.api_calls.cr_api import fetch_last_river_race_log
from src.sql_scripts.sql_clans import get_clans, get_clans_count, get_clan_league, get_clan_trophy, get_valid_clans
from src.sql_scripts.sql_war import insert_clan_stats_bulk, insert_player_weekly_fame_bulk
from src.utils.pool import init_pool
from tqdm.asyncio import tqdm_asyncio, tqdm

# import src.config as config
# config.load_env()


async def track_clans(pool, raceData):
    race = raceData[0]
    season = race.get('seasonId', -1)
    week = race.get('sectionIndex', -2) + 1
    data_created_date = race.get('createdDate')
    standings = race.get('standings', {})
    clan_stat_rows = []
    player_fame_rows = []
    for clan in standings:
        clantag = clan.get('clan',{}).get('tag')
        clan_name = clan.get('clan', {}).get('name')
        clan_league = await get_clan_league(pool, clantag)
        clan_trophy = await get_clan_trophy(pool, clantag)
        if not clan_trophy or clan_trophy < 3500:
            continue
        placement = clan.get('rank', -1)
        clan_fame = clan.get('clan', {}).get('fame')
        wins = 0
        losses = 0
        clan_throws = 0
        participants = [p['tag'] for p in clan.get('clan', {}).get('participants', []) if p.get('fame',0) > 0]
        cut_day_4 = clan_fame >= 10000 and placement == 1

        for playertag in participants:
            # Query matches for player this season/week
            matches = await pool.fetch("""
            SELECT battle_type, duel_round, match_result, current_day
            FROM matches
            WHERE playertag = $1 AND season = $2 AND week = $3 and clantag = $4 and is_void = False
            """, playertag, season, week, clantag)
            player_fame = 0
            player_decks = 0
            player_throws = 0
            for match in matches:
                day = match['current_day']
                if day == 4 and cut_day_4:
                    continue

                is_duel = match['battle_type'] == 'Duel'
                result = match['match_result']

                if result == 'throw' or result == 'tie':
                    player_throws += 1
                    clan_throws += 1
                    continue  # ✅ Skip adding to decks_used or fame

                # 🎯 From this point down, it's a valid (non-throw) deck
                player_decks += 1

                if result == 'win':
                    player_fame += 250 if is_duel else 200
                    wins += 1
                elif result == 'loss':
                    player_fame += 100
                    losses += 1

            if player_fame > 0:
                player_fame_rows.append((
                    season, week, playertag, clantag, clan_league,
                    player_fame, player_decks, player_throws
                ))
        clan_stat_rows.append((
            clantag, clan_name, season, week, clan_league, placement, clan_fame,
            wins, losses, clan_throws, participants
        ))

    async with pool.acquire() as conn:
        async with conn.transaction():
            await insert_clan_stats_bulk(conn, clan_stat_rows)
            await insert_player_weekly_fame_bulk(conn, player_fame_rows)




# async def main():
#     pool = await init_pool()
#     clantag = '#9U82JJ0Y'
#     semaphore = asyncio.Semaphore(50)
#     clans = await get_valid_clans(pool)
#     clansCount = await get_clans_count(pool)
#
#     # clans = [{'clantag': '#YC8R0RJ0'}]
#     async def process_clan(clan):
#         clantag = clan['clantag']
#         async with semaphore:
#             data = await fetch_last_river_race_log(pool, clantag)
#             if data and isinstance(data, dict) and data.get('items'):
#                 await track_clans(pool, data.get('items'))
#     start = time.time()
#     await tqdm_asyncio.gather(*[process_clan(clan) for clan in clans])
#     print(f"Took {time.time() - start:.2f}s to do all logs for {clansCount} players\n")


async def store_river_race_info(pool):
    semaphore = asyncio.Semaphore(30)
    clans = await get_valid_clans(pool)
    clanCount = len(clans)
    processed = 0
    skipped = 0
    update_batch = 50
    completed_since_last_update = 0
    progress = tqdm(clans, desc='📊 Storing River Race Info', dynamic_ncols=True, leave=False)
    async def process_clan(clan):
        nonlocal processed, skipped, completed_since_last_update
        clantag = clan['clantag']
        async with semaphore:
            data = await fetch_last_river_race_log(pool, clantag)
            if data and isinstance(data, dict) and data.get('items'):
                await track_clans(pool, data.get('items'))
                processed += 1
            else:
                skipped += 1
            completed_since_last_update += 1
            if completed_since_last_update >= update_batch:
                progress.update(completed_since_last_update)
                completed_since_last_update = 0


    start = time.time()
    await tqdm_asyncio.gather(*[process_clan(clan) for clan in clans])
    if completed_since_last_update > 0:
        progress.update(completed_since_last_update)
    progress.close()
    print(f"✅ Done! Processed: {processed}, Skipped: {skipped}, Total: {clanCount}")
    print(f"Took {time.time() - start:.2f}s to store all river race info")


# if __name__ == "__main__":
#     asyncio.run(main())