import asyncio
import logging

from src.core.db import get_db_pool, cleanup_history, _generate_threshold_uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify")

async def verify():
    pool = await get_db_pool()
    
    # 1. Insert dummy data representing an old thread (e.g., 40 days old)
    old_uuid = _generate_threshold_uuid(40)
    old_thread_id = "test-old-thread"
    
    # Insert a newer thread (10 days old)
    new_uuid = _generate_threshold_uuid(10)
    new_thread_id = "test-new-thread"
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Clean up previous test runs if any
            await cur.execute("DELETE FROM checkpoints WHERE thread_id IN (%s, %s)", (old_thread_id, new_thread_id))
            
            # Insert old thread
            await cur.execute(
                "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint, metadata) VALUES (%s, '', %s, '{}'::jsonb, '{}'::jsonb)",
                (old_thread_id, old_uuid)
            )
            
            # Insert new thread
            await cur.execute(
                "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint, metadata) VALUES (%s, '', %s, '{}'::jsonb, '{}'::jsonb)",
                (new_thread_id, new_uuid)
            )
            
            logger.info("Inserted dummy data: 1 old thread, 1 new thread.")
            
    # 2. Run the cleanup job
    logger.info("Running cleanup_history()...")
    await cleanup_history()
    logger.info("cleanup_history() finished.")
    
    # 3. Verify the old thread was deleted, but the new one remains
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT thread_id FROM checkpoints WHERE thread_id IN (%s, %s)", (old_thread_id, new_thread_id))
            remaining = [row["thread_id"] for row in await cur.fetchall()]
            
            logger.info(f"Remaining threads after cleanup: {remaining}")
            
            if old_thread_id not in remaining and new_thread_id in remaining:
                logger.info("✅ SUCCESS: The old thread was correctly deleted, and the new thread was preserved!")
            else:
                logger.error("❌ FAILURE: The cleanup logic did not work as expected.")

if __name__ == "__main__":
    # Use standard event loop to avoid ProactorEventLoop issues if run manually
    asyncio.run(verify())
