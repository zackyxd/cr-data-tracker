import time
import asyncpg
from collections import Counter, defaultdict


async def insert_deck(pool, deck_data):
    # start = time.perf_counter()
    # signature = generate_deck_signature(deck_data)
    cards, evos = generate_deck_signature(deck_data)
    # print(signature)
    async with pool.acquire() as conn:
        # Check if deck already exists
        existing = await conn.fetchval("""
            SELECT deck_id FROM deck_signatures 
            WHERE cards = $1 AND evolutions = $2
        """, cards, evos)

        if existing:
            return existing

        # Insert into decks
        new_deck_id = await conn.fetchval("""
            INSERT INTO decks DEFAULT VALUES
            RETURNING deck_id
        """)

        # Insert deck signature
        await conn.execute("""
            INSERT INTO deck_signatures (deck_id, cards, evolutions)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, new_deck_id, cards, evos)

        return new_deck_id


def generate_deck_signature(deck_data):
    # cards = sorted(f"{c['card_name']}" for c in deck_data['deck'])
    # evos = sorted(e['card_name'] for e in deck_data['evolutions'])
    cards = [c['card_name'] for c in deck_data['deck']]
    evos = [e['card_name'] for e in deck_data['evolutions']]
    return cards, evos

async def insert_match(pool, playertag, opponent_tag, player_deck_id, opponent_deck_id, battle_type, duel_round, result, clan_league, elixir_leaked, battle_time, season=None, week=None, current_day = None):
    # start = time.perf_counter()
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO matches (
            clantag, opponent_playertag, player_deck_id, opponent_deck_id, battle_type, duel_round, match_result, clan_league, elixir_leaked, battle_time, season, week, current_day
            ) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (clantag, battle_time, duel_round) DO NOTHING
        """, playertag, opponent_tag, player_deck_id, opponent_deck_id,
             battle_type, duel_round, result, clan_league, elixir_leaked, battle_time,
             season, week, current_day)
        # print(f'[Timing] Inserting single match took {time.perf_counter() - start:.3f}s')

async def update_deck_stats(pool, deck_id, result):
    # start = time.perf_counter()
    column_map = {
        'win': 'deck_wins',
        'loss': 'deck_losses',
        'tie': 'deck_ties',
        'throw': 'deck_throws',
    }
    column = column_map.get(result.lower())
    if not column:
        print(f"[WARN] Unknown match result: {result}, {deck_id}")
        return

    async with pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE decks
            SET {column} = {column} + 1,
                deck_count = deck_count + 1
                WHERE deck_id = $1""", deck_id)
    # print(f'[Timing] Updating deck stats took {time.perf_counter() - start:.3f}s')

async def update_deck_stats_bulk(conn, updates):
    # start = time.perf_counter()

    if not updates:
        return

    # Group and aggregate results
    deck_counts = defaultdict(Counter)

    for deck_id, result in updates:
        result = result.lower()
        if result == 'win':
            deck_counts[deck_id]['deck_wins'] += 1
        elif result == 'loss':
            deck_counts[deck_id]['deck_losses'] += 1
        elif result == 'tie':
            deck_counts[deck_id]['deck_ties'] += 1
        elif result == 'throw':
            deck_counts[deck_id]['deck_throws'] += 1

        deck_counts[deck_id]['deck_count'] += 1

    # Update all affected deck_ids
    for deck_id, counts in deck_counts.items():
        await conn.execute("""
            UPDATE decks
            SET
                deck_wins = deck_wins + $1,
                deck_losses = deck_losses + $2,
                deck_ties = deck_ties + $3,
                deck_throws = deck_throws + $4,
                deck_count = deck_count + $5
            WHERE deck_id = $6
        """,
            counts['deck_wins'],
            counts['deck_losses'],
            counts['deck_ties'],
            counts['deck_throws'],
            counts['deck_count'],
            deck_id)
    # print(f'[Timing] Updating bulk deck stats took {time.perf_counter() - start:.3f}s')


async def match_exists(pool, playertag, battle_time):
    start = time.perf_counter()
    async with pool.acquire() as conn:
        row = await conn.fetchval("""
            SELECT 1 FROM matches
            WHERE playertag = $1 AND battle_time = $2
            LIMIT 1
        """, playertag, battle_time)
        return row is not None