import asyncio
from datetime import datetime, timedelta, timezone

# Global maintenance hold (shared memory)
MAINTENANCE_UNTIL = None
MAINTENANCE_LOCK = asyncio.Lock()

async def is_under_maintenance() -> bool:
    async with MAINTENANCE_LOCK:
        if MAINTENANCE_UNTIL is None:
            return False
        return datetime.now(timezone.utc) < MAINTENANCE_UNTIL

async def set_maintenance(minutes: int = 20):
    global MAINTENANCE_UNTIL
    async with MAINTENANCE_LOCK:
        now = datetime.now(timezone.utc)
        if MAINTENANCE_UNTIL and now < MAINTENANCE_UNTIL:
            return False # already under maintenance

        # Newly set
        MAINTENANCE_UNTIL = now + timedelta(minutes=minutes)
        print(f"🚧 Maintenance detected — pausing all API calls until {MAINTENANCE_UNTIL}")
        return True