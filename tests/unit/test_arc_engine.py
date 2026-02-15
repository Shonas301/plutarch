"""tests for arc decision engine."""

from plutarch.arc.engine import (
    analyze_optimize,
    analyze_recycle,
    analyze_sell,
)
from plutarch.arc.models import (
    Item,
    ItemQuantity,
    OptimizeParams,
    Quest,
    StashItem,
)

# -- fixture helpers --


def make_item(
    id: str,
    name_en: str,
    value: int,
    recycles_into: dict[str, int] | None = None,
    type: str = "material",
    rarity: str = "common",
) -> Item:
    """helper to build Item objects for tests.

    Args:
        id: item identifier
        name_en: english name
        value: sell value in credits
        recycles_into: map of material_id -> quantity
        type: item type
        rarity: item rarity

    Returns:
        Item instance with reasonable defaults
    """
    return Item(
        id=id,
        name={"en": name_en},
        description={"en": f"test item: {name_en}"},
        type=type,
        rarity=rarity,
        value=value,
        weight_kg=1.0,
        stack_size=100,
        image_filename=f"{id}.png",
        updated_at="2025-01-01T00:00:00Z",
        recycles_into=recycles_into or {},
    )


def make_stash_item(
    item_id: str,
    quantity: int,
    name: str = "test item",
    slot_index: int = 0,
) -> StashItem:
    """helper to build StashItem objects for tests.

    Args:
        item_id: item identifier
        quantity: number of items in stack
        name: item name from stash api
        slot_index: slot position in stash

    Returns:
        StashItem instance
    """
    return StashItem(
        item_id=item_id,
        name=name,
        quantity=quantity,
        slot_index=slot_index,
    )


def make_quest(
    id: str,
    reward_item_ids: list[ItemQuantity] | None = None,
    granted_item_ids: list[ItemQuantity] | None = None,
    objectives: list[dict[str, str]] | None = None,
    trader: str = "test trader",
) -> Quest:
    """helper to build Quest objects for tests.

    Args:
        id: quest identifier
        reward_item_ids: items rewarded by quest
        granted_item_ids: items granted by quest
        objectives: quest objectives as localized strings
        trader: quest giver name

    Returns:
        Quest instance with reasonable defaults
    """
    return Quest(
        id=id,
        name={"en": f"quest {id}"},
        description={"en": f"test quest {id}"},
        trader=trader,
        objectives=objectives or [],
        reward_item_ids=reward_item_ids or [],
        xp=1000,
        previous_quest_ids=[],
        next_quest_ids=[],
        updated_at="2025-01-01T00:00:00Z",
        slug=id,
        granted_item_ids=granted_item_ids or [],
    )


# -- tests for analyze_sell --


class TestAnalyzeSell:
    """tests for analyze_sell function."""

    def test_item_with_sell_value_greater_than_recycle_value_appears(self):
        """should include item when selling is more profitable."""
        items = {
            "item1": make_item("item1", "profitable sell", value=100),
            "mat1": make_item("mat1", "material", value=10),
        }
        # recycling gives 3 * 10 = 30, selling gives 100
        items["item1"].recycles_into = {"mat1": 3}

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_sell(stash, items)

        assert len(result) == 1
        assert result[0].item_id == "item1"
        assert result[0].sell_value == 100
        assert result[0].recycle_value == 30
        assert result[0].action == "sell"

    def test_item_with_sell_value_less_than_recycle_value_does_not_appear(self):
        """should exclude item when recycling is more profitable."""
        items = {
            "item1": make_item("item1", "better recycle", value=10),
            "mat1": make_item("mat1", "material", value=50),
        }
        # recycling gives 3 * 50 = 150, selling gives 10
        items["item1"].recycles_into = {"mat1": 3}

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_sell(stash, items)

        assert len(result) == 0

    def test_items_sorted_by_sell_value_descending(self):
        """should sort results by sell_value highest first."""
        items = {
            "item1": make_item("item1", "low value", value=50),
            "item2": make_item("item2", "high value", value=200),
            "item3": make_item("item3", "mid value", value=100),
        }

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
            make_stash_item("item3", quantity=1),
        ]

        result = analyze_sell(stash, items)

        assert len(result) == 3
        assert result[0].item_id == "item2"
        assert result[0].sell_value == 200
        assert result[1].item_id == "item3"
        assert result[1].sell_value == 100
        assert result[2].item_id == "item1"
        assert result[2].sell_value == 50

    def test_zero_value_items_excluded(self):
        """should exclude items with zero value (cosmetics/trinkets)."""
        items = {
            "cosmetic": make_item("cosmetic", "trinket", value=0),
            "valuable": make_item("valuable", "material", value=100),
        }

        stash = [
            make_stash_item("cosmetic", quantity=1),
            make_stash_item("valuable", quantity=1),
        ]

        result = analyze_sell(stash, items)

        assert len(result) == 1
        assert result[0].item_id == "valuable"

    def test_items_not_in_catalog_skipped(self):
        """should skip items not found in item catalog."""
        items = {
            "item1": make_item("item1", "known item", value=100),
        }

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("unknown", quantity=1),
        ]

        result = analyze_sell(stash, items)

        assert len(result) == 1
        assert result[0].item_id == "item1"


# -- tests for analyze_recycle --


class TestAnalyzeRecycle:
    """tests for analyze_recycle function."""

    def test_item_with_recycle_value_greater_than_sell_value_appears(self):
        """should include item when recycling is more profitable."""
        items = {
            "item1": make_item("item1", "profitable recycle", value=10),
            "mat1": make_item("mat1", "valuable material", value=50),
        }
        # recycling gives 3 * 50 = 150, selling gives 10
        items["item1"].recycles_into = {"mat1": 3}

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_recycle(stash, items)

        assert len(result) == 1
        assert result[0].item_id == "item1"
        assert result[0].recycle_value == 150
        assert result[0].sell_value == 10
        assert result[0].action == "recycle"

    def test_item_with_recycle_value_less_than_sell_value_does_not_appear(self):
        """should exclude item when selling is more profitable."""
        items = {
            "item1": make_item("item1", "better sell", value=100),
            "mat1": make_item("mat1", "material", value=10),
        }
        # recycling gives 3 * 10 = 30, selling gives 100
        items["item1"].recycles_into = {"mat1": 3}

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_recycle(stash, items)

        assert len(result) == 0

    def test_items_with_no_recycles_into_excluded(self):
        """should exclude items with no recycle data."""
        items = {
            "item1": make_item("item1", "no recycle", value=100),
            "item2": make_item("item2", "has recycle", value=10),
            "mat1": make_item("mat1", "material", value=50),
        }
        items["item2"].recycles_into = {"mat1": 3}

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
        ]

        result = analyze_recycle(stash, items)

        assert len(result) == 1
        assert result[0].item_id == "item2"

    def test_items_sorted_by_margin_descending(self):
        """should sort by recycle margin (biggest advantage first)."""
        items = {
            "item1": make_item("item1", "small margin", value=10),
            "item2": make_item("item2", "large margin", value=5),
            "item3": make_item("item3", "mid margin", value=20),
            "mat1": make_item("mat1", "material", value=30),
        }
        # item1: recycle=90, sell=10, margin=-80
        items["item1"].recycles_into = {"mat1": 3}
        # item2: recycle=150, sell=5, margin=-145 (biggest advantage)
        items["item2"].recycles_into = {"mat1": 5}
        # item3: recycle=60, sell=20, margin=-40
        items["item3"].recycles_into = {"mat1": 2}

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
            make_stash_item("item3", quantity=1),
        ]

        result = analyze_recycle(stash, items)

        # sorted by margin descending (most negative = biggest recycle advantage)
        assert len(result) == 3
        assert result[0].item_id == "item2"
        assert result[0].margin == -145
        assert result[1].item_id == "item1"
        assert result[1].margin == -80
        assert result[2].item_id == "item3"
        assert result[2].margin == -40


# -- tests for analyze_optimize --


class TestAnalyzeOptimize:
    """tests for analyze_optimize function."""

    def test_items_in_quest_hold_set_placed_in_hold_list(self):
        """should place quest-needed items in hold list."""
        items = {
            "quest_item": make_item("quest_item", "quest reward", value=100),
        }

        stash = [make_stash_item("quest_item", quantity=1)]

        quests = {
            "quest1": make_quest(
                "quest1",
                reward_item_ids=[ItemQuantity(item_id="quest_item", quantity=1)],
            ),
        }

        result = analyze_optimize(stash, items, quests)

        assert len(result.hold) == 1
        assert result.hold[0].item_id == "quest_item"
        assert result.hold[0].action == "hold"

    def test_items_above_sell_threshold_go_to_sell_list(self):
        """should place high-value sell items in sell list."""
        items = {
            "item1": make_item("item1", "valuable", value=100),
            "mat1": make_item("mat1", "material", value=10),
        }
        # recycling gives 3 * 10 = 30, selling gives 100
        items["item1"].recycles_into = {"mat1": 3}

        stash = [make_stash_item("item1", quantity=1)]

        quests = {}

        result = analyze_optimize(stash, items, quests)

        assert len(result.sell) == 1
        assert result.sell[0].item_id == "item1"
        assert result.sell[0].action == "sell"
        assert result.total_sell_value == 100

    def test_items_above_recycle_threshold_go_to_recycle_list(self):
        """should place high-value recycle items in recycle list."""
        items = {
            "item1": make_item("item1", "recyclable", value=10),
            "mat1": make_item("mat1", "valuable material", value=50),
        }
        # recycling gives 3 * 50 = 150, selling gives 10
        items["item1"].recycles_into = {"mat1": 3}

        stash = [make_stash_item("item1", quantity=1)]

        quests = {}

        result = analyze_optimize(stash, items, quests)

        assert len(result.recycle) == 1
        assert result.recycle[0].item_id == "item1"
        assert result.recycle[0].action == "recycle"
        assert result.total_recycle_value == 150

    def test_min_profit_threshold_filters_low_margin_items(self):
        """should exclude items below profit threshold."""
        items = {
            "item1": make_item("item1", "low margin", value=100),
            "item2": make_item("item2", "high margin", value=200),
            "mat1": make_item("mat1", "material", value=30),
        }
        # item1: sell=100, recycle=90, margin=10 (below threshold)
        items["item1"].recycles_into = {"mat1": 3}
        # item2: sell=200, recycle=90, margin=110 (above threshold)
        items["item2"].recycles_into = {"mat1": 3}

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
        ]

        quests = {}
        params = OptimizeParams(min_profit_threshold=50)

        result = analyze_optimize(stash, items, quests, params)

        assert len(result.sell) == 1
        assert result.sell[0].item_id == "item2"

    def test_quest_aware_false_disables_hold_set(self):
        """should not hold quest items when quest_aware is False."""
        items = {
            "quest_item": make_item("quest_item", "quest reward", value=100),
        }

        stash = [make_stash_item("quest_item", quantity=1)]

        quests = {
            "quest1": make_quest(
                "quest1",
                reward_item_ids=[ItemQuantity(item_id="quest_item", quantity=1)],
            ),
        }

        params = OptimizeParams(quest_aware=False)

        result = analyze_optimize(stash, items, quests, params)

        assert len(result.hold) == 0
        assert len(result.sell) == 1
        assert result.sell[0].item_id == "quest_item"

    def test_totals_computed_correctly(self):
        """should compute correct totals for sell/recycle/hold."""
        items = {
            "sell1": make_item("sell1", "sell item 1", value=100),
            "sell2": make_item("sell2", "sell item 2", value=200),
            "recycle1": make_item("recycle1", "recycle item", value=10),
            "hold1": make_item("hold1", "hold item", value=50),
            "mat1": make_item("mat1", "material", value=50),
        }
        items["recycle1"].recycles_into = {"mat1": 3}

        stash = [
            make_stash_item("sell1", quantity=1),
            make_stash_item("sell2", quantity=1),
            make_stash_item("recycle1", quantity=1),
            make_stash_item("hold1", quantity=1),
        ]

        quests = {
            "quest1": make_quest(
                "quest1",
                reward_item_ids=[ItemQuantity(item_id="hold1", quantity=1)],
            ),
        }

        result = analyze_optimize(stash, items, quests)

        assert result.total_sell_value == 300  # 100 + 200
        assert result.total_recycle_value == 150  # 3 * 50
        assert result.total_hold_count == 1

    def test_quest_objectives_matching_item_names(self):
        """should hold items whose names appear in quest objectives."""
        items = {
            "copper_ore": make_item("copper_ore", "copper ore", value=100),
        }

        stash = [make_stash_item("copper_ore", quantity=5)]

        quests = {
            "quest1": make_quest(
                "quest1",
                objectives=[{"en": "collect 10 copper ore from the mines"}],
            ),
        }

        result = analyze_optimize(stash, items, quests)

        assert len(result.hold) == 1
        assert result.hold[0].item_id == "copper_ore"

    def test_granted_items_placed_in_hold_set(self):
        """should hold items granted by quests."""
        items = {
            "starter_kit": make_item("starter_kit", "starter kit", value=100),
        }

        stash = [make_stash_item("starter_kit", quantity=1)]

        quests = {
            "quest1": make_quest(
                "quest1",
                granted_item_ids=[ItemQuantity(item_id="starter_kit", quantity=1)],
            ),
        }

        result = analyze_optimize(stash, items, quests)

        assert len(result.hold) == 1
        assert result.hold[0].item_id == "starter_kit"


# -- edge cases --


class TestEdgeCases:
    """tests for edge cases and error handling."""

    def test_empty_stash_returns_empty_results(self):
        """should return empty lists for empty stash."""
        items = {"item1": make_item("item1", "test", value=100)}
        stash = []
        quests = {}

        result = analyze_optimize(stash, items, quests)

        assert len(result.sell) == 0
        assert len(result.recycle) == 0
        assert len(result.hold) == 0
        assert result.total_sell_value == 0
        assert result.total_recycle_value == 0

    def test_all_items_zero_value_returns_empty_results(self):
        """should return empty results when all items have zero value."""
        items = {
            "cosmetic1": make_item("cosmetic1", "hat", value=0),
            "cosmetic2": make_item("cosmetic2", "trinket", value=0),
        }

        stash = [
            make_stash_item("cosmetic1", quantity=1),
            make_stash_item("cosmetic2", quantity=1),
        ]

        result = analyze_sell(stash, items)

        assert len(result) == 0

    def test_material_not_found_in_items_dict_recycle_value_is_zero(self):
        """should handle missing materials in recycle calculation gracefully."""
        items = {
            "item1": make_item("item1", "mystery item", value=100),
        }
        # references material not in items dict
        items["item1"].recycles_into = {"unknown_mat": 5}

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_recycle(stash, items)

        # recycle value should be 0 because material doesn't exist
        # sell value is 100, so selling is better
        assert len(result) == 0
