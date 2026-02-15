"""shared dataclasses used across multiple arc api endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field

# -- shared primitives --

LocalizedString = dict[str, str]
"""multilingual text keyed by locale code (en, de, fr, ja, etc.)."""

RecipeMap = dict[str, int]
"""item_id -> quantity mapping used for recipes, recycling, salvage."""


@dataclass
class ItemQuantity:
    """an item reference with a count, used in rewards, requirements, etc."""

    item_id: str
    quantity: int


# -- response envelope (authenticated endpoints) --


@dataclass
class Meta:
    """metadata included in every authenticated api response."""

    request_id: str


@dataclass
class ApiError:
    """error body returned on 4xx/5xx responses."""

    code: str
    message: str


@dataclass
class ErrorResponse:
    """full error envelope from the api."""

    error: ApiError
    meta: Meta


# -- /api/items --


@dataclass
class ItemEffect:
    """a single effect on an item (e.g. duration, damage)."""

    value: str
    labels: LocalizedString = field(default_factory=dict)


@dataclass
class Item:
    """a game item from GET /api/items."""

    id: str
    name: LocalizedString
    description: LocalizedString
    type: str
    rarity: str
    value: int
    weight_kg: float
    stack_size: int
    image_filename: str
    updated_at: str
    effects: dict[str, ItemEffect] = field(default_factory=dict)
    craft_bench: str | None = None
    recipe: RecipeMap = field(default_factory=dict)
    recycles_into: RecipeMap = field(default_factory=dict)
    salvages_into: RecipeMap = field(default_factory=dict)


@dataclass
class ItemsResponse:
    """GET /api/items — all game items."""

    version: str
    generated_at: str
    items: list[Item]
    item_count: int


# -- /api/quests --


@dataclass
class Quest:
    """a quest from GET /api/quests."""

    id: str
    name: LocalizedString
    description: LocalizedString
    trader: str
    objectives: list[LocalizedString]
    reward_item_ids: list[ItemQuantity]
    xp: int
    previous_quest_ids: list[str]
    next_quest_ids: list[str]
    updated_at: str
    slug: str
    map: list[str] = field(default_factory=list)
    objectives_one_round: bool = False
    video_url: str | None = None
    other_requirements: list[str] = field(default_factory=list)
    granted_item_ids: list[ItemQuantity] = field(default_factory=list)


@dataclass
class QuestsResponse:
    """GET /api/quests — all quests."""

    version: str
    generated_at: str
    last_updated: str
    quests: dict[str, Quest]
    total_quests: int


# -- /api/hideout --


@dataclass
class HideoutLevel:
    """a single upgrade level for a hideout module."""

    level: int
    requirement_item_ids: list[ItemQuantity]


@dataclass
class HideoutModule:
    """a hideout module from GET /api/hideout."""

    id: str
    name: LocalizedString
    max_level: int
    levels: list[HideoutLevel]


@dataclass
class HideoutResponse:
    """GET /api/hideout — all hideout modules."""

    version: str
    generated_at: str
    last_updated: str
    hideout_modules: dict[str, HideoutModule]
    total_modules: int


# -- /api/projects --


@dataclass
class ProjectPhase:
    """a single phase within a project."""

    name: LocalizedString
    phase: int
    requirement_item_ids: list[ItemQuantity]


@dataclass
class Project:
    """a project from GET /api/projects."""

    id: str
    disabled: bool
    name: LocalizedString
    description: LocalizedString
    phases: list[ProjectPhase]


@dataclass
class ProjectsResponse:
    """GET /api/projects — all projects."""

    version: str
    generated_at: str
    projects: dict[str, Project]
    total_projects: int


# -- /api/v2/user/profile --


@dataclass
class UserProfile:
    """user profile data from GET /api/v2/user/profile."""

    user_id: str
    username: str
    player_level: int
    member_since: str


@dataclass
class UserProfileResponse:
    """GET /api/v2/user/profile — authenticated."""

    data: UserProfile
    meta: Meta


# -- /api/v2/user/stash --


@dataclass
class StashItem:
    """a single item in the user's stash."""

    item_id: str
    name: str
    quantity: int
    slot_index: int


@dataclass
class StashCurrencies:
    """currency balances in the user's stash."""

    credits: int
    cred: int
    raider_tokens: int
    xp: int


@dataclass
class StashSlots:
    """stash capacity info."""

    used: int
    max: int


@dataclass
class Pagination:
    """pagination metadata for paginated endpoints."""

    page: int
    per_page: int
    total: int
    total_pages: int


@dataclass
class StashData:
    """inner data for GET /api/v2/user/stash."""

    items: list[StashItem]
    currencies: StashCurrencies
    slots: StashSlots
    pagination: Pagination
    synced_at: str


@dataclass
class UserStashResponse:
    """GET /api/v2/user/stash — authenticated."""

    data: StashData
    meta: Meta


# -- /api/v2/user/loadout --


@dataclass
class LoadoutSlot:
    """a single equipment slot in the user's loadout."""

    item_id: str | None
    name: str | None
    quantity: int
    slot_index: int
    durability_percent: int


@dataclass
class SlotCounts:
    """capacity of each loadout section."""

    backpack: int
    quick_items: int
    safe_pocket: int
    augmented_slots: int


@dataclass
class Loadout:
    """the user's full loadout."""

    augment: LoadoutSlot | None
    shield: LoadoutSlot
    weapon1: LoadoutSlot
    weapon2: LoadoutSlot
    backpack: list[LoadoutSlot]
    quick_items: list[LoadoutSlot]
    safe_pocket: list[LoadoutSlot]
    augmented_slots: list[LoadoutSlot]
    slot_counts: SlotCounts


@dataclass
class LoadoutData:
    """inner data for GET /api/v2/user/loadout."""

    loadout: Loadout
    synced_at: str


@dataclass
class UserLoadoutResponse:
    """GET /api/v2/user/loadout — authenticated."""

    data: LoadoutData
    meta: Meta


# -- /api/v2/user/quests (500 from api — shape estimated from spec) --


@dataclass
class UserQuestProgress:
    """a single quest's completion status for the user."""

    quest_id: str
    completed: bool


@dataclass
class UserQuestsData:
    """inner data for GET /api/v2/user/quests."""

    quests: list[UserQuestProgress]
    synced_at: str


@dataclass
class UserQuestsResponse:
    """GET /api/v2/user/quests — authenticated.

    note: endpoint currently returns 500; shape is estimated from spec.
    """

    data: UserQuestsData
    meta: Meta


# -- /api/v2/user/hideout (500 from api — shape estimated from spec) --


@dataclass
class UserHideoutModule:
    """a single hideout module's upgrade progress for the user."""

    module_id: str
    current_level: int


@dataclass
class UserHideoutData:
    """inner data for GET /api/v2/user/hideout."""

    modules: list[UserHideoutModule]
    synced_at: str


@dataclass
class UserHideoutResponse:
    """GET /api/v2/user/hideout — authenticated.

    note: endpoint currently returns 500; shape is estimated from spec.
    """

    data: UserHideoutData
    meta: Meta


# -- /api/v2/user/projects (500 from api — shape estimated from spec) --


@dataclass
class UserProjectPhase:
    """a single project phase's completion status for the user."""

    phase: int
    completed: bool


@dataclass
class UserProjectProgress:
    """a single project's phase completion for the user."""

    project_id: str
    phases: list[UserProjectPhase]


@dataclass
class UserProjectsData:
    """inner data for GET /api/v2/user/projects."""

    projects: list[UserProjectProgress]
    synced_at: str


@dataclass
class UserProjectsResponse:
    """GET /api/v2/user/projects — authenticated.

    note: endpoint currently returns 500; shape is estimated from spec.
    """

    data: UserProjectsData
    meta: Meta


# -- decision engine dataclasses --


@dataclass
class OptimizeParams:
    """tunable parameters for the greedy stash optimizer."""

    quest_aware: bool = True
    min_profit_threshold: int = 0
    include_hideout: bool = False
    include_projects: bool = False


@dataclass
class Recommendation:
    """a single item recommendation from the decision engine."""

    item_id: str
    name: str  # english name from item catalog
    quantity: int
    sell_value: int  # total sell value (value * quantity)
    recycle_value: int  # total recycle value
    margin: int  # sell_value - recycle_value (positive = sell better)
    action: str  # "sell", "recycle", or "hold"


@dataclass
class OptimizeResult:
    """result of the greedy stash optimizer."""

    sell: list[Recommendation]
    recycle: list[Recommendation]
    hold: list[Recommendation]
    total_sell_value: int
    total_recycle_value: int
    total_hold_count: int
