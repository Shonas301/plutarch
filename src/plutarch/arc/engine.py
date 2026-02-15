"""decision engine for arc raiders stash management.

pure logic module — no I/O. takes item catalog, stash data, and quest data,
returns recommendations for selling, recycling, or holding items.
"""

from __future__ import annotations

from plutarch.arc.models import (
    Item,
    OptimizeParams,
    OptimizeResult,
    Quest,
    Recommendation,
    StashItem,
)


def build_deep_recycle_table(items: dict[str, Item]) -> dict[str, int]:
    """Resolve every item's recycle chain to base materials and cache the value.

    recursively follows recycles_into until reaching base materials (items with
    no recycles_into), then sums up the sell values of those base materials.
    the result is the total credit value you'd get by recycling an item all the
    way down and selling the final base materials.

    uses memoization — each item is resolved exactly once.

    Args:
        items: full item catalog

    Returns:
        dict mapping item_id -> deep recycle value per single unit
    """
    table: dict[str, int] = {}

    def _resolve(item_id: str) -> int:
        if item_id in table:
            return table[item_id]

        item = items.get(item_id)
        if not item or not item.recycles_into:
            # base material or unknown — can't recycle further, value is 0
            # (the sell value is tracked separately via item.value)
            table[item_id] = 0
            return 0

        # recurse: for each material we get from recycling, resolve its value.
        # if a material is a base mat (no recycles_into), use its sell price.
        # if it can be recycled further, use the deeper resolved value.
        total = 0
        for mat_id, mat_qty in item.recycles_into.items():
            mat = items.get(mat_id)
            if not mat:
                continue
            mat_deep = _resolve(mat_id)
            # use whichever is higher: selling the material or recycling it further
            mat_value = max(mat.value, mat_deep)
            total += mat_value * mat_qty

        table[item_id] = total
        return total

    for item_id in items:
        _resolve(item_id)

    return table


def _build_recommendation(
    stash_item: StashItem,
    item: Item,
    recycle_table: dict[str, int],
    action: str,
) -> Recommendation:
    """Build a recommendation from a stash item and its catalog entry.

    Args:
        stash_item: item from user's stash
        item: item catalog entry
        recycle_table: precomputed deep recycle values per item
        action: recommended action ("sell", "recycle", or "hold")

    Returns:
        recommendation with computed values
    """
    sell_value = item.value * stash_item.quantity
    recycle_value = recycle_table.get(stash_item.item_id, 0) * stash_item.quantity
    margin = sell_value - recycle_value

    return Recommendation(
        item_id=stash_item.item_id,
        name=item.name.get("en", stash_item.name),  # prefer english name
        quantity=stash_item.quantity,
        sell_value=sell_value,
        recycle_value=recycle_value,
        margin=margin,
        action=action,
    )


def analyze_sell(
    stash: list[StashItem],
    items: dict[str, Item],
    recycle_table: dict[str, int],
) -> list[Recommendation]:
    """Analyze which items should be sold instead of recycled.

    returns items where selling nets more credits than the deep recycle value
    (recursed to base materials), sorted by total sell value descending.
    excludes items with zero value (cosmetics/trinkets).

    Args:
        stash: user's stash items
        items: full item catalog
        recycle_table: precomputed deep recycle values per item

    Returns:
        list of sell recommendations, sorted by sell_value descending
    """
    recommendations = []

    for stash_item in stash:
        if stash_item.item_id not in items:
            continue

        item = items[stash_item.item_id]

        # skip zero-value items (cosmetics, trinkets)
        if item.value == 0:
            continue

        sell_value = item.value * stash_item.quantity
        recycle_value = recycle_table.get(stash_item.item_id, 0) * stash_item.quantity

        # only include if selling is better
        if sell_value > recycle_value:
            recommendations.append(
                _build_recommendation(stash_item, item, recycle_table, "sell")
            )

    # sort by sell value descending (highest value items first)
    recommendations.sort(key=lambda r: r.sell_value, reverse=True)
    return recommendations


def analyze_recycle(
    stash: list[StashItem],
    items: dict[str, Item],
    recycle_table: dict[str, int],
) -> list[Recommendation]:
    """Analyze which items should be recycled instead of sold.

    returns items where the deep recycle value (recursed to base materials) nets
    more than selling directly, sorted by recycle margin descending (biggest
    advantage first). excludes items with no recycle data.

    Args:
        stash: user's stash items
        items: full item catalog
        recycle_table: precomputed deep recycle values per item

    Returns:
        list of recycle recommendations, sorted by margin ascending (most
        negative margin = biggest recycle advantage)
    """
    recommendations = []

    for stash_item in stash:
        if stash_item.item_id not in items:
            continue

        item = items[stash_item.item_id]

        # skip items with no recycle data
        if not item.recycles_into:
            continue

        sell_value = item.value * stash_item.quantity
        recycle_value = recycle_table.get(stash_item.item_id, 0) * stash_item.quantity

        # only include if recycling is better
        if recycle_value > sell_value:
            recommendations.append(
                _build_recommendation(stash_item, item, recycle_table, "recycle")
            )

    # sort by margin ascending (most negative = biggest recycle advantage)
    recommendations.sort(key=lambda r: r.margin)
    return recommendations


def _build_quest_hold_set(quests: dict[str, Quest], items: dict[str, Item]) -> set[str]:
    """Build a set of item_ids that are needed for incomplete quests.

    scans quest reward_item_ids and granted_item_ids for item references.

    Args:
        quests: quest catalog
        items: item catalog for name matching

    Returns:
        set of item_ids to hold for quests
    """
    hold_set = set()

    for quest in quests.values():
        # add items granted by quests
        for item_qty in quest.granted_item_ids:
            hold_set.add(item_qty.item_id)

        # add items rewarded by quests
        for item_qty in quest.reward_item_ids:
            hold_set.add(item_qty.item_id)

        # scan objectives for item name matches
        # objectives are LocalizedString dicts with locale -> text
        for objective in quest.objectives:
            objective_text = objective.get("en", "").lower()
            # check if any item name appears in the objective text
            for item_id, item in items.items():
                item_name = item.name.get("en", "").lower()
                if item_name and item_name in objective_text:
                    hold_set.add(item_id)

    return hold_set


def analyze_optimize(
    stash: list[StashItem],
    items: dict[str, Item],
    recycle_table: dict[str, int],
    quests: dict[str, Quest],
    params: OptimizeParams | None = None,
) -> OptimizeResult:
    """Greedy optimizer for entire stash.

    step 1: build hold set — items needed for incomplete quests
    step 2: for remaining items, compare sell_value vs deep recycle_value
    step 3: greedy assignment — pick whichever action yields more credits
    step 4: return three lists (sell, recycle, hold) + summary totals

    Args:
        stash: user's stash items
        items: full item catalog
        recycle_table: precomputed deep recycle values per item
        quests: quest catalog
        params: tunable parameters for the optimizer

    Returns:
        optimize result with sell/recycle/hold lists and totals
    """
    if params is None:
        params = OptimizeParams()

    sell_recs = []
    recycle_recs = []
    hold_recs = []
    total_sell_value = 0
    total_recycle_value = 0

    # step 1: build hold set from quests
    hold_set = set()
    if params.quest_aware:
        hold_set = _build_quest_hold_set(quests, items)

    # step 2 & 3: process each stash item
    for stash_item in stash:
        if stash_item.item_id not in items:
            continue

        item = items[stash_item.item_id]

        # check if item should be held
        if stash_item.item_id in hold_set:
            rec = _build_recommendation(stash_item, item, recycle_table, "hold")
            hold_recs.append(rec)
            continue

        # compute values
        sell_value = item.value * stash_item.quantity
        recycle_value = recycle_table.get(stash_item.item_id, 0) * stash_item.quantity
        margin = abs(sell_value - recycle_value)

        # skip items below profit threshold
        if margin < params.min_profit_threshold:
            continue

        # greedy decision: pick whichever yields more credits
        if sell_value > recycle_value:
            rec = _build_recommendation(stash_item, item, recycle_table, "sell")
            sell_recs.append(rec)
            total_sell_value += sell_value
        elif recycle_value > sell_value:
            rec = _build_recommendation(stash_item, item, recycle_table, "recycle")
            recycle_recs.append(rec)
            total_recycle_value += recycle_value
        # if equal, default to sell (arbitrary tiebreaker)
        else:
            rec = _build_recommendation(stash_item, item, recycle_table, "sell")
            sell_recs.append(rec)
            total_sell_value += sell_value

    # sort results for better presentation
    sell_recs.sort(key=lambda r: r.sell_value, reverse=True)
    recycle_recs.sort(key=lambda r: r.margin)
    hold_recs.sort(key=lambda r: r.name)

    return OptimizeResult(
        sell=sell_recs,
        recycle=recycle_recs,
        hold=hold_recs,
        total_sell_value=total_sell_value,
        total_recycle_value=total_recycle_value,
        total_hold_count=len(hold_recs),
    )
