from __future__ import annotations

import logging
import datetime as dt
import re
from typing import Any, Optional

import discord
from discord.ext import commands
import dateparser
from dateparser.search import search_dates
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from .config import get_settings
from .cache import get_cached_answer
from .firecrawl import fetch_context_for_query
from .agent import generate_structured_answer
from .google_oauth import get_user_credentials

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


class CalendarCog(commands.Cog):
    """Create Google Calendar events."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="event",
        description="Create a calendar event from natural language"
    )
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

        # Extract duration first, then remove it before time parsing to avoid mis-parsing like "in 1 hour"
        duration = dt.timedelta(hours=1)
        dur_match = re.search(r"\b(?:for\s+)?(\d+)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes)\b", details, flags=re.IGNORECASE)
        details_no_duration = details
        if dur_match:
            qty = int(dur_match.group(1))
            unit = dur_match.group(2).lower()
            if unit.startswith("h"):
                duration = dt.timedelta(hours=qty)
            else:
                duration = dt.timedelta(minutes=qty)
            # Remove only the first occurrence of the duration phrase
            details_no_duration = re.sub(dur_match.re, " ", details, count=1)

        # Parse date/time from the remaining text, preferring future
        when = dateparser.parse(details_no_duration, settings={"PREFER_DATES_FROM": "future"})
        if not when:
            try:
                found = search_dates(details_no_duration, settings={"PREFER_DATES_FROM": "future"})
                if found and len(found) > 0:
                    when = found[0][1]
            except Exception:
                when = None
        if not when:
            msg = "I couldn’t parse the time. Try: 'tomorrow 3pm for 1h Team sync'"
            await (ctx.interaction.followup.send(msg) if getattr(ctx, "interaction", None) else ctx.reply(msg))
            return

        # Use UTC for now (per-user timezones later). If naive, treat as UTC.
        start = when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)
        end = start + duration

        # Build a concise summary by removing dates/times/duration and filler words
        summary_source = details[dur_match.end():].strip() if dur_match and dur_match.end() < len(details) else details_no_duration
        # Remove common time words and connectors
        summary_text = re.sub(r"\b(today|tomorrow|tonight|this\s+\w+|next\s+\w+|at|on|from|to|by|around|about)\b", " ", summary_source, flags=re.IGNORECASE)
        # Remove time patterns like 1pm, 1:00pm, 13:00
        summary_text = re.sub(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", " ", summary_text, flags=re.IGNORECASE)
        summary_text = re.sub(r"\b([01]?\d|2[0-3])(?:[:.]\d{2})\b", " ", summary_text)
        # Remove obvious command/filler words
        summary_text = re.sub(r"\b(add|create|schedule|set|make|meeting|event)\b", " ", summary_text, flags=re.IGNORECASE)
        summary_text = re.sub(r"\s+", " ", summary_text).strip()
        # Title-case short phrases, keep length reasonable
        summary = (summary_text.title() if summary_text else "Event")[:128]

        try:
            service = build("calendar", "v3", credentials=creds)
            body = {
                "summary": summary,
                "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            }
            ev = service.events().insert(calendarId="primary", body=body).execute()
            link = ev.get("htmlLink") or "(no link)"
            await (ctx.interaction.followup.send(f"Event created: {link}")
                   if getattr(ctx, "interaction", None) else ctx.reply(f"Event created: {link}"))
        except Exception as e:
            await (ctx.interaction.followup.send(f"Sorry, couldn’t create the event: {e}")
                   if getattr(ctx, "interaction", None) else ctx.reply(f"Sorry, couldn’t create the event: {e}"))

    @commands.hybrid_command(
        name="connect_google",
        description="Connect your Google account (placeholder)"
    )
    async def connect_google(self, ctx: commands.Context) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer(thinking=False)
            await ctx.interaction.followup.send(
                "Google connect coming soon. We’ll DM you a link to authorize via OAuth."
            )
        else:
            await ctx.reply("Google connect coming soon. We’ll DM you a link to authorize via OAuth.")


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
        await self.add_cog(CalendarCog(self))
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
