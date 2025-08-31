from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..agents.specialists import PersonalSpecialist, CommandSpecialist, NLPSpecialist, AnalyticsSpecialist
from ..user_settings import get_user_timezone, set_user_timezone
from ..tools.task_manager import get_task_manager, create_task_from_text
from ..services.metrics import get_metrics_collector, metrics_middleware


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
            # Use metrics middleware
            text = await metrics_middleware("help", ctx.author.id, self.command.act, query, {})
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
        
        try:
            msg = await metrics_middleware("ask_personal", ctx.author.id, self.personal.act, text, {"user_id": ctx.author.id, "user_tz": user_tz})

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
        except Exception as e:
            logger.error(f"Error in ask_personal: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't process your request.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't process your request."))

    @commands.hybrid_command(name="set_timezone", description="Set your timezone, e.g. Asia/Ho_Chi_Minh")
    async def set_timezone(self, ctx: commands.Context, *, tz: str) -> None:
        try:
            _ = ZoneInfo(tz)
            set_user_timezone(ctx.author.id, tz)
            # Record timezone in metrics
            metrics = get_metrics_collector()
            await metrics.record_user_timezone(ctx.author.id, tz)
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
                "Google connect coming soon. We'll DM you a link to authorize via OAuth."
            )
        else:
            await ctx.reply("Google connect coming soon. We'll DM you a link to authorize via OAuth.")


class TaskCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.task_manager = get_task_manager()

    @commands.hybrid_command(name="task", description="Create a new task")
    async def create_task(self, ctx: commands.Context, *, description: str) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            user_tz = get_user_timezone(ctx.author.id) or "Asia/Ho_Chi_Minh"
            task = create_task_from_text(description, ctx.author.id, user_tz)
            
            embed = discord.Embed(
                title="✅ Task Created",
                description=f"**{task.title}**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            
            if task.description:
                embed.add_field(name="Description", value=task.description[:1024], inline=False)
            if task.due_date:
                embed.add_field(name="Due Date", value=task.due_date.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="Priority", value=task.priority.title(), inline=True)
            if task.tags:
                embed.add_field(name="Tags", value=", ".join(task.tags), inline=True)
            
            await (ctx.interaction.followup.send(embed=embed)
                   if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't create the task.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't create the task."))

    @commands.hybrid_command(name="tasks", description="List your tasks")
    async def list_tasks(self, ctx: commands.Context, status: str = "pending") -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            tasks = self.task_manager.get_user_tasks(ctx.author.id, status=status, include_completed=False)
            
            if not tasks:
                await (ctx.interaction.followup.send(f"No {status} tasks found.")
                       if getattr(ctx, "interaction", None) else ctx.reply(f"No {status} tasks found."))
                return

            embed = discord.Embed(
                title=f"📋 Your Tasks ({status.title()})",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            for task in tasks[:10]:  # Limit to 10 tasks
                value = f"Priority: {task.priority.title()}"
                if task.due_date:
                    value += f"\nDue: {task.due_date.strftime('%Y-%m-%d %H:%M')}"
                if task.tags:
                    value += f"\nTags: {', '.join(task.tags)}"
                
                embed.add_field(
                    name=f"#{task.id} {task.title}",
                    value=value,
                    inline=False
                )

            await (ctx.interaction.followup.send(embed=embed)
                   if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't list your tasks.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't list your tasks."))

    @commands.hybrid_command(name="complete", description="Mark a task as completed")
    async def complete_task(self, ctx: commands.Context, task_id: int) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            updated_task = self.task_manager.update_task(task_id, ctx.author.id, status="completed")
            if updated_task:
                embed = discord.Embed(
                    title="✅ Task Completed",
                    description=f"**{updated_task.title}** has been marked as completed!",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow(),
                )
                await (ctx.interaction.followup.send(embed=embed)
                       if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
            else:
                await (ctx.interaction.followup.send("Task not found or you don't have permission to modify it.")
                       if getattr(ctx, "interaction", None) else ctx.reply("Task not found or you don't have permission to modify it."))
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't complete the task.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't complete the task."))

    @commands.hybrid_command(name="start", description="Mark a task as in progress")
    async def start_task(self, ctx: commands.Context, task_id: int) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            updated_task = self.task_manager.update_task(task_id, ctx.author.id, status="in_progress")
            if updated_task:
                embed = discord.Embed(
                    title="🚀 Task Started",
                    description=f"**{updated_task.title}** is now in progress!",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )
                await (ctx.interaction.followup.send(embed=embed)
                       if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
            else:
                await (ctx.interaction.followup.send("Task not found or you don't have permission to modify it.")
                       if getattr(ctx, "interaction", None) else ctx.reply("Task not found or you don't have permission to modify it."))
        except Exception as e:
            logger.error(f"Error starting task: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't start the task.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't start the task."))

    @commands.hybrid_command(name="cancel", description="Cancel a task")
    async def cancel_task(self, ctx: commands.Context, task_id: int) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            updated_task = self.task_manager.update_task(task_id, ctx.author.id, status="cancelled")
            if updated_task:
                embed = discord.Embed(
                    title="❌ Task Cancelled",
                    description=f"**{updated_task.title}** has been cancelled.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                await (ctx.interaction.followup.send(embed=embed)
                       if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
            else:
                await (ctx.interaction.followup.send("Task not found or you don't have permission to modify it.")
                       if getattr(ctx, "interaction", None) else ctx.reply("Task not found or you don't have permission to modify it."))
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't cancel the task.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't cancel the task."))

    @commands.hybrid_command(name="status", description="Change task status")
    async def change_status(self, ctx: commands.Context, task_id: int, status: str) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        valid_statuses = ["pending", "in_progress", "completed", "cancelled"]
        if status.lower() not in valid_statuses:
            await (ctx.interaction.followup.send(f"Invalid status. Use one of: {', '.join(valid_statuses)}")
                   if getattr(ctx, "interaction", None) else ctx.reply(f"Invalid status. Use one of: {', '.join(valid_statuses)}"))
            return

        try:
            updated_task = self.task_manager.update_task(task_id, ctx.author.id, status=status.lower())
            if updated_task:
                status_emoji = {
                    "pending": "⏳",
                    "in_progress": "🚀",
                    "completed": "✅",
                    "cancelled": "❌",
                }
                embed = discord.Embed(
                    title=f"{status_emoji.get(status.lower(), '📝')} Task Status Updated",
                    description=f"**{updated_task.title}** is now {status.lower().replace('_', ' ')}",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow(),
                )
                await (ctx.interaction.followup.send(embed=embed)
                       if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
            else:
                await (ctx.interaction.followup.send("Task not found or you don't have permission to modify it.")
                       if getattr(ctx, "interaction", None) else ctx.reply("Task not found or you don't have permission to modify it."))
        except Exception as e:
            logger.error(f"Error changing task status: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't change the task status.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't change the task status."))

    @commands.hybrid_command(name="delete", description="Delete a task permanently")
    async def delete_task(self, ctx: commands.Context, task_id: int) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            task = self.task_manager.get_task(task_id, ctx.author.id)
            if not task:
                await (ctx.interaction.followup.send("Task not found or you don't have permission to delete it.")
                       if getattr(ctx, "interaction", None) else ctx.reply("Task not found or you don't have permission to delete it."))
                return

            deleted = self.task_manager.delete_task(task_id, ctx.author.id)
            if deleted:
                embed = discord.Embed(
                    title="🗑️ Task Deleted",
                    description=f"**{task.title}** has been permanently deleted.",
                    color=discord.Color.dark_red(),
                    timestamp=discord.utils.utcnow(),
                )
                await (ctx.interaction.followup.send(embed=embed)
                       if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
            else:
                await (ctx.interaction.followup.send("Failed to delete the task.")
                       if getattr(ctx, "interaction", None) else ctx.reply("Failed to delete the task."))
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't delete the task.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't delete the task."))

class AnalyticsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.analytics = AnalyticsSpecialist()

    @commands.hybrid_command(name="stats", description="Get your usage statistics")
    async def get_stats(self, ctx: commands.Context) -> None:
        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            stats = await self.analytics.act("stats", {"user_id": ctx.author.id})
            
            embed = discord.Embed(
                title="📊 Your Statistics",
                description=stats,
                color=discord.Color.purple(),
                timestamp=discord.utils.utcnow(),
            )
            
            await (ctx.interaction.followup.send(embed=embed)
                   if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't get your statistics.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't get your statistics."))

    @commands.hybrid_command(name="system", description="Get system analytics (admin only)")
    async def get_system_stats(self, ctx: commands.Context) -> None:
        # Check if user is admin (you can customize this logic)
        if not ctx.author.guild_permissions.administrator:
            await (ctx.interaction.followup.send("You need administrator permissions to view system stats.")
                   if getattr(ctx, "interaction", None) else ctx.reply("You need administrator permissions to view system stats."))
            return

        if getattr(ctx, "interaction", None):
            await ctx.interaction.response.defer()
        else:
            await ctx.defer()

        try:
            stats = await self.analytics.act("system", {"user_id": ctx.author.id})
            
            embed = discord.Embed(
                title="🤖 System Analytics",
                description=stats,
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow(),
            )
            
            await (ctx.interaction.followup.send(embed=embed)
                   if getattr(ctx, "interaction", None) else ctx.reply(embed=embed))
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            await (ctx.interaction.followup.send("Sorry, I couldn't get system statistics.")
                   if getattr(ctx, "interaction", None) else ctx.reply("Sorry, I couldn't get system statistics."))


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
        await self.add_cog(TaskCog(self))
        await self.add_cog(AnalyticsCog(self))
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


