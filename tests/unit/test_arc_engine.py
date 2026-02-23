"""tests for arc decision engine."""

from plutarch.arc.engine import (
    analyze_optimize,
    analyze_recycle,
    analyze_sell,
    build_deep_recycle_table,
    find_recycle_sources,
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


# -- tests for build_deep_recycle_table --


class TestBuildDeepRecycleTable:
    """tests for the recursive recycle value table builder."""

    def test_base_material_has_zero_recycle_value(self):
        """base materials (no recycles_into) should resolve to 0."""
        items = {
            "metal_parts": make_item("metal_parts", "Metal Parts", value=75),
        }

        table = build_deep_recycle_table(items)

        assert table["metal_parts"] == 0

    def test_single_depth_recycle(self):
        """item recycling into base materials should sum their sell values."""
        items = {
            "item1": make_item(
                "item1",
                "test item",
                value=100,
                recycles_into={"metal_parts": 3, "rubber_parts": 2},
            ),
            "metal_parts": make_item("metal_parts", "Metal Parts", value=75),
            "rubber_parts": make_item("rubber_parts", "Rubber Parts", value=50),
        }

        table = build_deep_recycle_table(items)

        # 3*75 + 2*50 = 225 + 100 = 325
        assert table["item1"] == 325

    def test_multi_depth_recycle(self):
        """item recycling into intermediate materials should recurse."""
        items = {
            "weapon": make_item(
                "weapon", "Weapon", value=5000, recycles_into={"mech_comp": 3}
            ),
            "mech_comp": make_item(
                "mech_comp",
                "Mechanical Components",
                value=640,
                recycles_into={"metal_parts": 3, "rubber_parts": 2},
            ),
            "metal_parts": make_item("metal_parts", "Metal Parts", value=75),
            "rubber_parts": make_item("rubber_parts", "Rubber Parts", value=50),
        }

        table = build_deep_recycle_table(items)

        # mech_comp deep recycle: 225+100=325, sell=640 > 325 so parent uses 640
        assert table["mech_comp"] == 325
        assert table["weapon"] == 3 * 640

    def test_uses_max_of_sell_vs_deep_recycle_at_each_level(self):
        """at each level, should use whichever is higher: sell or recurse deeper."""
        items = {
            "top": make_item("top", "Top Item", value=100, recycles_into={"mid": 2}),
            "mid": make_item("mid", "Mid Item", value=10, recycles_into={"base": 5}),
            "base": make_item("base", "Base Material", value=50),
        }

        table = build_deep_recycle_table(items)

        # base: 0 (no recycles_into)
        # mid: 5 * max(50, 0) = 250 (deep recycle). mid.value=10, so max(10, 250)=250 at parent
        # top: 2 * max(10, 250) = 500 (uses 250 because deep > sell)
        assert table["base"] == 0
        assert table["mid"] == 250
        assert table["top"] == 500

    def test_unknown_material_skipped(self):
        """materials not in catalog should be skipped (contribute 0)."""
        items = {
            "item1": make_item(
                "item1",
                "test",
                value=100,
                recycles_into={"unknown": 5, "metal_parts": 2},
            ),
            "metal_parts": make_item("metal_parts", "Metal Parts", value=75),
        }

        table = build_deep_recycle_table(items)

        # unknown contributes 0, metal_parts contributes 2*75=150
        assert table["item1"] == 150

    def test_all_items_resolved(self):
        """table should contain an entry for every item in the catalog."""
        items = {
            "a": make_item("a", "A", value=100, recycles_into={"b": 2}),
            "b": make_item("b", "B", value=50, recycles_into={"c": 3}),
            "c": make_item("c", "C", value=10),
        }

        table = build_deep_recycle_table(items)

        assert len(table) == 3
        assert "a" in table
        assert "b" in table
        assert "c" in table


# -- tests for analyze_sell --


class TestAnalyzeSell:
    """tests for analyze_sell function."""

    def test_item_with_sell_value_greater_than_recycle_value_appears(self):
        """should include item when selling is more profitable."""
        items = {
            "item1": make_item(
                "item1", "profitable sell", value=100, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "material", value=10),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_sell(stash, items, table)

        assert len(result) == 1
        assert result[0].item_id == "item1"
        assert result[0].sell_value == 100
        assert result[0].recycle_value == 30
        assert result[0].action == "sell"

    def test_item_with_sell_value_less_than_recycle_value_does_not_appear(self):
        """should exclude item when recycling is more profitable."""
        items = {
            "item1": make_item(
                "item1", "better recycle", value=10, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "material", value=50),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_sell(stash, items, table)

        assert len(result) == 0

    def test_items_sorted_by_sell_value_descending(self):
        """should sort results by sell_value highest first."""
        items = {
            "item1": make_item("item1", "low value", value=50),
            "item2": make_item("item2", "high value", value=200),
            "item3": make_item("item3", "mid value", value=100),
        }
        table = build_deep_recycle_table(items)

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
            make_stash_item("item3", quantity=1),
        ]

        result = analyze_sell(stash, items, table)

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
        table = build_deep_recycle_table(items)

        stash = [
            make_stash_item("cosmetic", quantity=1),
            make_stash_item("valuable", quantity=1),
        ]

        result = analyze_sell(stash, items, table)

        assert len(result) == 1
        assert result[0].item_id == "valuable"

    def test_items_not_in_catalog_skipped(self):
        """should skip items not found in item catalog."""
        items = {
            "item1": make_item("item1", "known item", value=100),
        }
        table = build_deep_recycle_table(items)

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("unknown", quantity=1),
        ]

        result = analyze_sell(stash, items, table)

        assert len(result) == 1
        assert result[0].item_id == "item1"


# -- tests for analyze_recycle --


class TestAnalyzeRecycle:
    """tests for analyze_recycle function."""

    def test_item_with_recycle_value_greater_than_sell_value_appears(self):
        """should include item when recycling is more profitable."""
        items = {
            "item1": make_item(
                "item1", "profitable recycle", value=10, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "valuable material", value=50),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_recycle(stash, items, table)

        assert len(result) == 1
        assert result[0].item_id == "item1"
        assert result[0].recycle_value == 150
        assert result[0].sell_value == 10
        assert result[0].action == "recycle"

    def test_item_with_recycle_value_less_than_sell_value_does_not_appear(self):
        """should exclude item when selling is more profitable."""
        items = {
            "item1": make_item(
                "item1", "better sell", value=100, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "material", value=10),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_recycle(stash, items, table)

        assert len(result) == 0

    def test_items_with_no_recycles_into_excluded(self):
        """should exclude items with no recycle data."""
        items = {
            "item1": make_item("item1", "no recycle", value=100),
            "item2": make_item(
                "item2", "has recycle", value=10, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "material", value=50),
        }
        table = build_deep_recycle_table(items)

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
        ]

        result = analyze_recycle(stash, items, table)

        assert len(result) == 1
        assert result[0].item_id == "item2"

    def test_items_sorted_by_margin_ascending(self):
        """should sort by margin ascending (most negative = biggest recycle advantage)."""
        items = {
            "item1": make_item(
                "item1", "small margin", value=10, recycles_into={"mat1": 3}
            ),
            "item2": make_item(
                "item2", "large margin", value=5, recycles_into={"mat1": 5}
            ),
            "item3": make_item(
                "item3", "mid margin", value=20, recycles_into={"mat1": 2}
            ),
            "mat1": make_item("mat1", "material", value=30),
        }
        table = build_deep_recycle_table(items)

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
            make_stash_item("item3", quantity=1),
        ]

        result = analyze_recycle(stash, items, table)

        # sorted by margin ascending (most negative first)
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
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("quest_item", quantity=1)]

        quests = {
            "quest1": make_quest(
                "quest1",
                reward_item_ids=[ItemQuantity(item_id="quest_item", quantity=1)],
            ),
        }

        result = analyze_optimize(stash, items, table, quests)

        assert len(result.hold) == 1
        assert result.hold[0].item_id == "quest_item"
        assert result.hold[0].action == "hold"

    def test_items_above_sell_threshold_go_to_sell_list(self):
        """should place high-value sell items in sell list."""
        items = {
            "item1": make_item(
                "item1", "valuable", value=100, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "material", value=10),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("item1", quantity=1)]

        quests = {}

        result = analyze_optimize(stash, items, table, quests)

        assert len(result.sell) == 1
        assert result.sell[0].item_id == "item1"
        assert result.sell[0].action == "sell"
        assert result.total_sell_value == 100

    def test_items_above_recycle_threshold_go_to_recycle_list(self):
        """should place high-value recycle items in recycle list."""
        items = {
            "item1": make_item(
                "item1", "recyclable", value=10, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "valuable material", value=50),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("item1", quantity=1)]

        quests = {}

        result = analyze_optimize(stash, items, table, quests)

        assert len(result.recycle) == 1
        assert result.recycle[0].item_id == "item1"
        assert result.recycle[0].action == "recycle"
        assert result.total_recycle_value == 150

    def test_min_profit_threshold_filters_low_margin_items(self):
        """should exclude items below profit threshold."""
        items = {
            "item1": make_item(
                "item1", "low margin", value=100, recycles_into={"mat1": 3}
            ),
            "item2": make_item(
                "item2", "high margin", value=200, recycles_into={"mat1": 3}
            ),
            "mat1": make_item("mat1", "material", value=30),
        }
        table = build_deep_recycle_table(items)

        stash = [
            make_stash_item("item1", quantity=1),
            make_stash_item("item2", quantity=1),
        ]

        quests = {}
        params = OptimizeParams(min_profit_threshold=50)

        result = analyze_optimize(stash, items, table, quests, params)

        assert len(result.sell) == 1
        assert result.sell[0].item_id == "item2"

    def test_quest_aware_false_disables_hold_set(self):
        """should not hold quest items when quest_aware is False."""
        items = {
            "quest_item": make_item("quest_item", "quest reward", value=100),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("quest_item", quantity=1)]

        quests = {
            "quest1": make_quest(
                "quest1",
                reward_item_ids=[ItemQuantity(item_id="quest_item", quantity=1)],
            ),
        }

        params = OptimizeParams(quest_aware=False)

        result = analyze_optimize(stash, items, table, quests, params)

        assert len(result.hold) == 0
        assert len(result.sell) == 1
        assert result.sell[0].item_id == "quest_item"

    def test_totals_computed_correctly(self):
        """should compute correct totals for sell/recycle/hold."""
        items = {
            "sell1": make_item("sell1", "sell item 1", value=100),
            "sell2": make_item("sell2", "sell item 2", value=200),
            "recycle1": make_item(
                "recycle1", "recycle item", value=10, recycles_into={"mat1": 3}
            ),
            "hold1": make_item("hold1", "hold item", value=50),
            "mat1": make_item("mat1", "material", value=50),
        }
        table = build_deep_recycle_table(items)

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

        result = analyze_optimize(stash, items, table, quests)

        assert result.total_sell_value == 300  # 100 + 200
        assert result.total_recycle_value == 150  # 3 * 50
        assert result.total_hold_count == 1

    def test_quest_objectives_matching_item_names(self):
        """should hold items whose names appear in quest objectives."""
        items = {
            "copper_ore": make_item("copper_ore", "copper ore", value=100),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("copper_ore", quantity=5)]

        quests = {
            "quest1": make_quest(
                "quest1",
                objectives=[{"en": "collect 10 copper ore from the mines"}],
            ),
        }

        result = analyze_optimize(stash, items, table, quests)

        assert len(result.hold) == 1
        assert result.hold[0].item_id == "copper_ore"

    def test_granted_items_placed_in_hold_set(self):
        """should hold items granted by quests."""
        items = {
            "starter_kit": make_item("starter_kit", "starter kit", value=100),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("starter_kit", quantity=1)]

        quests = {
            "quest1": make_quest(
                "quest1",
                granted_item_ids=[ItemQuantity(item_id="starter_kit", quantity=1)],
            ),
        }

        result = analyze_optimize(stash, items, table, quests)

        assert len(result.hold) == 1
        assert result.hold[0].item_id == "starter_kit"


# -- edge cases --


class TestEdgeCases:
    """tests for edge cases and error handling."""

    def test_empty_stash_returns_empty_results(self):
        """should return empty lists for empty stash."""
        items = {"item1": make_item("item1", "test", value=100)}
        table = build_deep_recycle_table(items)
        stash = []
        quests = {}

        result = analyze_optimize(stash, items, table, quests)

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
        table = build_deep_recycle_table(items)

        stash = [
            make_stash_item("cosmetic1", quantity=1),
            make_stash_item("cosmetic2", quantity=1),
        ]

        result = analyze_sell(stash, items, table)

        assert len(result) == 0

    def test_material_not_found_in_items_dict_recycle_value_is_zero(self):
        """should handle missing materials in recycle calculation gracefully."""
        items = {
            "item1": make_item(
                "item1", "mystery item", value=100, recycles_into={"unknown_mat": 5}
            ),
        }
        table = build_deep_recycle_table(items)

        stash = [make_stash_item("item1", quantity=1)]

        result = analyze_recycle(stash, items, table)

        # recycle value should be 0 because material doesn't exist
        # sell value is 100, so selling is better
        assert len(result) == 0

    def test_deep_recycle_beats_shallow_for_intermediate_materials(self):
        """deep recycle should correctly value items with multi-level chains."""
        items = {
            "weapon": make_item(
                "weapon", "Big Gun", value=5000, recycles_into={"mech_comp": 5}
            ),
            "mech_comp": make_item(
                "mech_comp",
                "Mechanical Components",
                value=640,
                recycles_into={"metal": 3, "rubber": 2},
            ),
            "metal": make_item("metal", "Metal Parts", value=75),
            "rubber": make_item("rubber", "Rubber Parts", value=50),
        }
        table = build_deep_recycle_table(items)

        # mech_comp deep recycle: 3*75 + 2*50 = 325
        # but mech_comp sell = 640 > 325, so at weapon level we use 640 per mech_comp
        # weapon deep recycle: 5 * 640 = 3200
        assert table["weapon"] == 3200

        stash = [make_stash_item("weapon", quantity=1)]

        # weapon sell=5000 > deep_recycle=3200 → recommend sell
        result = analyze_sell(stash, items, table)
        assert len(result) == 1
        assert result[0].item_id == "weapon"
        assert result[0].sell_value == 5000
        assert result[0].recycle_value == 3200


# -- tests for find_recycle_sources --


class TestFindRecycleSources:
    """tests for the reverse recycle source finder."""

    def test_direct_source_found(self):
        """should find items that directly recycle into the target."""
        items = {
            "weapon": make_item(
                "weapon", "Weapon", value=100, recycles_into={"metal": 3}
            ),
            "metal": make_item("metal", "Metal Parts", value=50),
        }
        stash = [make_stash_item("weapon", quantity=5, name="Weapon")]

        target, sources = find_recycle_sources("Metal Parts", stash, items)

        assert target is not None
        assert target.id == "metal"
        assert len(sources) == 1
        assert sources[0].item_id == "weapon"
        assert sources[0].yield_per_unit == 3
        assert sources[0].total_yield == 15
        assert sources[0].depth == 1

    def test_recursive_source_found(self):
        """should find items that transitively recycle into the target."""
        items = {
            "weapon": make_item(
                "weapon", "Weapon", value=5000, recycles_into={"mech_comp": 5}
            ),
            "mech_comp": make_item(
                "mech_comp",
                "Mech Comp",
                value=640,
                recycles_into={"metal": 3, "rubber": 2},
            ),
            "metal": make_item("metal", "Metal Parts", value=75),
            "rubber": make_item("rubber", "Rubber Parts", value=50),
        }
        stash = [
            make_stash_item("weapon", quantity=2, name="Weapon"),
            make_stash_item("mech_comp", quantity=10, name="Mech Comp"),
        ]

        target, sources = find_recycle_sources("Metal Parts", stash, items)

        assert target is not None
        assert target.id == "metal"
        assert len(sources) == 2

        # both have total_yield=30, check both present
        source_ids = {s.item_id for s in sources}
        assert source_ids == {"weapon", "mech_comp"}

        mech = next(s for s in sources if s.item_id == "mech_comp")
        assert mech.yield_per_unit == 3
        assert mech.total_yield == 30
        assert mech.depth == 1

        weapon = next(s for s in sources if s.item_id == "weapon")
        assert weapon.yield_per_unit == 15
        assert weapon.total_yield == 30
        assert weapon.depth == 2

    def test_chain_names_correct(self):
        """should build correct chain path from source to target."""
        items = {
            "weapon": make_item(
                "weapon", "Big Gun", value=5000, recycles_into={"mech_comp": 5}
            ),
            "mech_comp": make_item(
                "mech_comp",
                "Mech Comp",
                value=640,
                recycles_into={"metal": 3},
            ),
            "metal": make_item("metal", "Metal Parts", value=75),
        }
        stash = [make_stash_item("weapon", quantity=1, name="Big Gun")]

        _, sources = find_recycle_sources("Metal Parts", stash, items)

        assert len(sources) == 1
        assert sources[0].chain == ["Big Gun", "Mech Comp", "Metal Parts"]

    def test_no_match_returns_none(self):
        """should return None target when query matches nothing."""
        items = {
            "metal": make_item("metal", "Metal Parts", value=50),
        }
        stash = [make_stash_item("metal", quantity=5)]

        target, sources = find_recycle_sources("Nonexistent Item", stash, items)

        assert target is None
        assert sources == []

    def test_no_stash_items_produce_target(self):
        """should return empty sources when nothing in stash recycles into target."""
        items = {
            "weapon": make_item(
                "weapon", "Weapon", value=100, recycles_into={"metal": 3}
            ),
            "metal": make_item("metal", "Metal Parts", value=50),
        }
        # stash has metal but not weapon
        stash = [make_stash_item("metal", quantity=5)]

        target, sources = find_recycle_sources("Metal Parts", stash, items)

        assert target is not None
        assert target.id == "metal"
        assert len(sources) == 0

    def test_case_insensitive_name_match(self):
        """should match target name case-insensitively."""
        items = {
            "weapon": make_item(
                "weapon", "Weapon", value=100, recycles_into={"metal": 3}
            ),
            "metal": make_item("metal", "Metal Parts", value=50),
        }
        stash = [make_stash_item("weapon", quantity=1)]

        target, sources = find_recycle_sources("metal parts", stash, items)

        assert target is not None
        assert target.id == "metal"
        assert len(sources) == 1

    def test_substring_name_match(self):
        """should match target by substring when no exact match."""
        items = {
            "weapon": make_item(
                "weapon", "Weapon", value=100, recycles_into={"metal": 3}
            ),
            "metal": make_item("metal", "Metal Parts", value=50),
        }
        stash = [make_stash_item("weapon", quantity=1)]

        target, sources = find_recycle_sources("Metal", stash, items)

        assert target is not None
        assert target.id == "metal"
        assert len(sources) == 1

    def test_three_depth_chain(self):
        """should follow 3-deep recycle chains."""
        items = {
            "top": make_item(
                "top", "Top Item", value=1000, recycles_into={"mid": 2}
            ),
            "mid": make_item(
                "mid", "Mid Item", value=500, recycles_into={"low": 4}
            ),
            "low": make_item(
                "low", "Low Item", value=100, recycles_into={"base": 3}
            ),
            "base": make_item("base", "Base Mat", value=10),
        }
        stash = [make_stash_item("top", quantity=1, name="Top Item")]

        target, sources = find_recycle_sources("Base Mat", stash, items)

        assert target is not None
        assert len(sources) == 1
        assert sources[0].item_id == "top"
        # 2 * 4 * 3 = 24
        assert sources[0].yield_per_unit == 24
        assert sources[0].depth == 3
        assert sources[0].chain == ["Top Item", "Mid Item", "Low Item", "Base Mat"]

    def test_empty_query_returns_none(self):
        """should return None for empty query string."""
        items = {"metal": make_item("metal", "Metal Parts", value=50)}
        stash = []

        target, sources = find_recycle_sources("", stash, items)

        assert target is None
        assert sources == []

    def test_multiple_sources_sorted_by_total_yield(self):
        """should sort sources by total_yield descending."""
        items = {
            "a": make_item("a", "Item A", value=100, recycles_into={"target": 2}),
            "b": make_item("b", "Item B", value=100, recycles_into={"target": 10}),
            "c": make_item("c", "Item C", value=100, recycles_into={"target": 5}),
            "target": make_item("target", "Target", value=50),
        }
        stash = [
            make_stash_item("a", quantity=3, name="Item A"),  # total: 6
            make_stash_item("b", quantity=1, name="Item B"),  # total: 10
            make_stash_item("c", quantity=4, name="Item C"),  # total: 20
        ]

        _, sources = find_recycle_sources("Target", stash, items)

        assert len(sources) == 3
        assert sources[0].item_id == "c"  # 20
        assert sources[1].item_id == "b"  # 10
        assert sources[2].item_id == "a"  # 6
