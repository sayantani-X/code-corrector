import os


def get_secret(secret_id: str, version_id: str = "latest") -> str:
    """
    Access the payload for the given secret version if one exists.
    Uses Google Cloud Secret Manager.
    """
    # For local development without GCP credentials, fallback to env vars
    if os.getenv("ENVIRONMENT") != "production":
        return os.environ.get(secret_id, f"dev-{secret_id}")

    try:
        from google.cloud import secretmanager

        from src.core.config import settings

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{settings.gcp_project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Failed to fetch secret {secret_id}: {e}")
        return os.environ.get(secret_id, "")
