from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "UrbanClimate-Expert"
    environment: str = "development"

    # 日志配置
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_rotation: str = "00:00"  # 每天午夜轮转
    log_retention: str = "30 days"

    # LLM configuration
    llm_type: str = "ollama"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:14b"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"

    # LightRAG workspace
    lightrag_workspace: str = "./data"

    # Rerank configuration
    enable_rerank: bool = False
    rerank_model: str = "rerank-v3.5"
    rerank_api_key: str | None = None
    rerank_base_url: str = "https://api.cohere.com/v2/rerank"
    rerank_max_tokens_per_doc: int = 4096

    # LightRAG timeout configuration (seconds)
    llm_timeout: int = 600  # LLM 调用超时，本地大模型建议 600+
    embedding_timeout: int = 120  # Embedding 调用超时

    @property
    def lightrag_workspace_path(self) -> Path:
        """将 lightrag_workspace 转换为绝对路径"""
        workspace = Path(self.lightrag_workspace)
        if not workspace.is_absolute():
            # 相对路径:相对于 backend/ 目录
            backend_dir = Path(__file__).resolve().parents[2]
            workspace = backend_dir / workspace
        return workspace.resolve()

    # Database configuration
    mysql_dsn: str = "mysql+aiomysql://root:password@localhost:3306/urban_climate"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j-password"

    # File storage configuration
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 100
    allowed_extensions: list[str] = [".pdf"]

    @property
    def upload_dir_path(self) -> Path:
        """将 upload_dir 转换为绝对路径"""
        upload_path = Path(self.upload_dir)
        if not upload_path.is_absolute():
            backend_dir = Path(__file__).resolve().parents[2]
            upload_path = backend_dir / upload_path
        return upload_path.resolve()

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
