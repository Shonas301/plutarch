"""discord cog for arc raiders stash management commands."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from plutarch.arc.client import ArcApiError, ArcClient
from plutarch.arc.engine import (
    analyze_optimize,
    analyze_recycle,
    analyze_sell,
    build_deep_recycle_table,
)
from plutarch.arc.formatter import (
    format_recommendations_with_total,
    format_recycle_recommendations,
    format_sell_recommendations,
)
from plutarch.arc.models import Item, OptimizeParams, Quest, Recommendation

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# embed colors
COLOR_SELL = 0x2ECC71  # green
COLOR_RECYCLE = 0x3498DB  # blue
COLOR_HOLD = 0xF39C12  # yellow
COLOR_ERROR = 0xE74C3C  # red


def _build_section_embeds(
    title: str,
    recommendations: Sequence[Recommendation],
    color: int,
    *,
    show_all: bool,
    command_hint: str = "%arcoptimize all",
) -> list[discord.Embed]:
    """Build embeds for an optimize section (sell/recycle/hold).

    Args:
        title: section title (e.g. "SELL")
        recommendations: recommendations for this section
        color: embed sidebar color
        show_all: whether to paginate across multiple embeds
        command_hint: command shown in truncation footer

    Returns:
        list of discord.Embed objects
    """
    descs, _ = format_recommendations_with_total(
        recommendations, show_all=show_all, command_hint=command_hint
    )
    total_pages = len(descs)
    embeds = []
    for i, desc in enumerate(descs):
        if show_all and total_pages > 1:
            page_title = f"{title} ({i + 1}/{total_pages})"
        else:
            page_title = title
        embeds.append(discord.Embed(title=page_title, description=desc, color=color))
    return embeds


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
        self._recycle_table: dict[str, int] | None = None

    async def cog_unload(self) -> None:
        """Clean up aiohttp session when cog is unloaded."""
        await self._arc_client.close()

    async def _ensure_caches(
        self,
    ) -> tuple[dict[str, Item], dict[str, Quest], dict[str, int]]:
        """Lazy-load item, quest, and recycle table caches.

        Returns:
            tuple of (items dict, quests dict, recycle table)

        Raises:
            ArcApiError: on api errors
        """
        if self._item_cache is None:
            logger.info("fetching item catalog from arctracker")
            self._item_cache = await self._arc_client.fetch_items()
            # rebuild recycle table when items are refreshed
            logger.info("building deep recycle value table")
            self._recycle_table = build_deep_recycle_table(self._item_cache)

        if self._quest_cache is None:
            logger.info("fetching quest catalog from arctracker")
            self._quest_cache = await self._arc_client.fetch_quests()

        return self._item_cache, self._quest_cache, self._recycle_table

    @commands.command(name="arcsell")
    async def arcsell(self, ctx: commands.Context, *args: str) -> None:
        """Show which stash items should be sold instead of recycled.

        Args:
            ctx: discord command context
            args: command arguments ("all" for full listing)
        """
        # check for api keys
        if not os.getenv("ARC_API_KEY") or not os.getenv("ARC_USER_KEY"):
            await ctx.send("Arc API keys not configured.")
            return

        # parse "all" flag
        show_all = len(args) > 0 and args[0].lower() == "all"

        try:
            # fetch data
            items, _, recycle_table = await self._ensure_caches()
            stash = await self._arc_client.fetch_stash()

            # analyze
            recommendations = analyze_sell(stash, items, recycle_table)

            # format into table embeds (3-column sell layout with per-unit values)
            descriptions, _ = format_sell_recommendations(
                recommendations, show_all=show_all, command_hint="%arcsell all"
            )

            # build and send embeds
            total_pages = len(descriptions)
            for i, desc in enumerate(descriptions):
                if show_all and total_pages > 1:
                    title = f"\U0001f4b0 Items to Sell ({i + 1}/{total_pages})"
                else:
                    title = "\U0001f4b0 Items to Sell"
                embed = discord.Embed(
                    title=title,
                    description=desc,
                    color=COLOR_SELL,
                )
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
    async def arcrecycle(self, ctx: commands.Context, *args: str) -> None:
        """Show which stash items should be recycled instead of sold.

        Args:
            ctx: discord command context
            args: command arguments ("all" for full listing)
        """
        # check for api keys
        if not os.getenv("ARC_API_KEY") or not os.getenv("ARC_USER_KEY"):
            await ctx.send("Arc API keys not configured.")
            return

        # parse "all" flag
        show_all = len(args) > 0 and args[0].lower() == "all"

        try:
            # fetch data
            items, _, recycle_table = await self._ensure_caches()
            stash = await self._arc_client.fetch_stash()

            # analyze
            recommendations = analyze_recycle(stash, items, recycle_table)

            # format into table embeds (3-column recycle layout with per-unit values)
            descriptions, _ = format_recycle_recommendations(
                recommendations, show_all=show_all, command_hint="%arcrecycle all"
            )

            # build and send embeds
            total_pages = len(descriptions)
            for i, desc in enumerate(descriptions):
                if show_all and total_pages > 1:
                    title = f"\u267b Items to Recycle ({i + 1}/{total_pages})"
                else:
                    title = "\u267b Items to Recycle"
                embed = discord.Embed(
                    title=title,
                    description=desc,
                    color=COLOR_RECYCLE,
                )
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
            all: show all items across multiple embeds
            --no-quests: disable quest-aware holdback
            --min-profit N: minimum profit threshold in credits
            --hideout: hold back items needed for hideout upgrades
            --projects: hold back items needed for projects

        Args:
            ctx: discord command context
            args: command arguments ("all" flag first, then other flags)
        """
        # check for api keys
        if not os.getenv("ARC_API_KEY") or not os.getenv("ARC_USER_KEY"):
            await ctx.send("Arc API keys not configured.")
            return

        # parse "all" flag from the front of args
        show_all = len(args) > 0 and args[0].lower() == "all"
        remaining_args = args[1:] if show_all else args

        # parse flags
        params = self._parse_optimize_flags(remaining_args)
        if params is None:
            await ctx.send("Invalid command flags. Use --min-profit <number>")
            return

        try:
            await self._run_optimize(ctx, params, show_all=show_all)
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

    async def _run_optimize(
        self,
        ctx: commands.Context,
        params: OptimizeParams,
        *,
        show_all: bool,
    ) -> None:
        """Execute the optimize analysis and send result embeds.

        Args:
            ctx: discord command context
            params: optimizer parameters
            show_all: whether to paginate across multiple embeds
        """
        # fetch data
        items, quests, recycle_table = await self._ensure_caches()
        stash = await self._arc_client.fetch_stash()

        # analyze
        result = analyze_optimize(stash, items, recycle_table, quests, params)

        # build section embeds
        all_embeds: list[discord.Embed] = []

        if result.sell:
            all_embeds.extend(
                _build_section_embeds(
                    "\U0001f4b0 SELL",
                    result.sell,
                    COLOR_SELL,
                    show_all=show_all,
                    command_hint="%arcoptimize all",
                )
            )

        if result.recycle:
            all_embeds.extend(
                _build_section_embeds(
                    "\u267b RECYCLE",
                    result.recycle,
                    COLOR_RECYCLE,
                    show_all=show_all,
                    command_hint="%arcoptimize all",
                )
            )

        if result.hold:
            all_embeds.extend(
                _build_section_embeds(
                    "\U0001f4e6 HOLD",
                    result.hold,
                    COLOR_HOLD,
                    show_all=show_all,
                    command_hint="%arcoptimize all",
                )
            )

        # summary embed
        summary_text = (
            f"**Sell:** {result.total_sell_value:,} credits"
            f" from {len(result.sell)} items\n"
            f"**Recycle:** {result.total_recycle_value:,} credits"
            f" from {len(result.recycle)} items\n"
            f"**Hold:** {result.total_hold_count} items"
            f" (quest-aware: {params.quest_aware})"
        )
        all_embeds.append(
            discord.Embed(
                title="Optimization Summary",
                description=summary_text,
                color=0x95A5A6,
            )
        )

        # send all embeds
        for embed in all_embeds:
            await ctx.send(embed=embed)
