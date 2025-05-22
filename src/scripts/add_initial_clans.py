import asyncio
from src.utils.pool import init_pool
# from src.api_calls.cr_api import fetch_members_in_clan
from src.sql_scripts.sql_clans import insert_clans
from src.api_calls.cr_api import fetch_clan
import json
import numpy as np
# import src.config as config
# config.load_env()
import asyncio
async def get_clan_info(pool, clantag):
    try:
        data = await fetch_clan(pool, clantag)
        if not data:
            return None
        return {
            "clantag": data.get("tag"),
            "clan_name": data.get("name"),
            "clan_trophy": data.get('clanWarTrophies'),
            'clan_league': int(np.clip(data.get('clanWarTrophies')//1000, 0, 5)) # Get 0-5 depending on clan war trophies. 5000+ trophies all same so limit to 5. Will be used to determine a more accurate elo
        }
    except asyncio.TimeoutError:
        print(f"⚠️ Timeout while fetching {clantag}")
        return None

# Add first clans to be checked, rest will be automatically added later.
async def init_clans(pool):

    clantags = ['#9U82JJ0Y', '#8CYR2V', '#V2GQU', '#YC8R0RJ0', '#L9VRJ', '#8UJ2UUJ8', '#P2P2Y880']

    tasks = [get_clan_info(pool, tag) for tag in clantags]
    results = await asyncio.gather(*tasks)
    clan_info_list = [clan for clan in results if clan is not None]

    for clan in clan_info_list:
        assert "clantag" in clan and "clan_name" in clan, f"Invalid clan: {clan}"

    await insert_clans(pool, clan_info_list)
    return clan_info_list
