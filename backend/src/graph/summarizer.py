from typing import Any

from src.core.config import settings
from src.core.llm import get_client
from src.domain.state import AgentState


async def summarizer_node(state: AgentState) -> dict[str, Any]:
    """
    LogSummarizer Node:
    Checks if the standard error or review comments are excessively large.
    If the content exceeds the configured token threshold, it uses Gemini Flash
    to condense the tracebacks into a concise explanation, preserving context window limits.
    """
    client = get_client()

    stderr_content = state.get("stderr", "").strip()
    review_content = state.get("review_comments", "").strip()

    stderr_summary = state.get("stderr_summary", "")
    review_summary = state.get("review_summary", "")

    try:
        # Check if stderr exceeds the token limit
        if stderr_content:
            token_response = await client.aio.models.count_tokens(
                model=settings.gemini_flash_model, contents=stderr_content
            )

            if (
                token_response.total_tokens
                and token_response.total_tokens > settings.summarizer_token_threshold
            ):
                print(
                    f"--- [LogSummarizer] Traceback is too large "
                    f"({token_response.total_tokens} tokens). Summarizing... ---"
                )

                prompt = (
                    "You are an expert software debugger. Analyze this execution traceback/error log "
                    "and summarize the root cause and key details in no more than 3-4 bullet points. "
                    "Focus only on the actionable information needed to fix the issue.\n\n"
                    f"Traceback:\n{stderr_content}"
                )

                # We use Gemini Flash for summarization tasks because it is fast and cheap
                response = await client.aio.models.generate_content(
                    model=settings.gemini_flash_model, contents=prompt
                )
                stderr_summary = response.text or "Failed to generate summary."
            else:
                # Content is small enough, no summary needed.
                stderr_summary = ""

        # Check if review comments exceed the token limit
        if review_content:
            token_response = await client.aio.models.count_tokens(
                model=settings.gemini_flash_model, contents=review_content
            )

            if (
                token_response.total_tokens
                and token_response.total_tokens > settings.summarizer_token_threshold
            ):
                print(
                    f"--- [LogSummarizer] Review comments are too large "
                    f"({token_response.total_tokens} tokens). Summarizing... ---"
                )

                prompt = (
                    "You are an expert code reviewer. Analyze these linter/security warnings "
                    "and summarize the most critical issues to fix in no more than 3-4 bullet points. "
                    "Focus only on the actionable information needed to resolve the warnings.\n\n"
                    f"Review Comments:\n{review_content}"
                )

                response = await client.aio.models.generate_content(
                    model=settings.gemini_flash_model, contents=prompt
                )
                review_summary = response.text or "Failed to generate summary."
            else:
                review_summary = ""

    except Exception as e:
        print(f"--- [LogSummarizer] Warning: Failed to calculate tokens or summarize logs: {e} ---")

    return {"stderr_summary": stderr_summary, "review_summary": review_summary}
