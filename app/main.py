from __future__ import annotations

import logging
import sys
import os

from .cogs.discord_bot import run_discord_bot


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for the Discord bot."""
    try:
        logger.info("Starting Command Help Bot...")
        if os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}:
            logger.info("DRY_RUN is enabled. Tool requests will be logged as JSON (key=tool_args_json).")
        run_discord_bot()
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


