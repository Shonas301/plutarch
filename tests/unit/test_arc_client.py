"""tests for arc api client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from plutarch.arc.client import ArcApiError, ArcClient


class TestFetchItems:
    """tests for fetch_items method."""

    async def test_parses_response_and_returns_dict_keyed_by_item_id(self):
        """should parse items response and return dict keyed by id."""
        mock_response_data = {
            "items": [
                {
                    "id": "item1",
                    "name": {"en": "Item 1"},
                    "description": {"en": "First item"},
                    "type": "material",
                    "rarity": "common",
                    "value": 100,
                    "weightKg": 1.5,
                    "stackSize": 50,
                    "imageFilename": "item1.png",
                    "updatedAt": "2025-01-01T00:00:00Z",
                    "effects": {},
                },
                {
                    "id": "item2",
                    "name": {"en": "Item 2"},
                    "description": {"en": "Second item"},
                    "type": "weapon",
                    "rarity": "rare",
                    "value": 500,
                    "weightKg": 3.0,
                    "stackSize": 1,
                    "imageFilename": "item2.png",
                    "updatedAt": "2025-01-01T00:00:00Z",
                    "effects": {
                        "damage": {
                            "value": "50",
                            "en": "Damage",
                        }
                    },
                    "craftBench": "workbench",
                    "recipe": {"mat1": 5},
                    "recyclesInto": {"mat2": 3},
                },
            ]
        }

        # mock the aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        # mock the session
        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        result = await client.fetch_items()

        assert len(result) == 2
        assert "item1" in result
        assert "item2" in result
        assert result["item1"].id == "item1"
        assert result["item1"].name == {"en": "Item 1"}
        assert result["item1"].value == 100
        assert result["item2"].id == "item2"
        assert result["item2"].craft_bench == "workbench"
        assert result["item2"].recipe == {"mat1": 5}
        assert result["item2"].recycles_into == {"mat2": 3}

    async def test_caches_second_call_returns_same_dict_without_http_request(self):
        """should cache items after first fetch and skip http on second call."""
        mock_response_data = {
            "items": [
                {
                    "id": "item1",
                    "name": {"en": "Item 1"},
                    "description": {"en": "First item"},
                    "type": "material",
                    "rarity": "common",
                    "value": 100,
                    "weightKg": 1.5,
                    "stackSize": 50,
                    "imageFilename": "item1.png",
                    "updatedAt": "2025-01-01T00:00:00Z",
                    "effects": {},
                },
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        # first call
        result1 = await client.fetch_items()

        # second call
        result2 = await client.fetch_items()

        # should return the same dict
        assert result1 is result2

        # should only make one http request
        assert mock_session.request.call_count == 1


class TestFetchQuests:
    """tests for fetch_quests method."""

    async def test_parses_response_and_caches(self):
        """should parse quests response and cache results."""
        mock_response_data = {
            "quests": {
                "quest1": {
                    "id": "quest1",
                    "name": {"en": "First Quest"},
                    "description": {"en": "Do the thing"},
                    "trader": "Trader A",
                    "objectives": [{"en": "Kill 10 enemies"}],
                    "rewardItemIds": [{"itemId": "reward1", "quantity": 1}],
                    "xp": 1000,
                    "previousQuestIds": [],
                    "nextQuestIds": ["quest2"],
                    "updatedAt": "2025-01-01T00:00:00Z",
                    "slug": "first-quest",
                    "grantedItemIds": [{"itemId": "starter", "quantity": 1}],
                },
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        # first call
        result1 = await client.fetch_quests()

        # second call
        result2 = await client.fetch_quests()

        # should parse correctly
        assert len(result1) == 1
        assert "quest1" in result1
        assert result1["quest1"].id == "quest1"
        assert result1["quest1"].trader == "Trader A"
        assert len(result1["quest1"].reward_item_ids) == 1
        assert result1["quest1"].reward_item_ids[0].item_id == "reward1"
        assert len(result1["quest1"].granted_item_ids) == 1
        assert result1["quest1"].granted_item_ids[0].item_id == "starter"

        # should cache
        assert result1 is result2
        assert mock_session.request.call_count == 1


class TestFetchStash:
    """tests for fetch_stash method."""

    async def test_auto_paginates_when_total_pages_greater_than_one(self):
        """should fetch all pages when total_pages > 1."""
        # first page response
        page1_response = {
            "data": {
                "items": [
                    {
                        "itemId": "item1",
                        "name": "Item 1",
                        "quantity": 5,
                        "slotIndex": 0,
                    }
                ],
                "currencies": {"credits": 1000, "cred": 500, "raiderTokens": 10, "xp": 5000},
                "slots": {"used": 1, "max": 100},
                "pagination": {"page": 1, "perPage": 1, "total": 2, "totalPages": 2},
                "syncedAt": "2025-01-01T00:00:00Z",
            }
        }

        # second page response
        page2_response = {
            "data": {
                "items": [
                    {
                        "itemId": "item2",
                        "name": "Item 2",
                        "quantity": 10,
                        "slotIndex": 1,
                    }
                ],
                "currencies": {"credits": 1000, "cred": 500, "raiderTokens": 10, "xp": 5000},
                "slots": {"used": 2, "max": 100},
                "pagination": {"page": 2, "perPage": 1, "total": 2, "totalPages": 2},
                "syncedAt": "2025-01-01T00:00:00Z",
            }
        }

        # mock responses
        mock_response1 = AsyncMock()
        mock_response1.status = 200
        mock_response1.json = AsyncMock(return_value=page1_response)
        mock_response1.__aenter__ = AsyncMock(return_value=mock_response1)
        mock_response1.__aexit__ = AsyncMock(return_value=False)

        mock_response2 = AsyncMock()
        mock_response2.status = 200
        mock_response2.json = AsyncMock(return_value=page2_response)
        mock_response2.__aenter__ = AsyncMock(return_value=mock_response2)
        mock_response2.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(side_effect=[mock_response1, mock_response2])
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        result = await client.fetch_stash(per_page=1)

        # should have items from both pages
        assert len(result) == 2
        assert result[0].item_id == "item1"
        assert result[1].item_id == "item2"

        # should make two requests
        assert mock_session.request.call_count == 2

    async def test_returns_flat_list_from_multiple_pages(self):
        """should return a flat list of items across all pages."""
        # same as previous test, but focus on output structure
        page1_response = {
            "data": {
                "items": [
                    {"itemId": "a", "name": "A", "quantity": 1, "slotIndex": 0},
                    {"itemId": "b", "name": "B", "quantity": 2, "slotIndex": 1},
                ],
                "currencies": {"credits": 1000, "cred": 500, "raiderTokens": 10, "xp": 5000},
                "slots": {"used": 4, "max": 100},
                "pagination": {"page": 1, "perPage": 2, "total": 4, "totalPages": 2},
                "syncedAt": "2025-01-01T00:00:00Z",
            }
        }

        page2_response = {
            "data": {
                "items": [
                    {"itemId": "c", "name": "C", "quantity": 3, "slotIndex": 2},
                    {"itemId": "d", "name": "D", "quantity": 4, "slotIndex": 3},
                ],
                "currencies": {"credits": 1000, "cred": 500, "raiderTokens": 10, "xp": 5000},
                "slots": {"used": 4, "max": 100},
                "pagination": {"page": 2, "perPage": 2, "total": 4, "totalPages": 2},
                "syncedAt": "2025-01-01T00:00:00Z",
            }
        }

        mock_response1 = AsyncMock()
        mock_response1.status = 200
        mock_response1.json = AsyncMock(return_value=page1_response)
        mock_response1.__aenter__ = AsyncMock(return_value=mock_response1)
        mock_response1.__aexit__ = AsyncMock(return_value=False)

        mock_response2 = AsyncMock()
        mock_response2.status = 200
        mock_response2.json = AsyncMock(return_value=page2_response)
        mock_response2.__aenter__ = AsyncMock(return_value=mock_response2)
        mock_response2.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(side_effect=[mock_response1, mock_response2])
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        result = await client.fetch_stash(per_page=2)

        # should have all items in flat list
        assert isinstance(result, list)
        assert len(result) == 4
        assert [item.item_id for item in result] == ["a", "b", "c", "d"]


class TestFetchProfile:
    """tests for fetch_profile method."""

    async def test_returns_user_profile(self):
        """should parse and return user profile."""
        mock_response_data = {
            "data": {
                "userId": "user123",
                "username": "TestPlayer",
                "playerLevel": 42,
                "memberSince": "2024-01-01T00:00:00Z",
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        result = await client.fetch_profile()

        assert result.user_id == "user123"
        assert result.username == "TestPlayer"
        assert result.player_level == 42
        assert result.member_since == "2024-01-01T00:00:00Z"


class TestErrorHandling:
    """tests for error handling."""

    async def test_non_200_response_raises_arc_api_error_with_correct_details(self):
        """should raise ArcApiError with code, message, and status from response."""
        mock_error_response = {
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Invalid API key",
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.json = AsyncMock(return_value=mock_error_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.closed = False

        client = ArcClient(app_key="bad_key", user_key="bad_user")
        client._session = mock_session

        with pytest.raises(ArcApiError) as exc_info:
            await client.fetch_items()

        error = exc_info.value
        assert error.code == "UNAUTHORIZED"
        assert error.message == "Invalid API key"
        assert error.status == 401
        assert "[401]" in str(error)
        assert "UNAUTHORIZED" in str(error)

    async def test_error_envelope_parsed_correctly(self):
        """should parse error envelope structure correctly."""
        mock_error_response = {
            "error": {
                "code": "RATE_LIMIT",
                "message": "Too many requests",
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.json = AsyncMock(return_value=mock_error_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        with pytest.raises(ArcApiError) as exc_info:
            await client.fetch_profile()

        error = exc_info.value
        assert error.code == "RATE_LIMIT"
        assert error.message == "Too many requests"
        assert error.status == 429

    async def test_missing_error_fields_use_defaults(self):
        """should use default error values when fields are missing."""
        mock_error_response = {
            "error": {}  # no code or message
        }

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.json = AsyncMock(return_value=mock_error_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.closed = False

        client = ArcClient(app_key="test_app", user_key="test_user")
        client._session = mock_session

        with pytest.raises(ArcApiError) as exc_info:
            await client.fetch_items()

        error = exc_info.value
        assert error.code == "UNKNOWN"
        assert error.message == "Unknown error"
        assert error.status == 500
