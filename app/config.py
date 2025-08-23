import os
from functools import lru_cache
from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Simple settings loader backed by environment variables."""

    def __init__(self) -> None:
        # Discord bot configuration
        self.discord_bot_token: str | None = os.getenv("DISCORD_BOT_TOKEN")
        self.discord_command_prefix: str = os.getenv("DISCORD_COMMAND_PREFIX", "!")
        self.discord_guild_id: int | None = (
            int(os.getenv("DISCORD_GUILD_ID")) if os.getenv("DISCORD_GUILD_ID") else None
        )

        # OpenAI
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

        # Ollama (local LLM)
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "mistral-nemo")

        # FireCrawl
        raw_firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
        self.firecrawl_api_key: str | None = (
            raw_firecrawl_key.strip() if isinstance(raw_firecrawl_key, str) else None
        )
        self.firecrawl_base_url: str = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev")
        
        # App settings
        self.debug: bool = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}
        self.default_timezone: str = os.getenv("DEFAULT_TIMEZONE", "Asia/Ho_Chi_Minh")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


