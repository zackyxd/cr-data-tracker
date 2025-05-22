import cr_tracker.config as config
config.load_env()
import os

print("[debug] DB_USER:", os.getenv("DB_USER"))
print("[debug] DB_PASSWORD:", os.getenv("DB_PASSWORD"))
print("[debug] DB_HOST:", os.getenv("DB_HOST"))
print("[debug] DB_NAME:", os.getenv("DB_NAME"))


from cr_tracker.scripts.add_initial_players import init_players
from cr_tracker.utils.pool import init_pool

import asyncio
import datetime
import time
from cr_tracker.scripts.create_tables import create_schema # Create table

# Import scripts
from cr_tracker.scripts.track_battle_log_matches import track_battles
from cr_tracker.scripts.update_clan_info import update_all_clan_info
from cr_tracker.scripts.update_match_season_week import updateAllSeasonWeeks
from cr_tracker.scripts.update_player_weekly_stats import update_all_player_stats
from cr_tracker.scripts.track_clan_war_weeks import store_river_race_info
from cr_tracker.scripts.add_initial_clans import init_clans

# Arizona UTC-7 permanently
START_DAY = 3 # Thursday
END_DAY = 0
START_UTC_HOUR = 10
END_UTC_HOUR = 9
START_MINUTE = 5
END_MINUTE = 5

def minutes_since_week_start(day, hour, minute):
    return day * 24 * 60 + hour * 60 + minute

def is_within_war_window():
    now = datetime.datetime.now(datetime.UTC)
    current_minutes = minutes_since_week_start(now.weekday(), now.hour, now.minute)

    start_minutes = minutes_since_week_start(START_DAY, START_UTC_HOUR, START_MINUTE)
    # end_minutes = minutes_since_week_start(END_DAY, END_UTC_HOUR, END_MINUTE)
    end_minutes = minutes_since_week_start(END_DAY + 7, END_UTC_HOUR, END_MINUTE)
    return start_minutes <= current_minutes < end_minutes

async def wait_until_next_thursday():
    print("⏳ Waiting for next Thursday 2:45am MST...")
    while not is_within_war_window():
        print('Checked if Thursday...')
        await asyncio.sleep(600)  # Sleep 10 minutes
    print("▶️ War window started!")

async def main():
    pool = await init_pool()
    await create_schema()
    clan_info_list = await init_clans(pool) # Create initial clans to look players from
    await init_players(pool, clan_info_list)
    print('Added init clans/players if needed.')
    while True:
        await wait_until_next_thursday()

        while is_within_war_window():
            print('🔎 Tracking battles...')
            await track_battles(pool, False)
            await asyncio.sleep(1)
        # After war week is over:
        print('War war is over, add everything else, then wait for Thursday!')
        await track_battles(pool, True) # Check all valid players to ensure all were caught
        await update_all_clan_info(pool) # update clan trophy / clan league
        await updateAllSeasonWeeks(pool) # Update all previous matches to this current season/week
        await update_all_player_stats(pool) # Update all player stats to make opponents elo
        await store_river_race_info(pool) # Track all clan races and participants for clans at trophy limit

if __name__ == "__main__":
    asyncio.run(main())