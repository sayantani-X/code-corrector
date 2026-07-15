from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gcp_project_id: str = "your-project-id"
    gcp_region: str = "us-central1"
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_flash_model: str = "gemini-3.5-flash"

    # Workspace paths for container sandboxing
    workspace_dir: str = "../workspace"
    docker_host_workspace_path: str | None = None

    # Database and Cache Settings
    database_url: str = "postgresql://postgres:postgres@localhost:5432/code_corrector"
    redis_url: str = "redis://localhost:6379/0"
    use_semantic_cache: bool = True
    cache_similarity_threshold: float = 0.92
    history_retention_days: int = 30
    history_max_size_mb: int = 200

    # Graph Execution Settings
    summarizer_token_threshold: int = 5000
    enable_hitl_executor: bool = True
    enable_hitl_planner: bool = True

    # API Authentication
    api_key: str = "default-dev-key-change-in-prod"


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
