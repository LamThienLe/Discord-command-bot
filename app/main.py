from __future__ import annotations

import logging
import sys

from .discord_bot import run_discord_bot


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for the Discord bot."""
    try:
        logger.info("Starting Command Help Bot...")
        run_discord_bot()
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


