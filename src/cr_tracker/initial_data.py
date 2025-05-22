import cr_tracker.config as config
config.load_env()
from cr_tracker.scripts.add_initial_players import init_players
from cr_tracker.utils.pool import init_pool

import asyncio
import datetime
import time
from cr_tracker.scripts.create_tables import create_schema # Create table

# Import scripts
from cr_tracker.scripts.track_battle_log_matches import track_battles

async def main():
    pool = await init_pool()

    for i in range (5):
        print('🔎 Tracking battles...')
        await track_battles(pool, False)
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())