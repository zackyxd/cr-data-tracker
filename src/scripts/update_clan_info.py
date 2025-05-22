import asyncio
import numpy as np
from src.api_calls.cr_api import fetch_clan
from src.sql_scripts.sql_clans import update_clan_info, get_clans, get_clans_count
from src.utils.pool import init_pool
import time
from tqdm.asyncio import tqdm_asyncio, tqdm

# import src.config as config
# config.load_env()

async def get_clan_info(pool, clantag):
    data = await fetch_clan(pool, clantag)
    if not data:
        return None
    try:
        clan_league = int(np.clip(data.get('clanWarTrophies')//1000, 0, 5))
    except TypeError:
        # print('Could not compute clan league')
        return None
    return {
        "clantag": data.get("tag"),
        "clan_name": data.get("name"),
        "clan_trophy": data.get('clanWarTrophies'),
        'clan_league': clan_league # Get 0-5 depending on clan war trophies. 5000+ trophies all same so limit to 5. Will be used to determine a more accurate elo
    }

# async def main():
#     pool = await init_pool()
#     semaphore = asyncio.Semaphore(50)
#     clansCount = await get_clans_count(pool)
#
#     clans = await get_clans(pool)
#
#     async def process_clan(clan):
#         clantag = clan['clantag']
#         async with semaphore:
#             try:
#                 clanInfo = await get_clan_info(pool, clantag)
#             except Exception as e:
#                 print(e.message)
#             if clanInfo and isinstance(clanInfo, dict) and clanInfo.get('clantag'):
#                 await update_clan_info(pool, clanInfo)
#             else:
#                 tqdm.write(f" ⚠️ Skipping {clantag} — no valid api data.")
#
#
#     start = time.time()
#     await tqdm_asyncio.gather(*[process_clan(clan) for clan in clans])
#     print(f"Took {time.time() - start:.2f}s to do all clan updates for {clansCount} players\n")


async def update_all_clan_info(pool):
    print('🫂 Updating all clan info with league and trophies...')
    semaphore = asyncio.Semaphore(30)
    clans = await get_clans(pool)
    clanCount = len(clans)
    processed = 0
    skipped = 0
    update_batch = 50
    completed_since_last_update = 0
    progress = tqdm(clans, desc='🆙 Updating Clan Info', dynamic_ncols=True, leave=False)
    async def process_clan(clan):
        nonlocal processed, skipped, completed_since_last_update
        clantag = clan['clantag']
        async with semaphore:
            clanInfo = await get_clan_info(pool, clantag)
            if clanInfo and isinstance(clanInfo, dict) and clanInfo.get('clantag'):
                await update_clan_info(pool, clanInfo)
                processed += 1
            else:
                skipped += 1
            completed_since_last_update += 1
            if completed_since_last_update >= update_batch:
                progress.update(completed_since_last_update)
                completed_since_last_update = 0

    start = time.time()
    await tqdm_asyncio.gather(*[process_clan(clan) for clan in clans])
    # Final leftover progress
    if completed_since_last_update > 0:
        progress.update(completed_since_last_update)
    progress.close()
    print(f"✅ Done! Processed: {processed}, Skipped: {skipped}, Total: {clanCount}")
    print(f"Took {time.time() - start:.2f}s to do all clan updates")



# if __name__ == "__main__":
#     asyncio.run(main())