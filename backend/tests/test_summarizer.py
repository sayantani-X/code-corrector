from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.state import AgentState
from src.graph.summarizer import summarizer_node


@pytest.fixture
def mock_dependencies():
    """
    Fixture to mock the Google GenAI Client and settings for testing
    the LogSummarizer node.
    """
    with (
        patch("src.graph.summarizer.get_client") as mock_client_factory,
        patch("src.graph.summarizer.settings") as mock_settings,
    ):
        # Set a low threshold for easy testing
        mock_settings.summarizer_token_threshold = 100
        mock_settings.gemini_flash_model = "test-flash"

        mock_client = MagicMock()
        mock_aio = AsyncMock()

        # Mock token counting
        mock_token_response = MagicMock()
        mock_token_response.total_tokens = 50  # Default to under limit
        mock_aio.models.count_tokens.return_value = mock_token_response

        # Mock summary generation
        mock_generate_response = MagicMock()
        mock_generate_response.text = "Mocked concise summary bullet points."
        mock_aio.models.generate_content.return_value = mock_generate_response

        mock_client.aio = mock_aio
        mock_client_factory.return_value = mock_client

        yield {"client": mock_client, "token_response": mock_token_response}


@pytest.mark.asyncio
async def test_summarizer_node_under_limit(mock_dependencies) -> None:
    """
    Tests that if the logs are under the token threshold, the summarizer does not
    call the LLM to generate a summary and returns empty strings.
    """
    state: AgentState = {
        "task": "",
        "plan": [],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "",
        "exit_code": 0,
        "retry_count": 0,
        "max_retries": 5,
        "stderr": "Small error log",
        "review_comments": "Small lint warning",
    }

    result = await summarizer_node(state)

    assert result["stderr_summary"] == ""
    assert result["review_summary"] == ""
    # Should only count tokens, not generate content
    mock_dependencies["client"].aio.models.generate_content.assert_not_called()
    assert mock_dependencies["client"].aio.models.count_tokens.call_count == 2


@pytest.mark.asyncio
async def test_summarizer_node_over_limit(mock_dependencies) -> None:
    """
    Tests that if the logs exceed the token threshold, the summarizer calls the LLM
    to generate concise summaries.
    """
    # Force the token count to exceed the limit (100)
    mock_dependencies["token_response"].total_tokens = 150

    state = {
        "stderr": "Massive error log from a gigantic traceback...",
        "review_comments": "Hundreds of lines of ruff/bandit warnings...",
    }

    result = await summarizer_node(state)

    assert result["stderr_summary"] == "Mocked concise summary bullet points."
    assert result["review_summary"] == "Mocked concise summary bullet points."
    # Should count tokens AND generate content for both fields
    assert mock_dependencies["client"].aio.models.generate_content.call_count == 2
