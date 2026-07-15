import asyncio
import logging

from src.core.db import get_db_pool, cleanup_history, close_db
from src.core.config import settings

logging.basicConfig(level=logging.INFO)

async def test():
    print(f"Current limits: retention={settings.history_retention_days} days, max_size={settings.history_max_size_mb} MB")
    
    # Initialize the database pool so `_pool` in db.py is populated
    await get_db_pool()
    
    print("Running cleanup_history()...")
    await cleanup_history()
    print("cleanup_history() finished.")
    
    await close_db()

if __name__ == "__main__":
    asyncio.run(test())
