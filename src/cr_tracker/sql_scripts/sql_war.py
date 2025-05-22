
async def insert_clan_stats_bulk(conn, clan_stat_rows):
    if not clan_stat_rows:
        return

    await conn.executemany("""
    INSERT INTO clan_war_stats (
    clantag, clan_name, season, week, clan_league, placement, clan_fame,
    wins, losses, throws, participants
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    ON CONFLICT (clantag, season, week) DO NOTHING
    """, clan_stat_rows)

async def insert_player_weekly_fame_bulk(conn, player_stat_rows):
    if not player_stat_rows:
        return
    await conn.executemany("""
    INSERT INTO player_weekly_fame (
    season, week, playertag, clantag, clan_league, player_fame, 
    decks_used, throws
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (playertag, clantag, clan_league, season, week) DO NOTHING
    """, player_stat_rows)