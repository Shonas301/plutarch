"""async http client for arctracker.io api endpoints."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import aiohttp

from plutarch.arc.models import (
    Item,
    ItemEffect,
    ItemQuantity,
    Pagination,
    Quest,
    StashCurrencies,
    StashData,
    StashItem,
    StashSlots,
    UserProfile,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class ArcApiError(Exception):
    """error from the arctracker api."""

    def __init__(self, code: str, message: str, status: int) -> None:
        """Initialize api error.

        Args:
            code: error code from api response
            message: error message from api response
            status: http status code
        """
        self.code = code
        self.message = message
        self.status = status
        super().__init__(f"[{status}] {code}: {message}")


class ArcClient:
    """async client for arctracker.io api.

    handles both public endpoints (items, quests) and authenticated
    endpoints (stash, profile). caches static data (items, quests)
    in-memory after first fetch.
    """

    BASE_URL = "https://arctracker.io"
    HTTP_OK = 200

    def __init__(self, app_key: str, user_key: str) -> None:
        """Initialize the arc api client.

        Args:
            app_key: application key from arctracker developer dashboard
            user_key: user's personal api key for authenticated endpoints
        """
        self._app_key = app_key
        self._user_key = user_key
        self._session: aiohttp.ClientSession | None = None
        self._item_cache: dict[str, Item] | None = None
        self._quest_cache: dict[str, Quest] | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session.

        Returns:
            active aiohttp client session
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = False,
        params: Mapping[str, str | int] | None = None,
    ) -> dict:
        """Make http request to arctracker api.

        Args:
            method: http method (GET, POST, etc)
            path: api path (e.g. /api/items)
            authenticated: whether to send user auth headers
            params: query parameters

        Returns:
            parsed json response

        Raises:
            ArcApiError: on non-200 responses with api error envelope
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"

        headers = {}
        if authenticated:
            headers["X-App-Key"] = self._app_key
            headers["Authorization"] = f"Bearer {self._user_key}"

        async with session.request(
            method, url, params=params, headers=headers
        ) as response:
            data = await response.json()

            if response.status != self.HTTP_OK:
                # parse error envelope: {"error": {"code": "...", "message": "..."}}
                error = data.get("error", {})
                code = error.get("code", "UNKNOWN")
                message = error.get("message", "Unknown error")
                raise ArcApiError(code, message, response.status)

            return data

    async def fetch_items(self) -> dict[str, Item]:
        """Fetch all game items from public endpoint.

        items are cached in-memory after first fetch.

        Returns:
            dictionary mapping item_id -> Item
        """
        if self._item_cache is not None:
            return self._item_cache

        data = await self._request("GET", "/api/items")

        items: dict[str, Item] = {}
        for item_data in data["items"]:
            # map camelCase to snake_case
            effects: dict[str, ItemEffect] = {}
            for effect_key, effect_data in item_data.get("effects", {}).items():
                if not isinstance(effect_data, dict):
                    continue
                # extract localized labels (all keys except 'value')
                labels = {k: v for k, v in effect_data.items() if k != "value"}
                effects[effect_key] = ItemEffect(
                    value=effect_data.get("value", ""),
                    labels=labels,
                )

            item = Item(
                id=item_data["id"],
                name=item_data.get("name", {}),
                description=item_data.get("description", {}),
                type=item_data.get("type", ""),
                rarity=item_data.get("rarity", ""),
                value=item_data.get("value", 0),
                weight_kg=item_data.get("weightKg", 0),
                stack_size=item_data.get("stackSize", 1),
                image_filename=item_data.get("imageFilename", ""),
                updated_at=item_data.get("updatedAt", ""),
                effects=effects,
                craft_bench=item_data.get("craftBench"),
                recipe=item_data.get("recipe", {}),
                recycles_into=item_data.get("recyclesInto", {}),
                salvages_into=item_data.get("salvagesInto", {}),
            )
            items[item.id] = item

        self._item_cache = items
        return items

    async def fetch_quests(self) -> dict[str, Quest]:
        """Fetch all quests from public endpoint.

        quests are cached in-memory after first fetch.

        Returns:
            dictionary mapping quest_id -> Quest
        """
        if self._quest_cache is not None:
            return self._quest_cache

        data = await self._request("GET", "/api/quests")

        quests: dict[str, Quest] = {}
        for _quest_id, quest_data in data["quests"].items():
            # map camelCase to snake_case for ItemQuantity lists
            reward_item_ids = [
                ItemQuantity(item_id=r["itemId"], quantity=r["quantity"])
                for r in quest_data.get("rewardItemIds", [])
            ]
            granted_item_ids = [
                ItemQuantity(item_id=g["itemId"], quantity=g["quantity"])
                for g in quest_data.get("grantedItemIds", [])
            ]

            quest = Quest(
                id=quest_data["id"],
                name=quest_data.get("name", {}),
                description=quest_data.get("description", {}),
                trader=quest_data.get("trader", ""),
                objectives=quest_data.get("objectives", []),
                reward_item_ids=reward_item_ids,
                xp=quest_data.get("xp", 0),
                previous_quest_ids=quest_data.get("previousQuestIds", []),
                next_quest_ids=quest_data.get("nextQuestIds", []),
                updated_at=quest_data.get("updatedAt", ""),
                slug=quest_data.get("slug", ""),
                map=quest_data.get("map", []),
                objectives_one_round=quest_data.get("objectivesOneRound", False),
                video_url=quest_data.get("videoUrl"),
                other_requirements=quest_data.get("otherRequirements", []),
                granted_item_ids=granted_item_ids,
            )
            quests[quest.id] = quest

        self._quest_cache = quests
        return quests

    async def fetch_stash(
        self,
        locale: str = "en",
        per_page: int = 50,
        sort: str = "slot",
    ) -> list[StashItem]:
        """Fetch all user stash items with automatic pagination.

        stash is always fetched fresh (not cached).

        Args:
            locale: language code (en, de, fr, etc)
            per_page: items per page (max 100)
            sort: sort order (slot, name, quantity)

        Returns:
            flat list of all stash items across all pages
        """
        # fetch first page to get pagination info
        params = {"locale": locale, "page": 1, "per_page": per_page, "sort": sort}
        data = await self._request(
            "GET", "/api/v2/user/stash", authenticated=True, params=params
        )

        # parse first page
        stash_data = self._parse_stash_data(data["data"])
        all_items = stash_data.items[:]
        total_pages = stash_data.pagination.total_pages

        # fetch remaining pages concurrently if needed
        if total_pages > 1:
            tasks = []
            for page in range(2, total_pages + 1):
                page_params = {
                    "locale": locale,
                    "page": page,
                    "per_page": per_page,
                    "sort": sort,
                }
                tasks.append(
                    self._request(
                        "GET",
                        "/api/v2/user/stash",
                        authenticated=True,
                        params=page_params,
                    )
                )

            # gather all pages
            pages = await asyncio.gather(*tasks)
            for page_data in pages:
                page_stash = self._parse_stash_data(page_data["data"])
                all_items.extend(page_stash.items)

        return all_items

    def _parse_stash_data(self, data: dict) -> StashData:
        """Parse stash data envelope from api response.

        Args:
            data: raw data dict from api response

        Returns:
            parsed StashData object
        """
        items = [
            StashItem(
                item_id=item["itemId"],
                name=item["name"],
                quantity=item["quantity"],
                slot_index=item["slotIndex"],
            )
            for item in data["items"]
        ]

        currencies = StashCurrencies(
            credits=data["currencies"]["credits"],
            cred=data["currencies"]["cred"],
            raider_tokens=data["currencies"]["raiderTokens"],
            xp=data["currencies"]["xp"],
        )

        slots = StashSlots(
            used=data["slots"]["used"],
            max=data["slots"]["max"],
        )

        pagination = Pagination(
            page=data["pagination"]["page"],
            per_page=data["pagination"]["perPage"],
            total=data["pagination"]["total"],
            total_pages=data["pagination"]["totalPages"],
        )

        return StashData(
            items=items,
            currencies=currencies,
            slots=slots,
            pagination=pagination,
            synced_at=data["syncedAt"],
        )

    async def fetch_profile(self) -> UserProfile:
        """Fetch user profile from authenticated endpoint.

        Returns:
            user profile with username, level, member_since
        """
        data = await self._request("GET", "/api/v2/user/profile", authenticated=True)

        profile_data = data["data"]
        return UserProfile(
            user_id=profile_data["userId"],
            username=profile_data["username"],
            player_level=profile_data["playerLevel"],
            member_since=profile_data["memberSince"],
        )

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> ArcClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()
