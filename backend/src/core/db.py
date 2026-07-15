import logging
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import settings

logger = logging.getLogger("db")

# Global async connection pool instance
_pool: Any = None


async def get_db_pool() -> Any:
    """
    Returns the global asynchronous database connection pool.
    Initializes the pool and the database schema if it hasn't been created yet.
    """
    global _pool
    if _pool is None:
        # Create an async pool. 'open=False' delays opening connections until we explicitly call .open()
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        await _pool.open()
        await _init_db()
    return _pool


async def close_db() -> None:
    """
    Gracefully closes the global asynchronous database connection pool.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def _init_db() -> None:
    """
    Initializes the database schema for the semantic cache using pgvector.
    Creates the required extension, tables, and the HNSW index for ultra-fast vector search.
    """
    global _pool
    if _pool is None:
        return

    try:
        # We acquire a connection from the pool to run schema migrations
        async with _pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Ensure the pgvector extension is available in the database
                await cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # 2. Create the hybrid semantic cache table
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS semantic_cache (
                        id BIGSERIAL PRIMARY KEY,
                        prompt TEXT UNIQUE NOT NULL,
                        prompt_embedding vector(768) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 3. Create an HNSW index for $O(\log N)$ similarity searches using Cosine Distance
                # We specify 'vector_cosine_ops' because we use the `<=>` operator
                await cur.execute("""
                    CREATE INDEX IF NOT EXISTS semantic_cache_embedding_idx
                    ON semantic_cache USING hnsw (prompt_embedding vector_cosine_ops);
                """)

                logger.info("Database schema initialized successfully with pgvector.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")


def _generate_threshold_uuid(days_ago: int) -> str:
    """Generates a UUIDv6 string corresponding to the timestamp of 'days_ago'."""
    import time
    timestamp_s = time.time() - (days_ago * 24 * 60 * 60)
    timestamp_100ns = int(timestamp_s * 1e7) + 122192928000000000
    time_high = (timestamp_100ns >> 28) & 0xFFFFFFFF
    time_mid = (timestamp_100ns >> 12) & 0xFFFF
    time_low_and_version = (timestamp_100ns & 0xFFF) | 0x6000
    return f"{time_high:08x}-{time_mid:04x}-{time_low_and_version:04x}-0000-000000000000"


async def cleanup_history() -> None:
    """
    Implements a hybrid cleanup policy for the LangGraph state history.
    1. Time-based: Deletes all threads older than settings.history_retention_days.
    2. Size-based: If the database is > settings.history_max_size_mb, iteratively deletes
       the oldest threads until size is within limits.
    """
    pool = await get_db_pool()

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Time-based Pruning
                threshold_uuid = _generate_threshold_uuid(settings.history_retention_days)
                
                # Using a CTE to identify threads whose most recent checkpoint is older than the threshold
                time_delete_query = """
                    WITH old_threads AS (
                        SELECT thread_id FROM checkpoints 
                        GROUP BY thread_id 
                        HAVING MAX(checkpoint_id) < %s
                    ),
                    del_blobs AS (DELETE FROM checkpoint_blobs WHERE thread_id IN (SELECT thread_id FROM old_threads)),
                    del_writes AS (DELETE FROM checkpoint_writes WHERE thread_id IN (SELECT thread_id FROM old_threads))
                    DELETE FROM checkpoints WHERE thread_id IN (SELECT thread_id FROM old_threads)
                    RETURNING thread_id;
                """
                await cur.execute(time_delete_query, (threshold_uuid,))
                deleted_rows = cur.rowcount
                if deleted_rows > 0:
                    logger.info(f"[Cleanup] Pruned {deleted_rows} threads older than {settings.history_retention_days} days.")

                # 2. Size-based Pruning
                # Calculate total size of the 3 langgraph tables in MB
                size_query = """
                    SELECT (
                        COALESCE(pg_total_relation_size('checkpoints'), 0) + 
                        COALESCE(pg_total_relation_size('checkpoint_blobs'), 0) + 
                        COALESCE(pg_total_relation_size('checkpoint_writes'), 0)
                    ) / (1024.0 * 1024.0) AS total_mb;
                """
                
                size_delete_query = """
                    WITH oldest_threads AS (
                        SELECT thread_id FROM checkpoints 
                        GROUP BY thread_id 
                        ORDER BY MAX(checkpoint_id) ASC 
                        LIMIT 50
                    ),
                    del_blobs AS (DELETE FROM checkpoint_blobs WHERE thread_id IN (SELECT thread_id FROM oldest_threads)),
                    del_writes AS (DELETE FROM checkpoint_writes WHERE thread_id IN (SELECT thread_id FROM oldest_threads))
                    DELETE FROM checkpoints WHERE thread_id IN (SELECT thread_id FROM oldest_threads)
                    RETURNING thread_id;
                """

                # Loop to delete oldest threads 50 at a time until we drop below the threshold
                max_iterations = 20 # Safety net
                for _ in range(max_iterations):
                    try:
                        await cur.execute(size_query)
                        row = await cur.fetchone()
                        if row is None:
                            break
                        total_mb = float(row["total_mb"])
                    except Exception:
                        # Tables might not exist yet if empty DB
                        break
                        
                    if total_mb <= settings.history_max_size_mb:
                        break
                        
                    logger.info(f"[Cleanup] DB size {total_mb:.2f} MB exceeds {settings.history_max_size_mb} MB limit. Pruning oldest threads...")
                    await cur.execute(size_delete_query)
                    if cur.rowcount == 0:
                        break # Nothing left to delete

    except Exception as e:
        logger.warning(f"Failed to execute background history cleanup: {e}")
