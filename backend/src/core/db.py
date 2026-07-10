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

                # Commit the schema transactions
                # (auto-committed because autocommit=True is set on the pool)
                logger.info("Database schema initialized successfully with pgvector.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
