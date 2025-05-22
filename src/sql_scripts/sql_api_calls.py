async def log_api_event(pool, event_type, status_code, context, message, success):
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO logs (event_type, status_code, message, success, context)
        VALUES ($1, $2, $3, $4, $5)
        """, event_type, status_code, message, success, context)
