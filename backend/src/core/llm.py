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
def generate_content_with_retry(client: genai.Client, model: str, prompt: str, **kwargs: Any) -> str:
    """
    Generates content using the google-genai client with exponential backoff for rate limits.
    """
    response = client.models.generate_content(model=model, contents=prompt, **kwargs)
    # Return string response
    return response.text or ""
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
def generate_content_with_retry(client: genai.Client, model: str, prompt: str, **kwargs: Any) -> str:
    """
    Generates content using the google-genai client with exponential backoff for rate limits.
    """
    response = client.models.generate_content(model=model, contents=prompt, **kwargs)
    # Return string response
    return response.text or ""
