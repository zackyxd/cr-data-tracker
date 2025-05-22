import asyncio
import json
import time

from tqdm.asyncio import tqdm_asyncio, tqdm

from cr_tracker.api_calls.cr_api import fetch_player, fetch_last_river_race_log
from cr_tracker.sql_scripts.sql_players import update_player_stats, get_entire_players


# import src.config as config
# config.load_env()

async def upload_player_stats(pool, player_data, season, week):
    playertag = player_data.get('tag')
    if not playertag:
        print(" ⚠️ upload_player_stats called with invalid player_data (missing tag):", player_data)
        return
    player_name = player_data.get('name')
    exp_level = player_data.get('expLevel', -1)
    acc_wins = player_data.get('wins', -1)
    acc_losses = player_data.get('losses', -1)
    trophy_road = player_data.get('trophies', -1)

    badge_list = player_data.get('badges', [])

    # Build a quick lookup dict for convenience
    badge_lookup = {b['name']: b for b in badge_list if 'name' in b}

    classic_wins = badge_lookup.get('Classic12Wins', {}).get('progress', 0)
    grand_wins = badge_lookup.get('Grand12Wins', {}).get('progress', 0)
    clan_war_wins = badge_lookup.get('ClanWarWins', {}).get('progress', 0)

    important_badges = {
        'Crl20Wins2021',
        'Crl20Wins2022',
        'Crl20Wins2023',
        'Crl20Wins2024',
        'Crl20Wins2025',
        'Crl20Wins2026',
        'LadderTournamentTop1000',
        'LadderTop1000',
        'CrlCompetitor2021',
        'CrlCompetitor2022',
        'CrlCompetitor2023',
        'CrlCompetitor2024',
        'CrlCompetitor2025',
        'CrlCompetitor2026',
        'CrlChampion2021',
        'CrlChampion2022',
        'CrlChampion2023',
        'CrlChampion2024',
        'CrlChampion2025',
        'CrlFinalist2022',
        'CrlFinalist2023',
        'CrlFinalist2024',
        'CrlFinalist2025',
        'CrlFinalist2026',
    }
    badges_json = [
        {
            "name": b["name"],
            "progress": b.get("progress", 1),
            "level": b.get("level", 0)
        }
        for b in badge_list if b.get("name") in important_badges
    ]
    # print(badges_json)

    badges_json_str = json.dumps(badges_json)  # Convert list to JSON string
    # print(badges_json_str)

    current_data = player_data.get('currentPathOfLegendSeasonResult', {}) or {}
    last_data = player_data.get('lastPathOfLegendSeasonResult', {}) or {}
    best_data = player_data.get('bestPathOfLegendSeasonResult', {}) or {}


    current_uc_medals = current_data.get('trophies') if current_data.get('leagueNumber') == 10 else None
    last_uc_medals = last_data.get('trophies') if last_data.get('leagueNumber') == 10 else None
    last_uc_rank = last_data.get('rank') if last_data.get('leagueNumber') == 10 else None
    best_uc_medals = best_data.get('trophies') if best_data.get('leagueNumber') == 10 else None
    best_uc_rank = best_data.get('rank') if best_data.get('leagueNumber') == 10 else None

    await update_player_stats(pool, player_name, playertag, season, week, exp_level, acc_wins, acc_losses, trophy_road, classic_wins, grand_wins, clan_war_wins, current_uc_medals, last_uc_medals, last_uc_rank, best_uc_medals, best_uc_rank, badges_json_str)

async def getSeasonWeek(pool, data):
    season = data['seasonId']
    week = data['sectionIndex'] + 1
    return season, week


# async def main():
#     pool = await init_pool()
#     semaphore = asyncio.Semaphore(50)
#     players = await get_all_players(pool)
#     # for player in players:
#         # print(player)
#     playersCount = await get_all_players_count(pool)
#     clantag = '9U82JJ0Y'
#     rrLog = await fetch_last_river_race_log(pool, clantag)
#     data = rrLog['items'][0]
#     season, week = await getSeasonWeek(pool, data)
#     # playertag = '#G9YV9GR8R'
#     # 209Y0JPY2Q noob, mo G9YV9GR8R
#     # print(type(data), isinstance(data,dict), data)
#     # data = await fetch_player(pool, playertag)
#     # await upload_player_stats(pool, data, season, week)
#
#     failed_players = []
#     async def process_player(player):
#         playertag = player['playertag']
#         async with semaphore:
#             stats = await fetch_player(pool, playertag)
#             if stats and isinstance(stats, dict) and stats.get('tag'):
#                 await upload_player_stats(pool, stats, season, week)
#             else:
#                 tqdm.write(f" ⚠️ Skipping {playertag} — no valid api data. {stats} {isinstance(stats,dict)} {stats.get('tag')}")
#                 failed_players.append(playertag)
#
#     start = time.time()
#     await tqdm_asyncio.gather(*[process_player(player) for player in players])
#     print(f"Took {time.time() - start:.2f}s to do all logs for {playersCount} players\n")
#
#     print(failed_players)


async def update_all_player_stats(pool):
    semaphore = asyncio.Semaphore(30)
    players = await get_entire_players(pool)
    playersCount = len(players)
    clantag = '9U82JJ0Y'
    rrLog = await fetch_last_river_race_log(pool, clantag)
    data = rrLog['items'][0]
    season, week = await getSeasonWeek(pool, data)

    failed_players = []
    processed = 0
    skipped = 0
    update_batch = 50
    completed_since_last_update = 0
    progress = tqdm(players, desc='🆙 Updating Player Weekly Stats', dynamic_ncols=True, leave=False)
    async def process_player(player):
        nonlocal processed, skipped, completed_since_last_update
        playertag = player['playertag']
        async with semaphore:
            stats = await fetch_player(pool, playertag)
            if stats and isinstance(stats, dict) and stats.get('tag'):
                await upload_player_stats(pool, stats, season, week)
                processed += 1
            else:
                skipped += 1
                failed_players.append(playertag)
        completed_since_last_update += 1
        if completed_since_last_update >= update_batch:
            progress.update(completed_since_last_update)
            completed_since_last_update = 0

    start = time.time()
    await tqdm_asyncio.gather(*[process_player(player) for player in players])
    if completed_since_last_update > 0:
        progress.update(completed_since_last_update)
    progress.close()
    print(f"✅ Done! Processed: {processed}, Skipped: {skipped}, Total: {playersCount}")
    print(f"Took {time.time() - start:.2f}s to do all player weekly stats.")
# if __name__ == "__main__":
#     asyncio.run(main())