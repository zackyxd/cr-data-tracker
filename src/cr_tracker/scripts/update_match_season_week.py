import time

from cr_tracker.sql_scripts.sql_matches import get_match_count

from cr_tracker.api_calls.cr_api import fetch_last_river_race_log
# import src.config as config
# config.load_env()

async def getSeasonWeek(pool, data):
    season = data['seasonId']
    week = data['sectionIndex'] + 1
    return season, week

async def updateAllSeasonWeeks(pool):
    print('🧑‍🔧 Updating all matches with their season/week...')
    matchCount = await get_match_count(pool)
    start = time.time()
    clantag = '9U82JJ0Y'
    rrLog = await fetch_last_river_race_log(pool, clantag)
    data = rrLog['items'][0]
    season, week = await getSeasonWeek(pool, data)
    async with pool.acquire() as conn:
        await conn.execute(f"""
        UPDATE matches
        SET season = $1,
        week = $2
        WHERE season IS NULL AND week IS NULL AND is_void = False
        """, season, week)
    print(f"Took {time.time() - start:.2f}s to update season/weeks for {matchCount} matches.\n")


# async def main():
#     pool = await init_pool()
#     await updateAllSeasonWeeks(pool)
#
# if __name__ == "__main__":
#     asyncio.run(main())