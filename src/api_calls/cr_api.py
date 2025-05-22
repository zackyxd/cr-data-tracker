import aiohttp
import asyncio

from aiolimiter import AsyncLimiter

from src.utils.rate_limiter import wait_and_record_api_call, wait_and_record_fast_call, wait_and_record_slow_call
import os
from urllib.parse import quote
from src.utils.pool import init_pool
from src.sql_scripts.sql_players import insert_player
from src.sql_scripts.sql_clans import insert_clan
from src.utils.maintenance import set_maintenance, is_under_maintenance
from src.sql_scripts.sql_api_calls import log_api_event
import json
# import src.config as config
# config.load_env()

global_limiter = AsyncLimiter(50, 1)
api_semaphore = asyncio.Semaphore(50)

timeout = aiohttp.ClientTimeout(total=10)
HEADERS = {"Authorization": f'Bearer {os.getenv('CR_API_KEY')}'}

# Convert tag to have # in front of it
def complete_tag(tag):
    if tag[0] != '#':
        tag = '#' + tag
    return tag

def encode_tag(tag):
    encoded_tag = quote(tag)
    return encoded_tag

# resp.status for status
# resp.url, resp.method for URL + method
# await resp.text() for raw body
# await resp.json() for parsed json
async def fetch_player(pool, playertag, max_retries=3):
    playertag = complete_tag(playertag)
    encoded_tag = encode_tag(playertag)

    for attempt in range(max_retries):
        if await is_under_maintenance():
            print("🛑 Skipping fetch — under maintenance cooldown.")
            return None
        try:
            async with api_semaphore:
                async with global_limiter:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        url = f'https://proxy.royaleapi.dev/v1/players/{encoded_tag}'
                        async with session.get(url, headers=HEADERS) as resp:
                            status = resp.status

                            if status == 503:
                                was_set = await set_maintenance(20)
                                if was_set:
                                    await log_api_event(pool, 'fetch_player', status, playertag, 'Maintenance Break', False)
                                return {'status': status, 'success': False, 'reason': 'Maintenance Break'}

                            if status == 404:
                                # print('❌ Player not found:', playertag)
                                await log_api_event(pool, 'fetch_player', status, playertag, 'Player Not Found', False)
                                return {'status': status, 'success': False, 'reason': 'Player Not Found'}

                            if status == 429:
                                print(f"⚠️ Real API rate limit hit for {playertag}, retrying...")
                                await log_api_event(pool, 'fetch_player', status, playertag, 'Rate limit hit', False)
                                await asyncio.sleep(2 ** attempt)
                                continue  # retry

                            if status != 200:
                                print(f"⚠️ Unexpected status {status} fetching {playertag}, retrying...")
                                await log_api_event(pool, 'fetch_player', status, playertag, 'Unexpected status', False)
                                await asyncio.sleep(2 ** attempt)
                                continue  # retry

                            data = await resp.json()
                            if data and "tag" in data:
                                # await log_api_event(pool, 'fetch_player', status, playertag, 'Received player data', True)
                                return data
                            else:
                                print(f"⚠️ Missing 'tag' in response for {playertag}")
                                return {'status': status, 'success': False, 'reason': 'Invalid response'}

        except asyncio.TimeoutError:
            print(f"⏱️ Timeout fetching player {playertag}, retrying...")
            await log_api_event(pool, 'fetch_player', 0, playertag, 'Timeout', False)
            await asyncio.sleep(2 ** attempt)
            continue  # retry

    print(f"❌ Failed to fetch {playertag} after {max_retries} retries.")
    return {'status': 0, 'success': False, 'reason': 'Retry Limit Exceeded'}


async def fetch_clan(pool, clantag):
    if await is_under_maintenance():
        print("🛑 Skipping fetch — under maintenance cooldown.")
        return None

    clantag = complete_tag(clantag)
    encoded_tag = encode_tag(clantag)

    try:
        async with api_semaphore:
            async with global_limiter:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    url = f'https://proxy.royaleapi.dev/v1/clans/{encoded_tag}'
                    async with session.get(url, headers=HEADERS) as resp:
                        status = resp.status
                        if status == 503: # If maintenance break, pause all API calls for 20 minutes
                            was_set = await set_maintenance(20)
                            if was_set:
                                await log_api_event(pool, event_type='fetch_clan', status_code=status, context=clantag, message='Maintenance Break', success=False)
                            return {'status': status, 'success': False, 'reason': 'Maintenance Break'}

                        if status == 404: # Invalid tag, or banned.
                            print('Clan was not found', clantag)
                            await log_api_event(pool, event_type='fetch_clan', status_code=status, context=clantag, message='Could not fetch clan', success=False)
                            return {'status': status, 'success': False, 'reason': 'Clan Not Found'}

                        if status == 429: # Rate limit hit
                            print('[Fetch Clan] Real Rate Limit Hit')
                            await log_api_event(pool, event_type='fetch_clan', status_code=status, context=clantag, message='Rate Limit Hit', success=False)
                            return {'status': status, 'success': False, 'reason': 'Rate Limit Hit'}

                        if status != 200:
                            # print(f"⚠️ Unexpected status fetching clan: {status}")
                            await log_api_event(pool, event_type='fetch_clan', status_code=status, context=clantag, message='Unknown error', success=False)
                            return {'status': status, 'success': False, 'reason': 'Unexpected Status'}

                        clanData = await resp.json()
                        if clanData:
                            # await log_api_event(pool, event_type='fetch_clan', status_code=status, context=clantag, message='Received clan data', success=True)
                            return clanData
    except asyncio.TimeoutError:
        # print(f"⏱️ Timeout fetching clan {clantag}")
        await log_api_event(pool, event_type='fetch_clan', status_code=0, context=clantag, message='Timeout', success=False)
        return {'status': 0, 'success': False, 'reason': 'Timeout'}
    print(f'[Rate Limited] Clan Fetch: {clantag}')
    return {'status': 429, 'success': False, 'reason': 'Rate Limit Hit'}


# Grab current rive race info
async def fetch_current_river_race(pool, clantag):
    if await is_under_maintenance():
        print("🛑 Skipping fetch — under maintenance cooldown.")
        return None

    clantag = complete_tag(clantag)
    encoded_tag = encode_tag(clantag)

    try:
        async with api_semaphore:
            async with global_limiter:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    url = f'https://proxy.royaleapi.dev/v1/clans/{encoded_tag}/currentriverrace'
                    async with session.get(url, headers=HEADERS) as resp:
                        status = resp.status

                        if status == 503:  # If maintenance break, pause all API calls for 20 minutes
                            was_set = await set_maintenance(20)
                            if was_set:
                                await log_api_event(pool, event_type='fetch_current_river_race', status_code=status, context=clantag,
                                                    message='Maintenance Break', success=False)
                            return {'status': status, 'success': False, 'reason': 'Maintenance Break'}

                        if status == 404:  # Invalid tag, or banned.
                            print('Clan was not found', clantag)
                            await log_api_event(pool, event_type='fetch_current_river_race', status_code=status, context=clantag,
                                                message='Could not fetch current river race', success=False)
                            return { 'status': status, 'success': False, 'reason': 'Current River Race Not Found' }

                        if status == 429: # Rate limit hit
                            await log_api_event(pool, event_type='fetch_clan', status_code=status, context=clantag, message='Rate Limit Hit', success=False)
                            return {'status': status, 'success': False, 'reason': 'Rate Limit Hit'}

                        if status != 200:
                            print(f"⚠️ Unexpected status fetching current river race: {status}")
                            await log_api_event(pool, event_type='fetch_current_river_race', status_code=status, context=clantag,
                                                message='Unknown error', success=False)
                            return { 'status': status, 'success': False, 'reason': 'Unexpected Status' }

                        data = await resp.json()
                        if data:
                            # await log_api_event(pool, event_type='fetch_current_river_race', status_code=status, context=clantag,
                            #                     message='Received current river race', success=True)
                            return data
    except asyncio.TimeoutError:
        print(f"⏱️ Timeout fetching current river race {clantag}")
        await log_api_event(pool, event_type='fetch_current_river_race', status_code=0, context=clantag, message='Timeout',
                            success=False)
        return {'status': 0, 'success': False, 'reason': 'Timeout'}
    # else:
    #     print(f'[Rate Limited] River Race Fetch: {clantag}')
    #     return {'status': 429, 'success': False, 'reason': 'Rate Limit Hit'}

async def fetch_battle_log(pool, playertag):
    if await is_under_maintenance():
        print("🛑 Skipping fetch — under maintenance cooldown.")
        return None

    playertag = complete_tag(playertag)
    encoded_tag = encode_tag(playertag)

    try:
        async with api_semaphore:
            async with global_limiter:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    url = f'https://proxy.royaleapi.dev/v1/players/{encoded_tag}/battlelog'
                    async with session.get(url, headers=HEADERS) as resp:
                        status = resp.status

                        if status == 503:  # If maintenance break, pause all API calls for 20 minutes
                            was_set = await set_maintenance(20)
                            if was_set:
                                await log_api_event(pool, event_type='fetch_battle_log', status_code=status, context=playertag,
                                                    message='Maintenance Break', success=False)
                            return {'status': status, 'success': False, 'reason': 'Maintenance Break'}

                        if status == 404:  # Invalid tag, or banned.
                            await log_api_event(pool, event_type='fetch_battle_log', status_code=status, context=playertag,
                                                message='Could not fetch battlelog', success=False)
                            return { 'status': status, 'success': False, 'reason': 'Battle Log Not Found' }

                        if status == 429: # Rate limit hit
                            await log_api_event(pool, event_type='fetch_battle_log', status_code=status, context=playertag, message='Rate Limit Hit', success=False)
                            print('[Battle Log] Real rate limit hit')
                            return {'status': status, 'success': False, 'reason': 'Rate Limit Hit'}

                        if status != 200:
                            print(f"⚠️ Unexpected status fetching battlelog: {status}")
                            await log_api_event(pool, event_type='fetch_battle_log', status_code=status, context=playertag,
                                                message='Unknown error', success=False)
                            return { 'status': status, 'success': False, 'reason': 'Unexpected Status' }

                        battle_log_data = await resp.json()
                        if battle_log_data:
                            # await log_api_event(pool, event_type='fetch_battle_log', status_code=status, context=playertag,
                            #                     message='Received Battle Log', success=True)
                            return battle_log_data
    except asyncio.TimeoutError:
        print(f"⏱️ Timeout fetching battle log {playertag}")
        await log_api_event(pool, event_type='fetch_battle_log', status_code=0, context=playertag,
                            message='Timeout',
                            success=False)
        return {'status': 0, 'success': False, 'reason': 'Timeout'}
    # else:
    #     print(f'[Rate Limited] Player Battle Log Fetch: {playertag}')
    #     return {'status': 429, 'success': False, 'reason': 'Rate Limit Hit'}

async def fetch_last_river_race_log(pool, clantag):
    if await is_under_maintenance():
        print("🛑 Skipping fetch — under maintenance cooldown.")
        return None

    clantag = complete_tag(clantag)
    encoded_tag = encode_tag(clantag)

    try:
        async with api_semaphore:
            async with global_limiter:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    url = f'https://proxy.royaleapi.dev/v1/clans/{encoded_tag}/riverracelog?limit=1'
                    async with session.get(url, headers=HEADERS) as resp:
                        status = resp.status

                        if status == 503:  # If maintenance break, pause all API calls for 20 minutes
                            was_set = await set_maintenance(20)
                            if was_set:
                                await log_api_event(pool, event_type='fetch_last_river_race_log', status_code=status, context=clantag,
                                                    message='Maintenance Break', success=False)
                            return {'status': status, 'success': False, 'reason': 'Maintenance Break'}

                        if status == 404:  # Invalid tag, or banned.
                            await log_api_event(pool, event_type='fetch_last_river_race_log', status_code=status, context=clantag,
                                                message='Could not fetch battlelog', success=False)
                            return { 'status': status, 'success': False, 'reason': 'River Race Log Not Found' }

                        if status == 429: # Rate limit hit
                            await log_api_event(pool, event_type='fetch_last_river_race_log', status_code=status, context=clantag, message='Rate Limit Hit', success=False)
                            print('rate limit hit')
                            return {'status': status, 'success': False, 'reason': 'Rate Limit Hit'}

                        if status != 200:
                            print(f"⚠️ Unexpected status fetching River Race Log: {status}")
                            await log_api_event(pool, event_type='fetch_last_river_race_log', status_code=status, context=clantag,
                                                message='Unknown error', success=False)
                            return { 'status': status, 'success': False, 'reason': 'Unexpected Status' }

                        river_log_data = await resp.json()
                        if river_log_data:
                            # await log_api_event(pool, event_type='fetch_last_river_race_log', status_code=status, context=clantag,
                            #                     message='Received River Race Log', success=True)
                            return river_log_data
    except asyncio.TimeoutError:
        print(f"⏱️ Timeout fetching river race log {clantag}")
        await log_api_event(pool, event_type='fetch_last_river_race_log', status_code=0, context=clantag,
                            message='Timeout',
                            success=False)
        return {'status': 0, 'success': False, 'reason': 'Timeout'}

async def check_battle_log(pool, playertag):
    battlelog = await fetch_battle_log(pool, playertag)
    # print(battlelog)
    return battlelog

async def fetch_members_in_clan(pool, clantag):
    clanData = await fetch_clan(pool, clantag)
    if not clanData:
        print('no clan data', clantag)
    members = clanData.get('memberList', [])
    return [
        {
            'playertag': member.get('tag'),
            'player_name': member.get('name')
        }
        for member in members
    ]

async def fetch_participants_in_clan(pool, clantag):
    data = await fetch_current_river_race(pool, clantag)

    # Try get data['clan'], if missing, return empty dict
    # Then try get ['participants'] from the dict, if missing, return empty list
    participants = data.get('clan', {}).get('participants', [])
    return [
        {
            'playertag': p['tag'],
            'player_name': p.get('name', 'N/A') # Default to N/A if no name
        }
            for p in participants if 'tag' in p
    ]

async def main():
    pool = await init_pool()

    clantag = '9U82JJ0Y'
    data = await fetch_participants_in_clan(pool, clantag)
    print(len(data))

    # playertag = 'P9J292JCL'
    # data = await check_battle_log(pool, playertag)
    print(data)
    # print(data['clan']['participants'])
    # clantags = ['8CYR2V', 'YC8R0RJ0']
    # tasks = []
    # task = asyncio.create_task(insert_clan(clantags, pool))
    # print(await fetch_members_in_clan(pool, clantag))
    # for tag in clantags:
    #     task = asyncio.create_task(fetch_members_in_clan(pool, tag))
    #     tasks.append(task)
    # data = await asyncio.gather(*tasks)

# if __name__ == "__main__":
#     asyncio.run(main())


# Remember to remove old api_calls

