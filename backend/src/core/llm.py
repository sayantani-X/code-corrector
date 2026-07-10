from typing import Any

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings


def get_client() -> genai.Client:
    """
    Returns an authenticated google-genai Client configured for Vertex AI.
    It expects Application Default Credentials to be set up in the environment.
    """
    return genai.Client(
        vertexai=True, project=settings.gcp_project_id, location=settings.gcp_region
    )


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def generate_content_with_retry(
    client: genai.Client, model: str, prompt: str, **kwargs: Any
) -> str:
    """
    Generates content using the google-genai client with exponential backoff for rate limits.
    (Synchronous version, primarily for simple scripts or tools)
    """
    response = client.models.generate_content(model=model, contents=prompt, **kwargs)
    return response.text or ""


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def generate_content_with_retry_async(
    client: genai.Client, model: str, prompt: str, use_cache: bool = True, **kwargs: Any
) -> str:
    """
    Asynchronously generates content using the google-genai client with exponential backoff.
    Integrates with the hybrid SemanticCache to bypass LLM calls for similar prompts.
    """
    from .cache import semantic_cache  # Local import to prevent circular dependency issues

    # 1. Check the semantic cache first
    if use_cache and settings.use_semantic_cache:
        cached_response = await semantic_cache.get_cache_hit(prompt)
        if cached_response is not None:
            return cached_response

    # 2. On cache miss, generate using Vertex AI
    response = await client.aio.models.generate_content(model=model, contents=prompt, **kwargs)
    response_text = response.text or ""

    # 3. Store the newly generated response in the semantic cache
    if use_cache and settings.use_semantic_cache and response_text:
        await semantic_cache.set_cache_entry(prompt, response_text)

    return response_text
