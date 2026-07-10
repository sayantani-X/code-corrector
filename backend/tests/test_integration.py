import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.core.db import close_db
from src.graph.graph import get_app


@patch("src.core.llm.generate_content_with_retry_async", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_graph_persistence_integration(mock_generate: AsyncMock) -> None:
    """
    Integration test to verify that the LangGraph state is properly saved
    to the PostgreSQL database using AsyncPostgresSaver and can be resumed.
    """
    mock_generate.return_value = (
        '{"steps": ["Step 1"], "entry_point": "main.py"}'
    )

    app = await get_app()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    initial_state = {
        "task": "Test persistence",
    }

    try:
        # Run the app until it reaches the first node (planner)
        # We invoke it with the initial state
        result = await app.ainvoke(initial_state, config=config)

        # Retrieve the persisted state using the same thread_id config
        retrieved_state_tuple = await app.checkpointer.aget_tuple(config)
        assert retrieved_state_tuple is not None, "Failed to retrieve the saved state checkpoint"

        channel_values = retrieved_state_tuple.checkpoint["channel_values"]
        assert "plan" in channel_values
        assert channel_values["entry_point"] == "main.py"

    finally:
        # Always close the connection pool to prevent hanging tests
        await close_db()
