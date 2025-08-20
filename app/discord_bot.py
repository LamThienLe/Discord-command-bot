from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

from .config import get_settings
from .cache import get_cached_answer
from .firecrawl import fetch_context_for_query
from .agent import generate_structured_answer

logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    """Cog that implements the hybrid /help and !help command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        description="Get help with a command or tool",
        help="Type /help followed by a command name to get help",
    )
    async def help_command(self, ctx: commands.Context, *, query: str) -> None:
        # Defer appropriately for slash commands
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            cached_answer = get_cached_answer(query)
            if cached_answer:
                embed = self._create_embed(query, cached_answer, "Cache")
                if getattr(ctx, "interaction", None):
                    await ctx.interaction.followup.send(embed=embed)
                else:
                    await ctx.reply(embed=embed)
                return

            context_text, source_urls = await fetch_context_for_query(query)
            answer = await generate_structured_answer(query, context_text)
            footer_source = (
                f"Sources: {', '.join(source_urls[:3])}" if source_urls else "AI Generated"
            )
            embed = self._create_embed(query, answer, footer_source)
            if getattr(ctx, "interaction", None):
                await ctx.interaction.followup.send(embed=embed)
            else:
                await ctx.reply(embed=embed)

        except Exception as e:
            logger.error(f"Error processing help command: {e}")
            embed = discord.Embed(
                title="Error",
                description=f"Sorry, I couldn't process your request: {str(e)}",
                color=discord.Color.red(),
            )
            if getattr(ctx, "interaction", None):
                await ctx.interaction.followup.send(embed=embed)
            else:
                await ctx.reply(embed=embed)

    def _create_embed(self, query: str, content: str, source: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"Help: {query}",
            description=content,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Source: {source} | Powered by AI")
        return embed


class CommandHelpBot(commands.Bot):
    """Discord bot that provides command/tool help using AI."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        settings = get_settings()
        self.settings = settings

        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=settings.discord_command_prefix,
            intents=intents,
            help_command=None,  # disable default help to use our own
            *args,
            **kwargs,
        )

    async def on_ready(self) -> None:
        logger.info(f"Bot connected as {self.user}")

    async def setup_hook(self) -> None:
        # Add the cog containing our commands
        await self.add_cog(HelpCog(self))
        # Sync slash commands (guild-specific if provided)
        try:
            if self.settings.discord_guild_id:
                guild_obj = discord.Object(id=self.settings.discord_guild_id)
                # Copy global app commands (from hybrid commands) to the guild for instant availability
                self.tree.copy_global_to(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                logger.info("Slash commands synced to guild %s", self.settings.discord_guild_id)
            else:
                await self.tree.sync()
                logger.info("Slash commands synced globally (may take up to ~1 hour)")
        except Exception as e:
            logger.error("Failed to sync slash commands: %s", e)

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        logger.error(f"Command error: {error}")
        await ctx.send(f"Sorry, there was an error processing your request: {error}")


def create_discord_bot() -> CommandHelpBot:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise ValueError("DISCORD_BOT_TOKEN is required")
    return CommandHelpBot()


def run_discord_bot() -> None:
    bot = create_discord_bot()
    settings = get_settings()
    logger.info("Starting Discord bot...")
    bot.run(settings.discord_bot_token)
