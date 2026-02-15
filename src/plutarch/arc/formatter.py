"""discord table formatter for arc raiders stash commands.

produces unicode box-drawing tables inside discord code blocks (monospace).
designed to fit within discord embed description limits (4096 chars).
uses ansi escape codes for colored output in discord ```ansi code blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from plutarch.arc.models import Recommendation

# -- ansi color code constants --

ANSI_BOLD_BLUE = "1;34"
ANSI_RED = "0;31"
ANSI_GREEN = "0;32"


def _margin_color(value: str) -> str | None:
    """Return ansi color code based on margin sign.

    Args:
        value: raw cell text (e.g. "+1,440", "-600", "0")

    Returns:
        ansi code string or None for no coloring
    """
    if value.startswith("+"):
        return ANSI_GREEN
    if value.startswith("-"):
        return ANSI_RED
    return None


@dataclass
class TableSpec:
    """bundled table layout specification (headers, alignment, widths, colors)."""

    headers: list[str]
    alignments: list[str]
    max_widths: list[int]
    cell_colors: list[str | Callable[[str], str | None] | None] = field(
        default_factory=list
    )


# -- table geometry constants --

# column fixed widths for recommendation tables
COL_ITEM_WIDTH = 20
COL_QTY_WIDTH = 5
COL_SELL_WIDTH = 9
COL_RCL_WIDTH = 9
COL_MARGIN_WIDTH = 9

# -- pagination limits for optimize layout (5 columns, 4 colored) --
# visual line width: 20 + 5 + 9 + 9 + 9 = 52 content + 6 pipes + 10 padding = 68
# ansi overhead per row: 4 colored columns * 11 chars = 44
# data row: 68 + 44 + 1 (newline) = 113 chars
# separator: 68 + 1 = 69 chars
# fixed chrome: 8 (```ansi\n) + 69*4 (borders/header) + 3 (```) = 287
# footer (worst case): 64 chars
# with footer: 287 + 64 + 113N + 69(N-1) <= 4096 => 282 + 182N <= 4096 => N = 20
# without footer: 287 - 69 + 182N <= 4096 => 218 + 182N <= 4096 => N = 21
OPT_MAX_ROWS_WITH_FOOTER = 20
OPT_MAX_ROWS_PER_EMBED = 21

# -- pagination limits for sell/recycle layout (3 columns, 3 colored) --
# visual line width: 20 + 9 + 9 = 38 content + 4 pipes + 6 padding = 48
# ansi overhead per row: 3 colored columns * 11 chars = 33
# data row: 48 + 33 + 1 (newline) = 82 chars
# separator: 48 + 1 = 49 chars
# fixed chrome: 8 (```ansi\n) + 49*4 (borders/header) + 3 (```) = 207
# footer (worst case): 64 chars
# with footer: 207 + 64 + 82N + 49(N-1) <= 4096 => 222 + 131N <= 4096 => N = 29
# without footer: 207 - 49 + 131N <= 4096 => 158 + 131N <= 4096 => N = 30
SELL_RCL_MAX_ROWS_WITH_FOOTER = 29
SELL_RCL_MAX_ROWS_PER_EMBED = 30

# -- legacy constants (kept for backwards compatibility with existing tests) --
# these match the old non-colored 5-column layout char budget
MAX_ROWS_WITH_FOOTER = 27
MAX_ROWS_PER_EMBED = 28


def _truncate(text: str, max_width: int) -> str:
    """Truncate text with ellipsis if it exceeds max_width.

    Args:
        text: string to potentially truncate
        max_width: maximum allowed width

    Returns:
        original or truncated string
    """
    if len(text) <= max_width:
        return text
    return text[: max_width - 1] + "\u2026"


def _format_number(value: int) -> str:
    """Format integer with comma thousands separators.

    Args:
        value: integer to format

    Returns:
        comma-formatted string (e.g. "1,200")
    """
    return f"{value:,}"


def _format_signed(value: int) -> str:
    """Format integer with explicit sign and comma separators.

    Args:
        value: integer to format

    Returns:
        signed comma-formatted string (e.g. "+1,440" or "-600")
    """
    if value > 0:
        return f"+{value:,}"
    if value < 0:
        return f"{value:,}"
    return "0"


def _align_cell(text: str, width: int, alignment: str) -> str:
    """Pad a cell value to the given width with the specified alignment.

    Args:
        text: cell content
        width: target column width
        alignment: "l" for left, "r" for right, "c" for center

    Returns:
        padded string
    """
    if alignment == "r":
        return text.rjust(width)
    if alignment == "c":
        return text.center(width)
    return text.ljust(width)


def _process_cells(
    cells: list[str],
    max_widths: list[int | None],
) -> list[str]:
    """Apply truncation to a list of cell values.

    Args:
        cells: raw cell strings
        max_widths: per-column max width (None means no limit)

    Returns:
        processed cell strings with truncation applied
    """
    return [
        _truncate(cell, mw) if mw is not None else cell
        for cell, mw in zip(cells, max_widths, strict=True)
    ]


def _compute_col_widths(
    proc_headers: list[str],
    proc_rows: list[list[str]],
    max_widths: list[int | None],
) -> list[int]:
    """Compute column widths from processed headers and rows.

    when a max_width is set for a column, it is treated as a fixed width
    (not a ceiling) so that per-row char cost is constant and predictable.
    columns without a max_width auto-size to their widest value.

    Args:
        proc_headers: processed header strings
        proc_rows: processed row data
        max_widths: per-column fixed width (None means auto-size)

    Returns:
        list of column widths
    """
    col_widths = []
    for i, header in enumerate(proc_headers):
        if max_widths[i] is not None:
            # fixed width: always use the declared width exactly
            col_widths.append(max_widths[i])
        else:
            # auto-size: fit to widest value
            w = len(header)
            for row in proc_rows:
                if i < len(row):
                    w = max(w, len(row[i]))
            col_widths.append(w)
    return col_widths


def _build_row_line(
    cells: list[str],
    col_widths: list[int],
    alignments: list[str],
    cell_colors: list[str | Callable[[str], str | None] | None] | None = None,
) -> str:
    """Build a single box-drawing row line.

    Args:
        cells: cell values for this row
        col_widths: column widths
        alignments: per-column alignment
        cell_colors: per-column color spec (None, static code, or callable)

    Returns:
        formatted row string like "│ val1 │ val2 │"
    """
    parts = []
    for i, width in enumerate(col_widths):
        raw_val = cells[i] if i < len(cells) else ""
        aligned = _align_cell(raw_val, width, alignments[i])

        # wrap aligned content (including padding) in ansi color codes
        if cell_colors and i < len(cell_colors) and cell_colors[i] is not None:
            color_spec = cell_colors[i]
            code = color_spec(raw_val) if callable(color_spec) else color_spec
            if code:
                aligned = f"\x1b[{code}m{aligned}\x1b[0m"

        parts.append(" " + aligned + " ")
    return "│" + "│".join(parts) + "│"


def _build_separator(
    col_widths: list[int],
    left: str,
    mid: str,
    right: str,
) -> str:
    """Build a horizontal separator line with box-drawing characters.

    Args:
        col_widths: column widths
        left: left corner/tee character
        mid: middle crossing character
        right: right corner/tee character

    Returns:
        separator string like "┌──────┬──────┐"
    """
    return left + mid.join("─" * (w + 2) for w in col_widths) + right


def format_table(
    headers: list[str],
    rows: list[list[str]],
    alignments: list[str] | None = None,
    max_widths: list[int] | None = None,
    cell_colors: list[str | Callable[[str], str | None] | None] | None = None,
) -> str:
    """Build a unicode box-drawing table string.

    Args:
        headers: column header labels
        rows: list of row data (each row is a list of cell strings)
        alignments: per-column alignment ("l", "r", "c"). defaults to "l"
        max_widths: per-column max width ceiling. truncates with ellipsis
        cell_colors: per-column ansi color spec. each entry is None (no color),
            a static ansi code string (e.g. "1;34"), or a callable that takes
            the raw cell value and returns an ansi code or None.

    Returns:
        complete table string with box-drawing borders, no trailing newline
    """
    num_cols = len(headers)
    if alignments is None:
        alignments = ["l"] * num_cols

    # normalize max_widths to list[int | None]
    mw: list[int | None] = list(max_widths) if max_widths else [None] * num_cols

    # apply truncation to headers and cells
    proc_headers = _process_cells(headers, mw)
    proc_rows = [_process_cells(row, mw) for row in rows]

    # compute column widths
    col_widths = _compute_col_widths(proc_headers, proc_rows, mw)

    # build border/separator lines with box-drawing characters
    top_border = _build_separator(col_widths, "┌", "┬", "┐")
    mid_sep = _build_separator(col_widths, "├", "┼", "┤")
    bottom_border = _build_separator(col_widths, "└", "┴", "┘")

    # build header (no colors) and data rows (with colors)
    header_line = _build_row_line(proc_headers, col_widths, alignments)
    data_lines = [
        _build_row_line(row, col_widths, alignments, cell_colors=cell_colors)
        for row in proc_rows
    ]

    # assemble: top border, header, header sep, data rows with separators, bottom
    parts = [top_border, header_line, mid_sep]
    for i, line in enumerate(data_lines):
        parts.append(line)
        if i < len(data_lines) - 1:
            parts.append(mid_sep)
    parts.append(bottom_border)
    return "\n".join(parts)


def format_table_for_embed(  # noqa: PLR0913
    headers: list[str],
    rows: list[list[str]],
    alignments: list[str] | None = None,
    max_widths: list[int] | None = None,
    footer: str | None = None,
    cell_colors: list[str | Callable[[str], str | None] | None] | None = None,
) -> str:
    """Wrap format_table output for discord embed descriptions.

    Args:
        headers: column header labels
        rows: list of row data
        alignments: per-column alignment
        max_widths: per-column max width ceiling
        footer: optional text appended outside the code block
        cell_colors: per-column ansi color spec passed to format_table

    Returns:
        markdown code block containing the table, with optional footer.
        uses ```ansi language tag when cell_colors are provided.
    """
    table = format_table(headers, rows, alignments, max_widths, cell_colors=cell_colors)
    # use ansi code block when colors are active
    lang = "ansi" if cell_colors else ""
    result = f"```{lang}\n{table}\n```"
    if footer:
        result += f"\n{footer}"
    return result


def _embed_from_spec(
    spec: TableSpec,
    rows: list[list[str]],
    footer: str | None = None,
) -> str:
    """Wrap format_table output using a TableSpec.

    Args:
        spec: bundled table layout specification
        rows: list of row data
        footer: optional text appended outside the code block

    Returns:
        markdown code block containing the table
    """
    colors = spec.cell_colors or None
    return format_table_for_embed(
        spec.headers,
        rows,
        spec.alignments,
        spec.max_widths,
        footer=footer,
        cell_colors=colors,
    )


def _recommendation_to_row(rec: Recommendation) -> list[str]:
    """Convert a single recommendation to a table row.

    Args:
        rec: recommendation to convert

    Returns:
        list of cell strings: [name, qty, sell, recycle, margin]
    """
    return [
        rec.name,
        str(rec.quantity),
        _format_number(rec.sell_value),
        _format_number(rec.recycle_value),
        _format_signed(rec.margin),
    ]


def _rec_table_spec() -> TableSpec:
    """Return the table spec for optimize tables (5 columns with ansi colors).

    Returns:
        TableSpec for the optimize layout
    """
    return TableSpec(
        headers=["Item", "Qty", "Sell", "Rcl", "Margin"],
        alignments=["l", "r", "r", "r", "r"],
        max_widths=[
            COL_ITEM_WIDTH,
            COL_QTY_WIDTH,
            COL_SELL_WIDTH,
            COL_RCL_WIDTH,
            COL_MARGIN_WIDTH,
        ],
        cell_colors=[ANSI_BOLD_BLUE, None, ANSI_RED, ANSI_RED, _margin_color],
    )


def _sell_table_spec() -> TableSpec:
    """Return the table spec for sell tables (3 columns with ansi colors).

    Returns:
        TableSpec for the sell layout
    """
    return TableSpec(
        headers=["Item", "Sell", "Margin"],
        alignments=["l", "r", "r"],
        max_widths=[COL_ITEM_WIDTH, COL_SELL_WIDTH, COL_MARGIN_WIDTH],
        cell_colors=[ANSI_BOLD_BLUE, ANSI_RED, _margin_color],
    )


def _recycle_table_spec() -> TableSpec:
    """Return the table spec for recycle tables (3 columns with ansi colors).

    Returns:
        TableSpec for the recycle layout
    """
    return TableSpec(
        headers=["Item", "Rcl", "Margin"],
        alignments=["l", "r", "r"],
        max_widths=[COL_ITEM_WIDTH, COL_RCL_WIDTH, COL_MARGIN_WIDTH],
        cell_colors=[ANSI_BOLD_BLUE, ANSI_RED, _margin_color],
    )


def _sell_rec_to_row(rec: Recommendation) -> list[str]:
    """Convert a recommendation to a sell-layout row with per-unit values.

    Args:
        rec: recommendation to convert

    Returns:
        list of cell strings: [name, sell_per_unit, margin_per_unit]
    """
    per_unit_sell = rec.sell_value // rec.quantity if rec.quantity else 0
    per_unit_margin = rec.margin // rec.quantity if rec.quantity else 0
    return [
        rec.name,
        _format_number(per_unit_sell),
        _format_signed(per_unit_margin),
    ]


def _recycle_rec_to_row(rec: Recommendation) -> list[str]:
    """Convert a recommendation to a recycle-layout row with per-unit values.

    Args:
        rec: recommendation to convert

    Returns:
        list of cell strings: [name, rcl_per_unit, margin_per_unit]
    """
    per_unit_rcl = rec.recycle_value // rec.quantity if rec.quantity else 0
    per_unit_margin = rec.margin // rec.quantity if rec.quantity else 0
    return [
        rec.name,
        _format_number(per_unit_rcl),
        _format_signed(per_unit_margin),
    ]


def format_sell_recommendations(
    recommendations: Sequence[Recommendation],
    *,
    show_all: bool = False,
    command_hint: str = "%arcsell all",
) -> tuple[list[str], bool]:
    """Format sell recommendations into 3-column embed descriptions with per-unit values.

    columns: Item | Sell | Margin (all per-unit, ansi colored)

    Args:
        recommendations: list of recommendations to format
        show_all: if True, paginate across multiple embeds.
                  if False, single embed with truncation footer.
        command_hint: command shown in truncation footer

    Returns:
        tuple of (list of embed descriptions, was_truncated)
    """
    if not recommendations:
        return ["No items to display."], False

    spec = _sell_table_spec()
    all_rows = [_sell_rec_to_row(r) for r in recommendations]

    if not show_all:
        return _format_single_embed_colored(
            spec, all_rows, command_hint, SELL_RCL_MAX_ROWS_WITH_FOOTER
        )

    return (
        _format_multi_embed_colored(spec, all_rows, SELL_RCL_MAX_ROWS_PER_EMBED),
        False,
    )


def format_recycle_recommendations(
    recommendations: Sequence[Recommendation],
    *,
    show_all: bool = False,
    command_hint: str = "%arcrecycle all",
) -> tuple[list[str], bool]:
    """Format recycle recommendations into 3-column embed descriptions with per-unit values.

    columns: Item | Rcl | Margin (all per-unit, ansi colored)

    Args:
        recommendations: list of recommendations to format
        show_all: if True, paginate across multiple embeds.
                  if False, single embed with truncation footer.
        command_hint: command shown in truncation footer

    Returns:
        tuple of (list of embed descriptions, was_truncated)
    """
    if not recommendations:
        return ["No items to display."], False

    spec = _recycle_table_spec()
    all_rows = [_recycle_rec_to_row(r) for r in recommendations]

    if not show_all:
        return _format_single_embed_colored(
            spec, all_rows, command_hint, SELL_RCL_MAX_ROWS_WITH_FOOTER
        )

    return (
        _format_multi_embed_colored(spec, all_rows, SELL_RCL_MAX_ROWS_PER_EMBED),
        False,
    )


def _format_single_embed_colored(
    spec: TableSpec,
    all_rows: list[list[str]],
    command_hint: str,
    max_with_footer: int,
) -> tuple[list[str], bool]:
    """Build single-embed output with ansi colors and optional truncation footer.

    Args:
        spec: bundled table layout specification
        all_rows: all data rows
        command_hint: command shown in truncation footer
        max_with_footer: max rows that fit with a footer line

    Returns:
        tuple of ([embed description], was_truncated)
    """
    truncated = len(all_rows) > max_with_footer
    display_rows = all_rows[:max_with_footer]
    remaining = len(all_rows) - max_with_footer

    footer = None
    if truncated:
        noun = "item" if remaining == 1 else "items"
        footer = (
            f"... and {remaining} more {noun}. use {command_hint} to see everything"
        )

    desc = _embed_from_spec(spec, display_rows, footer=footer)
    return [desc], truncated


def _format_multi_embed_colored(
    spec: TableSpec,
    all_rows: list[list[str]],
    max_per_embed: int,
) -> list[str]:
    """Build multi-embed paginated output with ansi colors.

    Args:
        spec: bundled table layout specification
        all_rows: all data rows
        max_per_embed: max rows per embed page

    Returns:
        list of embed descriptions (one per page)
    """
    pages = []
    for start in range(0, len(all_rows), max_per_embed):
        chunk = all_rows[start : start + max_per_embed]
        desc = _embed_from_spec(spec, chunk)
        pages.append(desc)
    return pages


def format_recommendations(
    recommendations: Sequence[Recommendation],
    *,
    show_all: bool = False,
    command_hint: str = "%arcsell all",
) -> tuple[list[str], bool]:
    """Format recommendations into 5-column embed descriptions with ansi colors.

    uses the optimize layout (Item, Qty, Sell, Rcl, Margin) with per-stack values.

    Args:
        recommendations: list of recommendations to format
        show_all: if True, paginate across multiple embeds.
                  if False, single embed with truncation footer.
        command_hint: command shown in truncation footer (e.g. "%arcsell all")

    Returns:
        tuple of (list of embed descriptions, was_truncated)
        - single-embed mode: up to OPT_MAX_ROWS_WITH_FOOTER rows, footer if needed
        - multi-embed mode: paginated at OPT_MAX_ROWS_PER_EMBED rows, no footer
    """
    if not recommendations:
        return ["No items to display."], False

    spec = _rec_table_spec()
    all_rows = [_recommendation_to_row(r) for r in recommendations]

    if not show_all:
        return _format_single_embed_colored(
            spec, all_rows, command_hint, OPT_MAX_ROWS_WITH_FOOTER
        )

    return (
        _format_multi_embed_colored(spec, all_rows, OPT_MAX_ROWS_PER_EMBED),
        False,
    )


def format_recommendations_with_total(
    recommendations: Sequence[Recommendation],
    *,
    show_all: bool = False,
    command_hint: str = "%arcoptimize all",
) -> tuple[list[str], bool]:
    """Format recommendations with a totals row appended and ansi colors.

    uses the optimize layout (Item, Qty, Sell, Rcl, Margin) with per-stack values.

    Args:
        recommendations: list of recommendations to format
        show_all: if True, paginate across multiple embeds.
                  if False, single embed with truncation.
        command_hint: command shown in truncation footer (e.g. "%arcoptimize all")

    Returns:
        tuple of (list of embed descriptions, was_truncated)
    """
    if not recommendations:
        return ["No items to display."], False

    spec = _rec_table_spec()
    all_rows = [_recommendation_to_row(r) for r in recommendations]

    # compute totals
    total_qty = sum(r.quantity for r in recommendations)
    total_sell = sum(r.sell_value for r in recommendations)
    total_rcl = sum(r.recycle_value for r in recommendations)
    total_margin = sum(r.margin for r in recommendations)

    totals_row = [
        "TOTAL",
        str(total_qty),
        _format_number(total_sell),
        _format_number(total_rcl),
        _format_signed(total_margin),
    ]

    if not show_all:
        # reserve one row for totals
        max_data = OPT_MAX_ROWS_WITH_FOOTER - 1
        truncated = len(all_rows) > max_data
        display_rows = all_rows[:max_data]
        remaining = len(all_rows) - max_data

        display_rows.append(totals_row)

        footer = None
        if truncated:
            noun = "item" if remaining == 1 else "items"
            footer = (
                f"... and {remaining} more {noun}. use {command_hint} to see everything"
            )

        desc = _embed_from_spec(spec, display_rows, footer=footer)
        return [desc], truncated

    return (
        _format_multi_embed_with_total(spec, all_rows, totals_row),
        False,
    )


def _format_multi_embed_with_total(
    spec: TableSpec,
    all_rows: list[list[str]],
    totals_row: list[str],
) -> list[str]:
    """Build multi-embed paginated output with totals on last page and ansi colors.

    Args:
        spec: bundled table layout specification
        all_rows: all data rows
        totals_row: pre-computed totals row

    Returns:
        list of embed descriptions (one per page)
    """
    pages = []
    for start in range(0, len(all_rows), OPT_MAX_ROWS_PER_EMBED):
        chunk = all_rows[start : start + OPT_MAX_ROWS_PER_EMBED]
        is_last = (start + OPT_MAX_ROWS_PER_EMBED) >= len(all_rows)
        if is_last:
            chunk.append(totals_row)
        desc = _embed_from_spec(spec, chunk)
        pages.append(desc)
    return pages
