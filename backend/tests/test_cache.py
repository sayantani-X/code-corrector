from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cache import semantic_cache


@pytest.fixture
def mock_dependencies():
    """
    Fixture to mock all external dependencies (Vertex AI, Postgres Pool, Redis)
    required for the SemanticCache unit tests.
    """
    with (
        patch("src.core.cache.SemanticCache._get_embedding", new_callable=AsyncMock) as mock_get_embedding,
        patch("src.core.cache.get_db_pool") as mock_db_pool,
        patch("src.core.cache.settings") as mock_settings,
    ):
        # Enable caching in settings
        mock_settings.use_semantic_cache = True
        mock_settings.cache_similarity_threshold = 0.92

        # 1. Mock the embedding return
        mock_get_embedding.return_value = [0.1] * 768

        # 2. Mock the Async PostgreSQL Connection Pool (psycopg)
        mock_cur = AsyncMock()

        class MockCursorContext:
            async def __aenter__(self):
                return mock_cur

            async def __aexit__(self, *args):
                pass

        class MockConnectionContext:
            def cursor(self):
                return MockCursorContext()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        mock_pool = MagicMock()
        mock_pool.connection.return_value = MockConnectionContext()

        # mock_db_pool is a coroutine returning mock_pool
        mock_db_pool.return_value = mock_pool

        # 3. Mock the Redis Async Client
        semantic_cache.redis_client = AsyncMock()

        yield {"get_embedding": mock_get_embedding, "cur": mock_cur, "redis": semantic_cache.redis_client}


@pytest.mark.asyncio
async def test_get_cache_miss(mock_dependencies) -> None:
    """
    Test scenario where the pgvector database returns no similar match.
    """
    mock_dependencies["cur"].fetchone.return_value = None

    result = await semantic_cache.get_cache_hit("Test prompt miss")

    assert result is None
    mock_dependencies["cur"].execute.assert_called_once()
    mock_dependencies["redis"].get.assert_not_called()


@pytest.mark.asyncio
async def test_get_cache_hit(mock_dependencies) -> None:
    """
    Test scenario where pgvector finds a match within the similarity threshold,
    and Redis successfully returns the cached string payload.
    """
    # Simulate a database row with distance 0.01 (which is <= max distance 0.08)
    mock_dependencies["cur"].fetchone.return_value = {"id": 123, "distance": 0.01}
    mock_dependencies["redis"].get.return_value = "Cached LLM Response"

    result = await semantic_cache.get_cache_hit("Test prompt hit")

    assert result == "Cached LLM Response"
    mock_dependencies["cur"].execute.assert_called_once()
    mock_dependencies["redis"].get.assert_called_once_with("cache:response:123")


@pytest.mark.asyncio
async def test_get_cache_hit_distance_too_far(mock_dependencies) -> None:
    """
    Test scenario where pgvector finds a nearest neighbor, but the distance
    is too large (i.e. below the similarity threshold of 0.92 -> max distance 0.08).
    """
    # Simulate a database row with distance 0.15 (which is > max distance 0.08)
    mock_dependencies["cur"].fetchone.return_value = {"id": 124, "distance": 0.15}

    result = await semantic_cache.get_cache_hit("Test prompt too far")

    assert result is None
    mock_dependencies["cur"].execute.assert_called_once()
    mock_dependencies["redis"].get.assert_not_called()


@pytest.mark.asyncio
async def test_set_cache_entry(mock_dependencies) -> None:
    """
    Test scenario where a new LLM generation is saved to the Postgres database
    and the text payload is cached in Redis with a TTL.
    """
    mock_dependencies["cur"].fetchone.return_value = {"id": 456}

    await semantic_cache.set_cache_entry("Test prompt to save", "New generated response")

    mock_dependencies["cur"].execute.assert_called_once()
    # Ensure Redis was called with the correct ID and TTL
    mock_dependencies["redis"].set.assert_called_once_with(
        "cache:response:456", "New generated response", ex=7 * 24 * 60 * 60
    )
