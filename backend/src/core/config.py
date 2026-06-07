from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gcp_project_id: str = "your-project-id"
    gcp_region: str = "us-central1"
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_flash_model: str = "gemini-3.5-flash"

    # Workspace paths for container sandboxing
    workspace_dir: str = "../workspace"
    docker_host_workspace_path: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
