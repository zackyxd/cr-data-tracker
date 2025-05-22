import asyncio
# from src.api_calls.cr_api import fetch_members_in_clan
from cr_tracker.sql_scripts.sql_players import insert_bulk_players
from cr_tracker.api_calls.cr_api import fetch_participants_in_clan, fetch_members_in_clan
# import src.config as config
# config.load_env()

async def fetch_all_members(pool, clantag):
    memberList = await fetch_members_in_clan(pool, clantag) or []
    participantList = await fetch_participants_in_clan(pool, clantag) or []
    combined = {p['playertag']: p for p in memberList + participantList}
    # singleList = memberList + participantList
    return list(combined.values())

async def init_players(pool, clan_info_list):
    tasks = [fetch_all_members(pool, clan['clantag']) for clan in clan_info_list]
    results = await asyncio.gather(*tasks)
    all_players = [p for clan_players in results if clan_players for p in clan_players]
    deduped = {p['playertag']: (p['player_name'], True) for p in all_players}  # add is_tracked=True
    await insert_bulk_players(pool, [(tag, name, tracked) for tag, (name, tracked) in deduped.items()])


# if __name__ == "__main__":
#     asyncio.run(main())