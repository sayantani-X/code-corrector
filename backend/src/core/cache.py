import logging

import redis.asyncio as redis
from google.genai import types

from .config import settings
from .db import get_db_pool
from .llm import get_client

# Configure logging for the cache module
logger = logging.getLogger("cache")


class SemanticCache:
    """
    A hybrid semantic cache that leverages PostgreSQL (pgvector) for ultra-fast $O(log N)$
    vector similarity searches, and Redis for serving the actual cached LLM response payloads.
    This pattern ensures high performance and prevents Redis Search dependencies.
    """

    def __init__(self) -> None:
        # Initialize an asynchronous Redis client connection
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    async def _get_embedding(self, text: str) -> list[float]:
        """
        Generates a 768-dimensional text embedding for the given input text using
        Vertex AI's specialized text-embedding-004 model.
        """
        client = get_client()
        # We use the asynchronous interface (.aio) to prevent blocking the event loop
        response = await client.aio.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(
                task_type="SEMANTIC_SIMILARITY", output_dimensionality=768
            ),
        )
        if response.embeddings and response.embeddings[0].values:
            return response.embeddings[0].values
        return []

    async def get_cache_hit(self, prompt: str) -> str | None:
        """
        Checks if the provided prompt is semantically similar to a previously cached prompt.
        If the cosine similarity exceeds the threshold (e.g. 0.92), returns the cached response.
        """
        if not settings.use_semantic_cache:
            return None

        try:
            # 1. Generate the vector embedding for the incoming prompt
            vector = await self._get_embedding(prompt)

            # Format the vector as a string array for PostgreSQL pgvector insertion: '[v1, v2, ...]'
            vector_str = f"[{','.join(str(v) for v in vector)}]"

            # The <=> operator in pgvector calculates cosine distance.
            # Cosine distance = 1 - cosine similarity.
            # E.g., threshold 0.92 similarity => max distance 0.08
            max_distance = 1.0 - settings.cache_similarity_threshold

            pool = await get_db_pool()
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    # 2. Perform nearest-neighbor query using the HNSW index in PostgreSQL
                    await cur.execute(
                        """
                        SELECT id, prompt_embedding <=> %s::vector AS distance 
                        FROM semantic_cache
                        ORDER BY prompt_embedding <=> %s::vector
                        LIMIT 1;
                        """,
                        (vector_str, vector_str),
                    )

                    row = await cur.fetchone()

                    if row:
                        match_id, distance = row["id"], row["distance"]  # type: ignore

                        # 3. If the distance is within our acceptable bounds, it's a hit!
                        if distance <= max_distance:
                            logger.info(
                                f"Semantic Cache HIT! Match ID: {match_id}, Distance: {distance:.4f}"
                            )

                            # Retrieve the actual response text payload from Redis
                            redis_key = f"cache:response:{match_id}"
                            cached_response = await self.redis_client.get(redis_key)
                            if isinstance(cached_response, bytes):
                                return cached_response.decode("utf-8")
                            return cached_response

            logger.debug("Semantic Cache MISS (No matches within similarity threshold).")
            return None

        except Exception as e:
            logger.warning(f"Failed to query semantic cache: {e}")
            return None

    async def set_cache_entry(self, prompt: str, response: str) -> None:
        """
        Saves a new prompt and its generated LLM response into the hybrid cache.
        """
        if not settings.use_semantic_cache:
            return

        try:
            # 1. Compute embedding for the new prompt
            vector = await self._get_embedding(prompt)
            vector_str = f"[{','.join(str(v) for v in vector)}]"

            pool = await get_db_pool()
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    # 2. Insert or update the prompt and its embedding into PostgreSQL.
                    # We use an UPSERT (ON CONFLICT DO UPDATE) to prevent duplicates
                    # if the exact same prompt string is saved twice.
                    await cur.execute(
                        """
                        INSERT INTO semantic_cache (prompt, prompt_embedding)
                        VALUES (%s, %s::vector)
                        ON CONFLICT (prompt) DO UPDATE 
                        SET prompt_embedding = EXCLUDED.prompt_embedding
                        RETURNING id;
                        """,
                        (prompt, vector_str),
                    )
                    row = await cur.fetchone()

                    if row:
                        match_id = row["id"]  # type: ignore

                        # 3. Save the actual large text payload to Redis.
                        # We apply a 7-day TTL (Time To Live) to automatically evict stale cache entries.
                        redis_key = f"cache:response:{match_id}"
                        ttl_seconds = 7 * 24 * 60 * 60
                        await self.redis_client.set(redis_key, response, ex=ttl_seconds)
                        logger.debug(f"Saved new entry to semantic cache (Match ID: {match_id}).")

        except Exception as e:
            logger.warning(f"Failed to save entry to semantic cache: {e}")


# Export a global singleton instance of the SemanticCache
semantic_cache = SemanticCache()
