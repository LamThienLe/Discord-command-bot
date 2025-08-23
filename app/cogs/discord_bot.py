from __future__ import annotations

import logging
from typing import Any, Optional
import datetime as dt

import discord
from discord.ext import commands
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..agents.specialists import PersonalSpecialist, CommandSpecialist
from ..user_settings import get_user_timezone, set_user_timezone
from ..google_oauth import get_user_credentials
from ..tools.google_calendar import GoogleCalendarClient


logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.command = CommandSpecialist()

    @commands.hybrid_command(name="help", description="Get help with a command or tool")
    async def help_command(self, ctx: commands.Context, *, query: str) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            text = await self.command.act(query, {})
            if not text:
                text = "No answer available. Ensure MCP server is running (USE_MCP=true)."
            # Discord embed description limit is 4096 chars
            description = text if len(text) <= 4096 else (text[:4000] + "\n\n… truncated …")
            embed = discord.Embed(
                title=f"Help: {query}",
                description=description,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )
            if getattr(ctx, "interaction", None):
                await ctx.interaction.followup.send(embed=embed)
            else:
                await ctx.reply(embed=embed)
        except Exception as e:
            logger.error(f"Error processing help command: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't process your request.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't process your request."))


class CalendarCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.personal = PersonalSpecialist()


    @commands.hybrid_command(name="ask_personal", description="Ask personal assistant to schedule or plan.")
    async def ask_personal(self, ctx: commands.Context, *, text: str) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        settings = get_settings()
        user_tz = get_user_timezone(ctx.author.id) or settings.default_timezone or "Asia/Ho_Chi_Minh"
        msg = await self.personal.act(text, {"user_id": ctx.author.id, "user_tz": user_tz})

        # Follow-up path if time missing
        if msg.startswith("What time should I schedule"):
            await (ctx.interaction.followup.send(msg) if getattr(ctx, "interaction", None) else ctx.reply(msg))
            def _check(m: discord.Message) -> bool:
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
            try:
                reply: discord.Message = await self.bot.wait_for("message", check=_check, timeout=60)
            except Exception:
                out = "Timed out waiting for a time. Please try again."
                await (ctx.interaction.followup.send(out) if getattr(ctx, "interaction", None) else ctx.reply(out))
                return
            msg = await self.personal.act(f"{text} at {reply.content}", {"user_id": ctx.author.id, "user_tz": user_tz})

        await (ctx.interaction.followup.send(msg) if getattr(ctx, "interaction", None) else ctx.reply(msg))


    # Removed /ask_command; use /help instead which routes to CommandSpecialist


    @commands.hybrid_command(name="set_timezone", description="Set your timezone, e.g. Asia/Ho_Chi_Minh")
    async def set_timezone(self, ctx: commands.Context, *, tz: str) -> None:
        try:
            _ = ZoneInfo(tz)
            set_user_timezone(ctx.author.id, tz)
            await (ctx.interaction.followup.send(f"Timezone set to {tz}")
                   if getattr(ctx, "interaction", None) else ctx.reply(f"Timezone set to {tz}"))
        except Exception:
            await (ctx.interaction.followup.send("Invalid timezone. Try something like Asia/Ho_Chi_Minh")
                   if getattr(ctx, "interaction", None) else ctx.reply("Invalid timezone. Try something like Asia/Ho_Chi_Minh"))

    @commands.hybrid_command(name="connect_google", description="Connect your Google account (placeholder)")
    async def connect_google(self, ctx: commands.Context) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer(thinking=False)
            await ctx.interaction.followup.send(
                "Google connect coming soon. We’ll DM you a link to authorize via OAuth."
            )
        else:
            await ctx.reply("Google connect coming soon. We’ll DM you a link to authorize via OAuth.")


class CommandHelpBot(commands.Bot):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        settings = get_settings()
        self.settings = settings

        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=settings.discord_command_prefix,
            intents=intents,
            help_command=None,
            *args,
            **kwargs,
        )

    async def on_ready(self) -> None:
        logger.info(f"Bot connected as {self.user}")

    async def setup_hook(self) -> None:
        await self.add_cog(HelpCog(self))
        await self.add_cog(CalendarCog(self))
        try:
            if self.settings.discord_guild_id:
                guild_obj = discord.Object(id=self.settings.discord_guild_id)
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


