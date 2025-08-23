from __future__ import annotations

import logging
from typing import Any, Optional
import datetime as dt

import discord
from discord.ext import commands
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..cache import get_cached_answer
from ..agents.help_agent import answer_help_query
from ..agents.calendar_agent import parse_times_and_summary
from ..user_settings import get_user_timezone, set_user_timezone
from ..google_oauth import get_user_credentials
from ..tools.google_calendar import GoogleCalendarClient


logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="help", description="Get help with a command or tool")
    async def help_command(self, ctx: commands.Context, *, query: str) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            cached_answer = get_cached_answer(query)
            if cached_answer:
                content, footer_source = cached_answer, "Cache"
            else:
                content, sources = await answer_help_query(query)
                footer_source = f"Sources: {', '.join(sources[:3])}" if sources else "AI Generated"

            embed = discord.Embed(
                title=f"Help: {query}",
                description=content,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"Source: {footer_source} | Powered by AI")
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

    @commands.hybrid_command(name="event", description="Create a calendar event from natural language")
    async def event(self, ctx: commands.Context, *, details: str) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        creds = get_user_credentials(ctx.author.id)
        if not creds:
            await (ctx.interaction.followup.send("Please connect Google first with `/connect_google`.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Please connect Google first with `/connect_google`."))
            return

        settings = get_settings()
        user_tz = get_user_timezone(ctx.author.id) or settings.default_timezone or "UTC"

        gcal = GoogleCalendarClient(creds)
        if user_tz == "UTC":
            tz2 = gcal.get_user_timezone()
            if isinstance(tz2, str) and tz2:
                user_tz = tz2

        start, end, summary = await parse_times_and_summary(details, user_tz)
        if start is None or end is None:
            msg = "I couldn’t parse the time. Try: 'tomorrow 3pm for 1h Team sync'"
            await (ctx.interaction.followup.send(msg) if getattr(ctx, "interaction", None) else ctx.reply(msg))
            return

        try:
            link = gcal.create_event(summary=summary, start=start, end=end)
            await (ctx.interaction.followup.send(f"Event created: {link}")
                   if getattr(ctx, "interaction", None) else ctx.reply(f"Event created: {link}"))
        except Exception as e:
            await (ctx.interaction.followup.send(f"Sorry, couldn’t create the event: {e}")
                   if getattr(ctx, "interaction", None) else ctx.reply(f"Sorry, couldn’t create the event: {e}"))

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


