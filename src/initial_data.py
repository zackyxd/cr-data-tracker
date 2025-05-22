import src.config as config
config.load_env()
from src.scripts.add_initial_players import init_players
from src.utils.pool import init_pool

import asyncio
import datetime
import time
from src.scripts.create_tables import create_schema # Create table

# Import scripts
from src.scripts.track_battle_log_matches import track_battles

async def main():
    pool = await init_pool()

    for i in range (5):
        print('🔎 Tracking battles...')
        await track_battles(pool, False)
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())