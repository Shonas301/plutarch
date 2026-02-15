"""discord cog for arc raiders stash management commands."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from plutarch.arc.client import ArcApiError, ArcClient
from plutarch.arc.engine import analyze_optimize, analyze_recycle, analyze_sell
from plutarch.arc.models import Item, OptimizeParams, Quest, Recommendation

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# embed colors
COLOR_SELL = 0x2ECC71  # green
COLOR_RECYCLE = 0x3498DB  # blue
COLOR_HOLD = 0xF39C12  # yellow
COLOR_ERROR = 0xE74C3C  # red

# discord embed limits
MAX_EMBED_DESC_LENGTH = 4000


class ArcStash(commands.Cog):
    """arc raiders stash management commands."""

    def __init__(self, client: commands.Bot) -> None:
        """Initialize the arc stash cog.

        Args:
            client: discord bot client
        """
        self.client = client
        self._arc_client = ArcClient(
            app_key=os.getenv("ARC_API_KEY", ""),
            user_key=os.getenv("ARC_USER_KEY", ""),
        )
        self._item_cache: dict[str, Item] | None = None
        self._quest_cache: dict[str, Quest] | None = None

    async def cog_unload(self) -> None:
        """Clean up aiohttp session when cog is unloaded."""
        await self._arc_client.close()

    async def _ensure_caches(self) -> tuple[dict[str, Item], dict[str, Quest]]:
        """Lazy-load item and quest caches on first command invocation.

        Returns:
            tuple of (items dict, quests dict)

        Raises:
            ArcApiError: on api errors
        """
        if self._item_cache is None:
            logger.info("fetching item catalog from arctracker")
            self._item_cache = await self._arc_client.fetch_items()

        if self._quest_cache is None:
            logger.info("fetching quest catalog from arctracker")
            self._quest_cache = await self._arc_client.fetch_quests()

        return self._item_cache, self._quest_cache

    def _format_recommendation_line(self, rec: Recommendation) -> str:
        """Format a single recommendation as a text line.

        Args:
            rec: recommendation to format

        Returns:
            formatted line with name, qty, sell, recycle, margin
        """
        return (
            f"{rec.name} x{rec.quantity} — "
            f"sell: {rec.sell_value}cr, recycle: {rec.recycle_value}cr "
            f"(margin: {rec.margin:+d}cr)"
        )

    def _build_embeds(
        self,
        title: str,
        recommendations: Sequence[Recommendation],
        color: int,
    ) -> list[discord.Embed]:
        """Build one or more embeds from recommendations, paginating if needed.

        Args:
            title: embed title
            recommendations: list of recommendations to include
            color: embed color

        Returns:
            list of embeds (multiple if content exceeds char limit)
        """
        if not recommendations:
            embed = discord.Embed(
                title=title,
                description="No items to display.",
                color=color,
            )
            return [embed]

        embeds = []
        current_lines = []
        current_length = 0

        for rec in recommendations:
            line = self._format_recommendation_line(rec)
            line_length = len(line) + 1  # +1 for newline

            # check if adding this line would exceed the limit
            if current_length + line_length > MAX_EMBED_DESC_LENGTH:
                # flush current embed
                total_value = sum(
                    r.sell_value if r.action == "sell" else r.recycle_value
                    for r in recommendations[: len(current_lines)]
                )
                summary = f"\n\n**Total:** {total_value} credits from {len(current_lines)} items"
                description = "\n".join(current_lines) + summary

                embed_title = title if not embeds else f"{title} (continued)"
                embeds.append(
                    discord.Embed(
                        title=embed_title,
                        description=description,
                        color=color,
                    )
                )

                # start new embed
                current_lines = [line]
                current_length = line_length
            else:
                current_lines.append(line)
                current_length += line_length

        # flush remaining lines
        if current_lines:
            # compute total for this chunk
            start_idx = sum(len(e.description.split("\n")) - 2 for e in embeds)
            chunk_recs = recommendations[start_idx : start_idx + len(current_lines)]
            total_value = sum(
                r.sell_value if r.action == "sell" else r.recycle_value
                for r in chunk_recs
            )
            summary = (
                f"\n\n**Total:** {total_value} credits from {len(current_lines)} items"
            )
            description = "\n".join(current_lines) + summary

            embed_title = title if not embeds else f"{title} (continued)"
            embeds.append(
                discord.Embed(
                    title=embed_title,
                    description=description,
                    color=color,
                )
            )

        return embeds

    @commands.command(name="arcsell")
    async def arcsell(self, ctx: commands.Context) -> None:
        """Show which stash items should be sold instead of recycled.

        Args:
            ctx: discord command context
        """
        # check for api keys
        if not os.getenv("ARC_API_KEY") or not os.getenv("ARC_USER_KEY"):
            await ctx.send("Arc API keys not configured.")
            return

        try:
            # fetch data
            items, _ = await self._ensure_caches()
            stash = await self._arc_client.fetch_stash()

            # analyze
            recommendations = analyze_sell(stash, items)

            # build and send embeds
            embeds = self._build_embeds("Items to Sell", recommendations, COLOR_SELL)
            for embed in embeds:
                await ctx.send(embed=embed)

        except ArcApiError as e:
            logger.exception("arctracker api error in arcsell")
            embed = discord.Embed(
                title="API Error",
                description=f"Error from ArcTracker: [{e.status}] {e.code}",
                color=COLOR_ERROR,
            )
            await ctx.send(embed=embed)
        except Exception:
            logger.exception("unexpected error in arcsell")
            await ctx.send("Something went wrong while analyzing your stash.")

    @commands.command(name="arcrecycle")
    async def arcrecycle(self, ctx: commands.Context) -> None:
        """Show which stash items should be recycled instead of sold.

        Args:
            ctx: discord command context
        """
        # check for api keys
        if not os.getenv("ARC_API_KEY") or not os.getenv("ARC_USER_KEY"):
            await ctx.send("Arc API keys not configured.")
            return

        try:
            # fetch data
            items, _ = await self._ensure_caches()
            stash = await self._arc_client.fetch_stash()

            # analyze
            recommendations = analyze_recycle(stash, items)

            # build and send embeds
            embeds = self._build_embeds(
                "Items to Recycle", recommendations, COLOR_RECYCLE
            )
            for embed in embeds:
                await ctx.send(embed=embed)

        except ArcApiError as e:
            logger.exception("arctracker api error in arcrecycle")
            embed = discord.Embed(
                title="API Error",
                description=f"Error from ArcTracker: [{e.status}] {e.code}",
                color=COLOR_ERROR,
            )
            await ctx.send(embed=embed)
        except Exception:
            logger.exception("unexpected error in arcrecycle")
            await ctx.send("Something went wrong while analyzing your stash.")

    def _parse_optimize_flags(self, args: tuple[str, ...]) -> OptimizeParams | None:
        """Parse command flags into OptimizeParams.

        Args:
            args: command arguments

        Returns:
            parsed params, or None if invalid
        """
        params = OptimizeParams()
        arg_list = list(args)
        i = 0
        while i < len(arg_list):
            arg = arg_list[i]
            if arg == "--no-quests":
                params.quest_aware = False
            elif arg == "--hideout":
                params.include_hideout = True
            elif arg == "--projects":
                params.include_projects = True
            elif arg == "--min-profit":
                if i + 1 < len(arg_list):
                    try:
                        params.min_profit_threshold = int(arg_list[i + 1])
                        i += 1  # skip the next arg (the number)
                    except ValueError:
                        return None
                else:
                    return None
            i += 1
        return params

    @commands.command(name="arcoptimize")
    async def arcoptimize(self, ctx: commands.Context, *args: str) -> None:
        """Greedy optimizer showing sell/recycle/hold recommendations.

        Flags:
            --no-quests: disable quest-aware holdback
            --min-profit N: minimum profit threshold in credits
            --hideout: hold back items needed for hideout upgrades
            --projects: hold back items needed for projects

        Args:
            ctx: discord command context
            args: command arguments (flags)
        """
        # check for api keys
        if not os.getenv("ARC_API_KEY") or not os.getenv("ARC_USER_KEY"):
            await ctx.send("Arc API keys not configured.")
            return

        # parse flags
        params = self._parse_optimize_flags(args)
        if params is None:
            await ctx.send("Invalid command flags. Use --min-profit <number>")
            return

        try:
            # fetch data
            items, quests = await self._ensure_caches()
            stash = await self._arc_client.fetch_stash()

            # analyze
            result = analyze_optimize(stash, items, quests, params)

            # build embeds for each section
            all_embeds = []

            # sell section (green)
            if result.sell:
                sell_embeds = self._build_embeds("SELL", result.sell, COLOR_SELL)
                all_embeds.extend(sell_embeds)

            # recycle section (blue)
            if result.recycle:
                recycle_embeds = self._build_embeds(
                    "RECYCLE", result.recycle, COLOR_RECYCLE
                )
                all_embeds.extend(recycle_embeds)

            # hold section (yellow)
            if result.hold:
                hold_embeds = self._build_embeds("HOLD", result.hold, COLOR_HOLD)
                all_embeds.extend(hold_embeds)

            # summary embed
            summary_text = (
                f"**Sell:** {result.total_sell_value} credits from {len(result.sell)} items\n"
                f"**Recycle:** {result.total_recycle_value} credits from {len(result.recycle)} items\n"
                f"**Hold:** {result.total_hold_count} items (quest-aware: {params.quest_aware})"
            )
            summary_embed = discord.Embed(
                title="Optimization Summary",
                description=summary_text,
                color=0x95A5A6,  # gray
            )
            all_embeds.append(summary_embed)

            # send all embeds
            for embed in all_embeds:
                await ctx.send(embed=embed)

        except ArcApiError as e:
            logger.exception("arctracker api error in arcoptimize")
            embed = discord.Embed(
                title="API Error",
                description=f"Error from ArcTracker: [{e.status}] {e.code}",
                color=COLOR_ERROR,
            )
            await ctx.send(embed=embed)
        except Exception:
            logger.exception("unexpected error in arcoptimize")
            await ctx.send("Something went wrong while optimizing your stash.")
