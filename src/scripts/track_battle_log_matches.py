import asyncio
from src.sql_scripts.sql_clans import get_clan_league, get_clans, get_clan_trophy
from src.sql_scripts.sql_players import get_all_valid_players
from src.utils.pool import init_pool
from src.api_calls.cr_api import check_battle_log
from src.utils.convertBattleTime import convertBattleTime, is_in_war_window, check_current_day, get_current_war_day
from src.sql_scripts.sql_decks import insert_deck, match_exists, update_deck_stats_bulk
from src.sql_scripts.sql_clans import insert_clan, get_clans
from src.sql_scripts.sql_matches import insert_matches_bulk
from src.scripts.add_initial_clans import get_clan_info
import time
from tqdm.asyncio import tqdm_asyncio, tqdm
# import src.config as config
# config.load_env()

LOWEST_LEAGUE_TROPHIES = 3500

# Check that contains riverRacePvP, riverRaceDuel, riverRaceDuelColosseum
async def calculateMatch(pool, battle_log, existing_clans, existing_players, playertag, is_first_scan, clan_trophy_cache, clan_league_cache):
    match_rows = []
    deck_stats_updates = [] # (deck_ id, result) tuples)
    playertags_to_insert = {}  # dict of {clantag: is_tracked}
    playertags_to_update = []

    daily_battle_counts = {
        1: 0,
        2: 0,
        3: 0,
        4: 0,
    }
    updated_days = set()

    for match in battle_log:
        matchType = match.get('type')
        if matchType not in ['riverRacePvP', 'riverRaceDuel', 'riverRaceDuelColosseum']:
            # print(f'Skipping non-war type: {matchType}')
            continue

        raw_battle_time = match.get('battleTime')
        battle_time = convertBattleTime(raw_battle_time)
        if is_in_war_window(raw_battle_time) is False:
            # print('battle was outside of time')
            continue
        current_day = check_current_day(raw_battle_time)
        clantag = match.get('team')[0].get('clan').get('tag')
        t_clan_name = match.get('team')[0].get('clan').get('name')
        o_clan_name = match.get('opponent')[0].get('clan').get('name')
        t_playertag = match.get('team')[0].get('tag')
        o_playertag = match.get('opponent')[0].get('tag')
        if await match_exists(pool, t_playertag, battle_time):
            # print(f"⏩ Skipping duplicate match for {t_playertag} at {battle_time}")
            continue

        t_player = match.get('team')[0]
        o_player = match.get('opponent')[0]
        t_clantag = t_player['clan']['tag']
        o_clantag = o_player['clan']['tag']
        t_playername = t_player['name'] # Check opponent missing clan from data
        o_playername = o_player['name'] # Check opponent missing clan from data

        # If player's clantag not tracked, add it. Should always be tracked, but incase
        if t_playertag not in existing_players and t_playertag not in playertags_to_insert:
            playertags_to_insert[t_playertag] = (t_playername, True)

        # If team's clan not tracked, add it to get the league
        if t_clantag not in existing_clans:
            await insert_missing_clan(pool, t_clantag)
            existing_clans.add(t_clantag)

        # Only add opponent's clan and clantag if clan trophies >= amount wanted
        # if o_clantag not in existing_clans:
        #     await insert_missing_clan(pool, o_clantag)
        #     existing_clans.add(o_clantag)

        if o_clantag not in clan_trophy_cache:
            await insert_missing_clan(pool, o_clantag)
            # Refresh cache after insert
            row = await pool.fetchrow("SELECT clan_trophy FROM clans WHERE clantag = $1", o_clantag)
            if row:
                clan_trophy_cache[o_clantag] = row['clan_trophy']

        # clan_trophy = await get_clan_trophy(pool, o_clantag) # Get team clan's league
        # clan_league = await get_clan_league(pool, clantag)
        # clan_trophy = clan_trophy_cache.get(clantag)
        clan_league = clan_league_cache.get(clantag)
        clan_trophy = clan_trophy_cache.get(clantag)

        if clan_trophy is None:
            # Try to refetch
            row = await pool.fetchrow("SELECT clan_trophy FROM clans WHERE clantag = $1", clantag)
            if row and row['clan_trophy'] is not None:
                clan_trophy = row['clan_trophy']
                clan_trophy_cache[clantag] = clan_trophy
            else:
                print(f"⚠️ Trophies missing for clan {clantag}")
                continue  # Skip or fallback logic here

        if clan_league is None:
            # Try to refetch
            row = await pool.fetchrow("SELECT clan_league FROM clans WHERE clantag = $1", clantag)
            if row and row['clan_league'] is not None:
                clan_league = row['clan_league']
                clan_league_cache[clantag] = clan_league
            else:
                print(f"⚠️ clan_league missing for clan {clantag}")
                continue  # Skip or fallback logic here



        # Add opponent if not added yet
        if o_playertag not in existing_players and o_playertag not in playertags_to_insert:
            if clan_trophy >= LOWEST_LEAGUE_TROPHIES:
                playertags_to_insert[o_playertag] = (o_playername, True)
            else:
                playertags_to_insert[o_playertag] = (o_playername, False)
        elif o_playertag in existing_players and clan_trophy >= LOWEST_LEAGUE_TROPHIES:
            playertags_to_update.append(o_playertag)

        if matchType == 'riverRacePvP':
            result = await process_1v1_match(pool, match, t_player, t_playertag, t_clantag, t_playername, o_player, o_playertag, o_playername, clan_trophy, battle_time, current_day, is_first_scan, match_rows, deck_stats_updates, playertags_to_insert, playertags_to_update, daily_battle_counts, updated_days)
        elif matchType in ['riverRaceDuel', 'riverRaceDuelColosseum']:
            result = await process_duel_match(pool, match, t_player, t_playertag, t_clantag, t_playername, o_player, o_playertag, o_playername, clan_trophy, battle_time, current_day, is_first_scan, match_rows, deck_stats_updates, playertags_to_insert, playertags_to_update, daily_battle_counts, updated_days)

    deduped_inserts = [(tag, name, tracked) for tag, (name, tracked) in playertags_to_insert.items()]

    async with pool.acquire() as conn:
        async with conn.transaction():
            if deduped_inserts:
                await insert_bulk_players(conn, deduped_inserts)
                existing_players.update(tag for tag, _, _ in deduped_inserts)
            if is_first_scan:
                await mark_player_as_scanned(pool, playertag)

            for day in updated_days:
                await update_player_battle_count(conn, playertag, day=day, new_count=daily_battle_counts[day])

            await update_bulk_player_tracking(conn, playertags_to_update)
            await insert_matches_bulk(conn, match_rows)
            await update_deck_stats_bulk(conn, deck_stats_updates)

            # Handle overflow: If dayX has > 4 matches, shift extras to next day
            for day in updated_days:
                if daily_battle_counts[day] > 4 and day < 4:
                    overflow = daily_battle_counts[day] - 4
                    print(f"🛠 Fixing overflow of {overflow} matches for {playertag} on day {day}")

                    # Update most recent N overflow matches and move them to next day
                    await conn.execute(f"""
                        WITH to_fix AS (
                            SELECT match_id
                            FROM matches
                            WHERE playertag = $1 AND current_day = $2 AND (is_void IS DISTINCT FROM TRUE)
                            ORDER BY battle_time DESC
                            LIMIT $3
                        )
                        UPDATE matches
                        SET current_day = $4
                        WHERE match_id IN (SELECT match_id FROM to_fix)
                    """, playertag, day, overflow, day + 1)
                    print(playertag, day, overflow, day + 1)
                    print(f"✅ Shifted {overflow} matches from day {day} to day {day + 1} for {playertag}")

                    # Update battle_counts accordingly
                    await update_player_battle_count(conn, playertag, day=day, new_count=4)
                    await update_player_battle_count(conn, playertag, day=day + 1,
                                                     new_count=daily_battle_counts.get(day + 1, 0) + overflow)
                elif daily_battle_counts[day] > 4 and day == 4:
                    overflow = daily_battle_counts[day] - 4
                    print(f"🛠 Fixing overflow of {overflow} matches for {playertag} on day {day}. Moving them back to day 3")

                    # Update most recent N overflow matches and move them to next day
                    await conn.execute(f"""
                                            WITH to_fix AS (
                                                SELECT match_id
                                                FROM matches
                                                WHERE playertag = $1 AND current_day = $2 AND is_void = False AND season IS NULL
                                                ORDER BY battle_time ASC
                                                LIMIT $3
                                            )
                                            UPDATE matches
                                            SET current_day = $4
                                            WHERE match_id IN (SELECT match_id FROM to_fix)
                                        """, playertag, day, overflow, day - 1)
                    print(playertag, day, overflow, day + 1)
                    print(f"✅ Shifted {overflow} matches from day {day} to day {day - 1} for {playertag}")

                    # Update battle_counts accordingly
                    await update_player_battle_count(conn, playertag, day=day, new_count=4)
                    await update_player_battle_count(conn, playertag, day=day - 1,
                                                     new_count=daily_battle_counts.get(day - 1, 0) + overflow)


async def process_1v1_match(pool, match, t_player, t_playertag, t_clantag, t_playername, o_player, o_playertag, o_playername, clan_league, battle_time, current_day, is_first_scan, match_rows, deck_stats_updates, playertags_to_insert, playertags_to_update, daily_battle_counts, updated_days):
    battleType = '1v1'
    # Grab single decks and evos
    t_deck, t_evos = grabDeck(match.get('team')[0].get('cards'))
    o_deck, o_evos = grabDeck(match.get('opponent')[0].get('cards'))

    # Insert both decks (if not already existing)
    t_deck_id = await insert_deck(pool, {'deck': t_deck, 'evolutions': t_evos})
    o_deck_id = await insert_deck(pool, {'deck': o_deck, 'evolutions': o_evos})

    # Wrap in fake "rounds" for consistent printing

    t_decks = [{"deck": t_deck, "evolutions": t_evos}]

    t_result = calculate1v1Result(match.get('team')[0], match.get('opponent')[0])
    t_match_result = list(zip(t_result, t_decks))

    for i, (match_data, deck_data) in enumerate(t_match_result):
        # deck_id = await insert_deck(pool, deck_data)
        # Example for 1v1
        match_rows.append((
            t_clantag,
            t_playername,
            o_playername,
            t_playertag,
            o_playertag,
            t_deck_id,
            o_deck_id,
            [c['card_level'] for c in t_deck],
            [c['card_level'] for c in o_deck],
            battleType,
            None,  # duel_round is None for 1v1
            match_data['result'],
            clan_league,
            match_data['elixir_leaked'],
            battle_time,
            None,
            None,
            current_day,
            is_first_scan
        ))

        if not is_first_scan:
            daily_battle_counts[current_day] += 1
            updated_days.add(current_day)

        deck_stats_updates.append((t_deck_id, match_data['result']))

    return match_rows, deck_stats_updates, playertags_to_insert, playertags_to_update, updated_days

async def process_duel_match(pool, match, t_player, t_playertag, t_clantag, t_playername, o_player, o_playertag, o_playername, clan_league, battle_time, current_day, is_first_scan, match_rows, deck_stats_updates, playertags_to_insert, playertags_to_update, daily_battle_counts, updated_days):
    battleType = 'Duel'

    t_rounds = match.get('team')[0].get('rounds')  # get the rounds played
    o_rounds = match.get('opponent')[0].get('rounds')  # get the rounds played

    t_duel_decks = grabDuelDecks(t_rounds)  # grab the duel decks
    o_duel_decks = grabDuelDecks(o_rounds)  # grab the duel decks

    t_results = calculateDuelResult(t_rounds, o_rounds)  # Calculate each game if it was win/loss
    o_results = calculateDuelResult(o_rounds, t_rounds)  # Calculate each game if it was win/loss

    t_matches = list(zip(t_results, t_duel_decks))  # Combine decks with result
    o_matches = list(zip(o_results, o_duel_decks))  # Combine decks with result

    # Insert each round
    for round_idx, ((t_match, t_deck), (o_match, o_deck)) in enumerate(zip(t_matches, o_matches)):
        # Insert deck (deduplicated)
        t_deck_id = await insert_deck(pool, t_deck)
        o_deck_id = await insert_deck(pool, o_deck)

        # Example for duel round
        match_rows.append((
            t_clantag,
            t_playername,
            o_playername,
            t_playertag,
            o_playertag,
            t_deck_id,
            o_deck_id,
            [c['card_level'] for c in t_deck['deck']],
            [c['card_level'] for c in o_deck['deck']],
            battleType,
            round_idx + 1,
            t_match['result'],
            clan_league,
            t_match['elixir_leaked'],
            battle_time,
            None,
            None,
            current_day,
            is_first_scan
        ))

        if not is_first_scan:
            daily_battle_counts[current_day] += 1
            updated_days.add(current_day)

        deck_stats_updates.append((t_deck_id, t_match['result']))

    return match_rows, deck_stats_updates, playertags_to_insert, playertags_to_update, updated_days


def grabDeck(deck):
    whole_deck = []
    evos = []

    for i, card in enumerate(deck):
        card_data = {
            'card_name': card.get('name'),
            'card_level': getCardLevel(card.get('rarity'), card.get('level'))
        }
        whole_deck.append(card_data)

        if i < 2 and card.get('maxEvolutionLevel') == 1:
            evos.append(card_data)
    sorted_whole_deck = sorted(whole_deck, key=lambda c: c['card_name'])
    sorted_evos = sorted(evos, key=lambda c: c['card_name'])
    return sorted_whole_deck, sorted_evos

def grabDuelDecks(rounds):
    all_decks = []
    for round in rounds:
        deck_cards = round.get("cards", [])
        deck, evos = grabDeck(deck_cards)
        all_decks.append({
            "deck": deck,
            "evolutions": evos
        })
    return all_decks

# Calculate if win, loss, tie
def calculate1v1Result(t, o): # t_round =
    result = None # Start as None to make sure it gets set
    t_crowns = t.get('crowns')
    o_crowns = o.get('crowns')
    t_elixir_leaked = t.get('elixirLeaked')
    o_elixir_leaked = o.get('elixirLeaked')
    if t_crowns > o_crowns:
        result = 'win'
    elif t_crowns < o_crowns:
        result = 'loss'

    t_pt = t.get('princessTowersHitPoints') or [] # Array for princess towers
    o_pt = o.get('princessTowersHitPoints') or [] # Array for princess towers

    if sorted(t_pt) == sorted(o_pt):
        result = 'tie'
    elif t_elixir_leaked - o_elixir_leaked >= 9 and sum(o_pt) > 8000 and result == 'loss':
        result = 'throw'
    elif len(t_pt) == len(o_pt) and min(t_pt) == min(o_pt):
        result = 'tie'
    elif result is None:
        result = 'unknown'
        t_elixir_leaked = 0

    return [{
        'result': result,
        'elixir_leaked': round(t_elixir_leaked, 2)
    }]

def calculateDuelResult(t_round, o_round):
    results = []
    # Enumerate starts at 0 to account for the rounds
    for i, (t_round, o_round) in enumerate(zip(t_round, o_round)):
        t_crowns = t_round.get('crowns')
        o_crowns = o_round.get('crowns')
        if t_crowns > o_crowns:
            result = 'win'
        elif t_crowns < o_crowns:
            result = 'loss'
        else:
            # Fallback to princess tower damage if needed
            t_pt = t_round.get('princessTowersHitPoints') or []
            o_pt = o_round.get('princessTowersHitPoints') or []
            if t_pt == o_pt:
                result = 'tie'
            else:
                print('result was unknown?', t_round, o_round)
                result = 'unknown'

        t_elixir_leak = t_round.get('elixirLeaked')
        o_elixir_leak = o_round.get('elixirLeaked')
        # cards_not_used = sum(1 for card in t_round.get('cards') if not card.get('used', False)) # If card_used = False
        cards_used = sum(1 for card in t_round.get('cards') if card.get('used', True)) # If card_used = True
        if cards_used <= 3 and result == 'loss':
            result = 'throw'
        elif 6 <= cards_used <= 8 and result == 'loss':
            result = 'loss' # If 6+ cards were used, you lost
        elif t_elixir_leak - o_elixir_leak >= 9 and result == 'loss' and cards_used <= 5:
            result = 'throw' # If you used less than 5 cards and leaked 10+ elixir, you likely threw
        elif t_elixir_leak - o_elixir_leak >= 7 and result == 'loss' and cards_used <= 5 and i >= 1:
            result = 'throw'
        # else:
        #     result = 'loss'

        results.append({
            'result': result,
            'elixir_leaked': round(t_round.get('elixirLeaked', 0), 2),
        })

    return results


async def insert_missing_clan(pool, clantag):
    try:
        clan_info_list = await get_clan_info(pool, clantag)
        if clan_info_list is not None:
            await insert_clan(pool, clan_info_list)
        return 'Inserted clan!'
    except TypeError:
        print('Error with this clan for clan war trophy clip:', clantag)
        return None

def getCardLevel(rarityType, level):
    rarity = {'common': level, 'rare': level+2, 'epic': level+5, 'legendary': level+8, 'champion': level+10}
    return rarity[rarityType]

# async def main():
#     pool = await init_pool()
#     playersCount = await get_players_count(pool)
#     print('Checking', playersCount, 'players')
#     # players = [{ 'clantag': 'P9R0U8JJR'}]
#     # players = [{ 'clantag': 'UL2020PVL'}]
#
#     # Set a semaphore to limit concurrency (respect API rate limits!)
#     semaphore = asyncio.Semaphore(50)  # adjust as needed (10 concurrent)
#
#     current_day = get_current_war_day()
#     print(current_day)
#     players = await get_all_players(pool, current_day)
#     # players = await get_player(pool, '#LL9P0JVVU', current_day)
#     existing_players = set(p['playertag'] for p in players)
#     # Instead of just playertags, keep a dict mapping tag to scan status
#     player_scan_status = {
#         p['playertag']: {
#             'has_been_scanned': p['has_been_scanned'],
#             f'day{current_day}_battles': p[f'day{current_day}_battles']
#         }
#         for p in players
#     }
#     # existing_players = set(players)
#     existing_clans = set(await get_clans(pool))
#
#
#     async def process_player(player):
#         playertag = player['playertag']
#         async with semaphore:
#             battlelog = await check_battle_log(pool, playertag)
#             if battlelog and isinstance(battlelog, list):
#                 is_first_scan = not player_scan_status.get(playertag, {}).get("has_been_scanned", False)
#                 await calculateMatch(pool, battlelog, existing_clans, existing_players, playertag, is_first_scan)
#                 await update_player_last_checked(pool, playertag) # Update that player was checked
#             else:
#                 tqdm.write(f" ⚠️ Skipping {playertag} — no valid battle log")
#     start = time.time()
#     await tqdm_asyncio.gather(*[process_player(player) for player in players])
#
#     # Create and gather tasks
#     # tasks = [process_player(player) for player in players]
#     # await asyncio.gather(*tasks, return_exceptions=True)
#     # for result in tasks:
#     #     if isinstance(result, Exception):
#     #         print("⚠️ Task failed:", result)
#
#     print(f"Took {time.time() - start:.2f}s to do all logs for {playersCount} players\n")

async def track_battles(pool, all):
    semaphore = asyncio.Semaphore(30)  # adjust as needed (10 concurrent)
    current_day = get_current_war_day() # Get current day to check for 4 battles
    print('The current day is:', current_day)
    if all:
        players = await get_all_valid_players(pool, current_day) # Get ALL players, run this on last iteration
        forWho = 'For All'
    else:
        players = await get_valid_players(pool, current_day)
        forWho = 'For Set'
    playersCount = len(players)
    existing_players = set(p['playertag'] for p in players)
    player_scan_status = { # This is how 4 battles is checked
        p['playertag']: {
            'has_been_scanned': p['has_been_scanned'],
            f'day{current_day}_battles': p[f'day{current_day}_battles']
        }
        for p in players
    }

    # Preload clan trophies into cache
    clan_trophy_cache = {}
    rows = await pool.fetch("SELECT clantag, clan_trophy FROM clans WHERE clan_trophy IS NOT NULL")
    clan_trophy_cache = {row['clantag']: row['clan_trophy'] for row in rows}

    clan_league_cache = {}
    rows = await pool.fetch("SELECT clantag, clan_league FROM clans WHERE clan_league IS NOT NULL")
    clan_league_cache = {row['clantag']: row['clan_league'] for row in rows}

    existing_clans = set(await get_clans(pool)) # Create set of all current clans
    processed = 0
    skipped = 0
    update_batch = 50
    completed_since_last_update = 0
    progress = tqdm(players, desc=f'⚔️ Tracking Battles {forWho}', dynamic_ncols=True, leave=False)
    async def process_player(player):
        nonlocal processed, skipped, completed_since_last_update
        playertag = player['playertag']
        async with semaphore:
            battlelog = await check_battle_log(pool, playertag)
            if battlelog and isinstance(battlelog, list):
                is_first_scan = not player_scan_status.get(playertag, {}).get("has_been_scanned", False)
                await calculateMatch(pool, battlelog, existing_clans, existing_players, playertag, is_first_scan, clan_trophy_cache, clan_league_cache)
                await update_player_last_checked(pool, playertag) # Update that player was checked
                processed += 1
            else:
                skipped += 1
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
    print(f"Took {time.time() - start:.2f}s to do all battle logs")


# Get only valid players and limit it. Check within 2 hours
async def get_valid_players(pool, current_day):
    column = f"day{current_day}_battles"
    query = f"""
        SELECT * FROM players
        WHERE is_tracked = TRUE
        AND COALESCE({column}, 0) < 4
        AND (last_checked <= NOW() - INTERVAL '2 hours' OR last_checked IS NULL)
        LIMIT 5000
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query)


# Insert all players from matches at once
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

# First time iterating through a player, void all those matches as they may be inaccurate.
async def mark_player_as_scanned(conn, playertag):
    await conn.execute(
        "UPDATE players SET has_been_scanned = TRUE WHERE playertag = $1", playertag
    )

# Set players to be checked in future if they are valid (in the clan trophy range wanted)
async def update_bulk_player_tracking(conn, playertags):
    if not playertags:
        return
    await conn.executemany("""
        UPDATE players
        SET is_tracked = TRUE
        WHERE playertag = $1
    """, [(tag,) for tag in playertags])

# Update a players battle count. Used to check if they have 4 battles.
async def update_player_battle_count(conn, playertag, day, new_count):
    col = f"day{day}_battles"
    await conn.execute(f"""
        UPDATE players
        SET {col} = $1
        WHERE playertag = $2
    """, new_count, playertag)

# Update the last time a player was checked to not check too frequently.
async def update_player_last_checked(pool, playertag):
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE players
        SET last_checked = NOW()
        WHERE playertag = $1
        """, playertag)



# if __name__ == "__main__":
#     asyncio.run(main())