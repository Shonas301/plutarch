"""discord table formatter for arc raiders stash commands.

produces unicode box-drawing tables inside discord code blocks (monospace).
designed to fit within discord embed description limits (4096 chars).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from plutarch.arc.models import Recommendation

# -- table geometry constants --

# column fixed widths for recommendation tables
COL_ITEM_WIDTH = 20
COL_QTY_WIDTH = 5
COL_SELL_WIDTH = 9
COL_RCL_WIDTH = 9
COL_MARGIN_WIDTH = 9

# pagination limits (derived from char budget math)
# column content width: 20 + 5 + 9 + 9 + 9 = 52
# box-drawing borders and padding: 6 │ + 5*2 padding spaces = 16
# total line width: 52 + 16 = 68
# per row with newline: 69 chars
#
# fixed chrome (no data rows):
#   ```\n              = 4
#   ┌───...┐\n         = 69  (top border)
#   │ hdr  │\n         = 69  (header row)
#   ├───...┤\n         = 69  (header separator)
#   └───...┘\n         = 69  (bottom border)
#   ```                = 3
#   chrome total:        283
#
# row separators between every data row:
#   for N data rows: N * 69 (data lines) + (N - 1) * 69 (separators) = (2N - 1) * 69
#
# footer (worst case with "%arcoptimize all"):
#   \n + "... and 999 more items. use %arcoptimize all to see everything"
#   = 1 + 63 = 64 chars
#
# embed description limit: 4096 chars
# with footer: 283 + 64 + (2N - 1) * 69 <= 4096 => N <= 27.66 => N = 27
# without footer: 283 + (2N - 1) * 69 <= 4096 => N <= 28.13 => N = 28
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
) -> str:
    """Build a single box-drawing row line.

    Args:
        cells: cell values for this row
        col_widths: column widths
        alignments: per-column alignment

    Returns:
        formatted row string like "│ val1 │ val2 │"
    """
    parts = []
    for i, width in enumerate(col_widths):
        val = cells[i] if i < len(cells) else ""
        parts.append(" " + _align_cell(val, width, alignments[i]) + " ")
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
) -> str:
    """Build a unicode box-drawing table string.

    Args:
        headers: column header labels
        rows: list of row data (each row is a list of cell strings)
        alignments: per-column alignment ("l", "r", "c"). defaults to "l"
        max_widths: per-column max width ceiling. truncates with ellipsis

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

    # build header and data rows
    header_line = _build_row_line(proc_headers, col_widths, alignments)
    data_lines = [_build_row_line(row, col_widths, alignments) for row in proc_rows]

    # assemble: top border, header, header sep, data rows with separators, bottom
    parts = [top_border, header_line, mid_sep]
    for i, line in enumerate(data_lines):
        parts.append(line)
        if i < len(data_lines) - 1:
            parts.append(mid_sep)
    parts.append(bottom_border)
    return "\n".join(parts)


def format_table_for_embed(
    headers: list[str],
    rows: list[list[str]],
    alignments: list[str] | None = None,
    max_widths: list[int] | None = None,
    footer: str | None = None,
) -> str:
    """Wrap format_table output for discord embed descriptions.

    Args:
        headers: column header labels
        rows: list of row data
        alignments: per-column alignment
        max_widths: per-column max width ceiling
        footer: optional text appended outside the code block

    Returns:
        markdown code block containing the table, with optional footer
    """
    table = format_table(headers, rows, alignments, max_widths)
    result = f"```\n{table}\n```"
    if footer:
        result += f"\n{footer}"
    return result


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


def _rec_table_spec() -> tuple[list[str], list[str], list[int]]:
    """Return the standard headers, alignments, max_widths for rec tables.

    Returns:
        tuple of (headers, alignments, max_widths)
    """
    headers = ["Item", "Qty", "Sell", "Rcl", "Margin"]
    alignments = ["l", "r", "r", "r", "r"]
    max_widths = [
        COL_ITEM_WIDTH,
        COL_QTY_WIDTH,
        COL_SELL_WIDTH,
        COL_RCL_WIDTH,
        COL_MARGIN_WIDTH,
    ]
    return headers, alignments, max_widths


def format_recommendations(
    recommendations: Sequence[Recommendation],
    *,
    show_all: bool = False,
    command_hint: str = "%arcsell all",
) -> tuple[list[str], bool]:
    """Format recommendations into embed description strings.

    Args:
        recommendations: list of recommendations to format
        show_all: if True, paginate across multiple embeds.
                  if False, single embed with truncation footer.
        command_hint: command shown in truncation footer (e.g. "%arcsell all")

    Returns:
        tuple of (list of embed descriptions, was_truncated)
        - single-embed mode: up to MAX_ROWS_WITH_FOOTER rows, footer if needed
        - multi-embed mode: paginated at MAX_ROWS_PER_EMBED rows, no footer
    """
    if not recommendations:
        return ["No items to display."], False

    headers, alignments, max_widths = _rec_table_spec()
    all_rows = [_recommendation_to_row(r) for r in recommendations]

    if not show_all:
        return _format_single_embed(
            headers, all_rows, alignments, max_widths, command_hint
        )

    return _format_multi_embed(headers, all_rows, alignments, max_widths), False


def _format_single_embed(
    headers: list[str],
    all_rows: list[list[str]],
    alignments: list[str],
    max_widths: list[int],
    command_hint: str,
) -> tuple[list[str], bool]:
    """Build single-embed output with optional truncation footer.

    Args:
        headers: column headers
        all_rows: all data rows
        alignments: column alignments
        max_widths: column max widths
        command_hint: command shown in truncation footer

    Returns:
        tuple of ([embed description], was_truncated)
    """
    truncated = len(all_rows) > MAX_ROWS_WITH_FOOTER
    display_rows = all_rows[:MAX_ROWS_WITH_FOOTER]
    remaining = len(all_rows) - MAX_ROWS_WITH_FOOTER

    footer = None
    if truncated:
        noun = "item" if remaining == 1 else "items"
        footer = (
            f"... and {remaining} more {noun}. use {command_hint} to see everything"
        )

    desc = format_table_for_embed(
        headers, display_rows, alignments, max_widths, footer=footer
    )
    return [desc], truncated


def _format_multi_embed(
    headers: list[str],
    all_rows: list[list[str]],
    alignments: list[str],
    max_widths: list[int],
) -> list[str]:
    """Build multi-embed paginated output.

    Args:
        headers: column headers
        all_rows: all data rows
        alignments: column alignments
        max_widths: column max widths

    Returns:
        list of embed descriptions (one per page)
    """
    pages = []
    for start in range(0, len(all_rows), MAX_ROWS_PER_EMBED):
        chunk = all_rows[start : start + MAX_ROWS_PER_EMBED]
        desc = format_table_for_embed(headers, chunk, alignments, max_widths)
        pages.append(desc)
    return pages


def format_recommendations_with_total(
    recommendations: Sequence[Recommendation],
    *,
    show_all: bool = False,
    command_hint: str = "%arcoptimize all",
) -> tuple[list[str], bool]:
    """Format recommendations with a totals row appended.

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

    headers, alignments, max_widths = _rec_table_spec()
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
        max_data = MAX_ROWS_WITH_FOOTER - 1
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

        desc = format_table_for_embed(
            headers, display_rows, alignments, max_widths, footer=footer
        )
        return [desc], truncated

    return (
        _format_multi_embed_with_total(
            headers, all_rows, alignments, max_widths, totals_row
        ),
        False,
    )


def _format_multi_embed_with_total(
    headers: list[str],
    all_rows: list[list[str]],
    alignments: list[str],
    max_widths: list[int],
    totals_row: list[str],
) -> list[str]:
    """Build multi-embed paginated output with totals on last page.

    Args:
        headers: column headers
        all_rows: all data rows
        alignments: column alignments
        max_widths: column max widths
        totals_row: pre-computed totals row

    Returns:
        list of embed descriptions (one per page)
    """
    pages = []
    for start in range(0, len(all_rows), MAX_ROWS_PER_EMBED):
        chunk = all_rows[start : start + MAX_ROWS_PER_EMBED]
        is_last = (start + MAX_ROWS_PER_EMBED) >= len(all_rows)
        if is_last:
            chunk.append(totals_row)
        desc = format_table_for_embed(headers, chunk, alignments, max_widths)
        pages.append(desc)
    return pages
