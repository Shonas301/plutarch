"""tests for arc discord table formatter."""

import math

from plutarch.arc.formatter import (
    ANSI_BOLD_BLUE,
    ANSI_GREEN,
    ANSI_RED,
    MAX_ROWS_PER_EMBED,
    MAX_ROWS_WITH_FOOTER,
    OPT_MAX_ROWS_PER_EMBED,
    OPT_MAX_ROWS_WITH_FOOTER,
    SELL_RCL_MAX_ROWS_PER_EMBED,
    SELL_RCL_MAX_ROWS_WITH_FOOTER,
    _margin_color,
    format_recommendations,
    format_recommendations_with_total,
    format_recycle_recommendations,
    format_sell_recommendations,
    format_table,
    format_table_for_embed,
)
from plutarch.arc.models import Recommendation

# -- fixture helpers --


def make_rec(
    name: str = "Test Item",
    quantity: int = 1,
    sell_value: int = 100,
    recycle_value: int = 50,
    margin: int = 50,
    action: str = "sell",
    item_id: str = "test_item",
) -> Recommendation:
    """helper to build Recommendation objects for tests.

    Args:
        name: item name
        quantity: item count
        sell_value: total sell value
        recycle_value: total recycle value
        margin: sell_value - recycle_value
        action: "sell", "recycle", or "hold"
        item_id: item identifier

    Returns:
        Recommendation instance
    """
    return Recommendation(
        item_id=item_id,
        name=name,
        quantity=quantity,
        sell_value=sell_value,
        recycle_value=recycle_value,
        margin=margin,
        action=action,
    )


# -- tests for format_table --


class TestFormatTable:
    """tests for the unicode box-drawing table formatter."""

    def test_basic_table_with_headers_and_rows(self):
        """should produce a properly formatted box-drawing table."""
        headers = ["Name", "Value"]
        rows = [["Alpha", "100"], ["Beta", "200"]]

        result = format_table(headers, rows)

        lines = result.split("\n")
        # top border, header, header sep, row, sep, row, bottom border = 7
        assert len(lines) == 7
        assert lines[0].startswith("┌")
        assert lines[0].endswith("┐")
        assert lines[-1].startswith("└")
        assert lines[-1].endswith("┘")
        assert "Name" in lines[1]
        assert "Value" in lines[1]
        assert "Alpha" in lines[3]
        assert "Beta" in lines[5]

    def test_row_separators_between_data_rows(self):
        """should have separator lines between every data row."""
        headers = ["Name", "Value"]
        rows = [["A", "1"], ["B", "2"], ["C", "3"]]

        result = format_table(headers, rows)

        lines = result.split("\n")
        # 9 lines: top, header, hdr_sep, A, sep, B, sep, C, bottom
        assert len(lines) == 9
        # separators between data rows use ├ and ┤
        assert lines[4].startswith("├")
        assert lines[4].endswith("┤")
        assert lines[6].startswith("├")
        assert lines[6].endswith("┤")

    def test_single_data_row_no_mid_separator(self):
        """single data row should have no separator between data rows."""
        headers = ["X"]
        rows = [["1"]]

        result = format_table(headers, rows)

        lines = result.split("\n")
        # 5 lines: top, header, hdr_sep, data, bottom
        assert len(lines) == 5
        assert lines[0].startswith("┌")
        assert lines[2].startswith("├")
        assert lines[4].startswith("└")

    def test_no_trailing_newline(self):
        """table output should not end with a newline."""
        headers = ["A"]
        rows = [["x"]]

        result = format_table(headers, rows)

        assert not result.endswith("\n")

    def test_left_alignment_default(self):
        """columns should be left-aligned by default."""
        headers = ["Name"]
        rows = [["Hi"]]

        result = format_table(headers, rows)

        # "Name" is 4 chars wide, "Hi" should be left-padded with spaces on right
        data_line = result.split("\n")[3]
        # extract cell content between box-drawing pipes
        cell = data_line.split("│")[1]
        assert cell.startswith(" Hi")

    def test_right_alignment(self):
        """right-aligned columns should pad on the left."""
        headers = ["Value"]
        rows = [["42"]]

        result = format_table(headers, rows, alignments=["r"])

        data_line = result.split("\n")[3]
        cell = data_line.split("│")[1]
        # "Value" is 5 chars, "42" right-aligned should have leading spaces
        assert cell.endswith("42 ")
        assert "  42" in cell

    def test_center_alignment(self):
        """center-aligned columns should pad on both sides."""
        headers = ["Header"]
        rows = [["Hi"]]

        result = format_table(headers, rows, alignments=["c"])

        data_line = result.split("\n")[3]
        cell = data_line.split("│")[1]
        # "Hi" centered in 6-char-wide column
        assert "Hi" in cell

    def test_item_name_truncation_with_ellipsis(self):
        """cells exceeding max_width should be truncated with ellipsis."""
        headers = ["Name"]
        rows = [["This Is A Very Long Item Name That Exceeds Limit"]]

        result = format_table(headers, rows, max_widths=[10])

        data_line = result.split("\n")[3]
        # should contain truncated text with ellipsis
        assert "\u2026" in data_line
        # the truncated text should be at most 10 chars
        cell = data_line.split("│")[1].strip()
        assert len(cell) <= 10

    def test_column_width_auto_sizes_to_widest_value(self):
        """columns should be wide enough for the widest value."""
        headers = ["X"]
        rows = [["Short"], ["Much Longer Value"]]

        result = format_table(headers, rows)

        lines = result.split("\n")
        # all lines should be the same width
        widths = {len(line) for line in lines}
        assert len(widths) == 1

    def test_multiple_columns(self):
        """table with multiple columns should have correct separators."""
        headers = ["A", "B", "C"]
        rows = [["1", "2", "3"]]

        result = format_table(headers, rows)

        header_line = result.split("\n")[1]
        # should have 4 box-drawing pipe characters (outer + between columns)
        assert header_line.count("│") == 4

    def test_max_width_caps_column_width(self):
        """max_widths should cap the column width even if content is wider."""
        headers = ["Name"]
        rows = [["ShortName"]]

        result = format_table(headers, rows, max_widths=[5])

        # column should be 5 chars wide, not 9
        top_line = result.split("\n")[0]
        # ┌───────┐ means 5 + 2 padding = 7 horizontal lines
        assert "┌───────┐" in top_line

    def test_box_drawing_characters_correct(self):
        """should use correct box-drawing characters for each position."""
        headers = ["A", "B"]
        rows = [["1", "2"], ["3", "4"]]

        result = format_table(headers, rows)

        lines = result.split("\n")
        # top border: ┌ ... ┬ ... ┐
        assert lines[0][0] == "┌"
        assert lines[0][-1] == "┐"
        assert "┬" in lines[0]
        # header separator: ├ ... ┼ ... ┤
        assert lines[2][0] == "├"
        assert lines[2][-1] == "┤"
        assert "┼" in lines[2]
        # row separator (same as header sep)
        assert lines[4][0] == "├"
        assert lines[4][-1] == "┤"
        assert "┼" in lines[4]
        # bottom border: └ ... ┴ ... ┘
        assert lines[-1][0] == "└"
        assert lines[-1][-1] == "┘"
        assert "┴" in lines[-1]
        # data rows use │
        assert lines[1][0] == "│"
        assert lines[1][-1] == "│"
        # horizontal lines use ─
        assert "─" in lines[0]


# -- tests for ansi color codes --


class TestAnsiColors:
    """tests for ansi escape code coloring in table output."""

    def test_static_color_wraps_cell(self):
        """static color spec should wrap the aligned cell content in ansi codes."""
        headers = ["Name"]
        rows = [["Test"]]

        result = format_table(headers, rows, cell_colors=["1;34"])

        # data row should contain ansi escape sequences
        data_line = result.split("\n")[3]
        assert "\x1b[1;34m" in data_line
        assert "\x1b[0m" in data_line

    def test_callable_color_receives_raw_value(self):
        """callable color spec should receive the raw cell value."""
        received_values = []

        def capture_color(value: str) -> str | None:
            received_values.append(value)
            return "0;32"

        headers = ["Val"]
        rows = [["hello"]]
        format_table(headers, rows, cell_colors=[capture_color])

        assert "hello" in received_values

    def test_callable_returning_none_skips_color(self):
        """callable returning None should not add ansi codes."""
        headers = ["Val"]
        rows = [["test"]]

        result = format_table(headers, rows, cell_colors=[lambda _v: None])

        data_line = result.split("\n")[3]
        assert "\x1b[" not in data_line

    def test_none_color_spec_skips_column(self):
        """None in cell_colors should leave that column uncolored."""
        headers = ["A", "B"]
        rows = [["x", "y"]]

        result = format_table(headers, rows, cell_colors=[None, "0;31"])

        data_line = result.split("\n")[3]
        # only second column should have color
        assert "\x1b[0;31m" in data_line
        # split by pipe to check first column has no escape
        parts = data_line.split("│")
        assert "\x1b[" not in parts[1]  # first data cell (between pipes 0 and 1)

    def test_headers_are_not_colored(self):
        """header row should not contain ansi escape codes."""
        headers = ["Name"]
        rows = [["Test"]]

        result = format_table(headers, rows, cell_colors=["1;34"])

        header_line = result.split("\n")[1]
        assert "\x1b[" not in header_line

    def test_border_chars_not_colored(self):
        """box-drawing border characters should not be inside ansi escape sequences."""
        headers = ["X"]
        rows = [["A"]]

        result = format_table(headers, rows, cell_colors=["0;31"])

        data_line = result.split("\n")[3]
        # borders should be outside escape sequences
        assert data_line.startswith("│")
        assert data_line.endswith("│")

    def test_margin_color_positive_returns_green(self):
        """_margin_color should return green code for positive values."""
        assert _margin_color("+1,440") == ANSI_GREEN

    def test_margin_color_negative_returns_red(self):
        """_margin_color should return red code for negative values."""
        assert _margin_color("-600") == ANSI_RED

    def test_margin_color_zero_returns_none(self):
        """_margin_color should return None for zero value."""
        assert _margin_color("0") is None


# -- tests for format_table_for_embed --


class TestFormatTableForEmbed:
    """tests for the discord embed wrapper."""

    def test_wraps_in_code_block(self):
        """output should be wrapped in triple backtick code block."""
        headers = ["X"]
        rows = [["1"]]

        result = format_table_for_embed(headers, rows)

        assert result.startswith("```\n")
        assert result.endswith("\n```")

    def test_ansi_code_block_when_colors_provided(self):
        """output should use ```ansi when cell_colors are provided."""
        headers = ["X"]
        rows = [["1"]]

        result = format_table_for_embed(headers, rows, cell_colors=["1;34"])

        assert result.startswith("```ansi\n")
        assert result.endswith("\n```")

    def test_plain_code_block_when_no_colors(self):
        """output should use plain ``` when no cell_colors are provided."""
        headers = ["X"]
        rows = [["1"]]

        result = format_table_for_embed(headers, rows)

        assert result.startswith("```\n")
        assert "```ansi" not in result

    def test_footer_appended_outside_code_block(self):
        """footer text should appear after the closing code fence."""
        headers = ["X"]
        rows = [["1"]]

        result = format_table_for_embed(headers, rows, footer="more items...")

        assert result.endswith("\nmore items...")
        # code block should be closed before footer
        assert "```\nmore items..." in result

    def test_no_footer_when_none(self):
        """should not append anything when footer is None."""
        headers = ["X"]
        rows = [["1"]]

        result = format_table_for_embed(headers, rows, footer=None)

        assert result.endswith("\n```")


# -- tests for number formatting --


class TestNumberFormatting:
    """tests for number comma formatting and signed margins."""

    def test_comma_formatting_in_recommendations(self):
        """sell and recycle values should be comma-formatted."""
        rec = make_rec(sell_value=1200, recycle_value=3500, margin=-2300)
        descs, _ = format_recommendations([rec])

        assert "1,200" in descs[0]
        assert "3,500" in descs[0]

    def test_positive_margin_has_plus_sign(self):
        """positive margins should show + prefix."""
        rec = make_rec(margin=1440)
        descs, _ = format_recommendations([rec])

        assert "+1,440" in descs[0]

    def test_negative_margin_has_minus_sign(self):
        """negative margins should show - prefix."""
        rec = make_rec(margin=-600)
        descs, _ = format_recommendations([rec])

        assert "-600" in descs[0]

    def test_zero_margin(self):
        """zero margin should display as 0."""
        rec = make_rec(margin=0)
        descs, _ = format_recommendations([rec])

        # should contain "0" in the margin column
        assert "0" in descs[0]


# -- tests for format_recommendations (optimize 5-column layout) --


class TestFormatRecommendations:
    """tests for recommendation formatting into embed descriptions."""

    def test_empty_recommendations(self):
        """should return 'No items to display.' for empty list."""
        descs, truncated = format_recommendations([])

        assert len(descs) == 1
        assert descs[0] == "No items to display."
        assert not truncated

    def test_single_recommendation(self):
        """should produce a single embed with one data row."""
        rec = make_rec(
            name="Metal Parts", quantity=5, sell_value=375, recycle_value=0, margin=375
        )
        descs, truncated = format_recommendations([rec])

        assert len(descs) == 1
        assert not truncated
        assert "Metal Parts" in descs[0]
        assert "375" in descs[0]

    def test_recommendation_table_has_correct_headers(self):
        """table should include Item, Qty, Sell, Rcl, Margin headers."""
        rec = make_rec()
        descs, _ = format_recommendations([rec])

        assert "Item" in descs[0]
        assert "Qty" in descs[0]
        assert "Sell" in descs[0]
        assert "Rcl" in descs[0]
        assert "Margin" in descs[0]

    def test_long_item_name_truncated(self):
        """item names over 20 chars should be truncated with ellipsis."""
        rec = make_rec(name="Mechanical Components Extra Long Name")
        descs, _ = format_recommendations([rec])

        assert "\u2026" in descs[0]

    def test_output_uses_ansi_code_block(self):
        """format_recommendations should produce ```ansi code blocks."""
        rec = make_rec()
        descs, _ = format_recommendations([rec])

        assert descs[0].startswith("```ansi\n")

    def test_output_contains_ansi_escape_codes(self):
        """data rows should contain ansi escape sequences for coloring."""
        rec = make_rec()
        descs, _ = format_recommendations([rec])

        assert "\x1b[" in descs[0]

    def test_single_embed_row_limit(self):
        """single-embed mode should cap at OPT_MAX_ROWS_WITH_FOOTER rows."""
        recs = [make_rec(name=f"Item {i}", item_id=f"item_{i}") for i in range(100)]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert len(descs) == 1
        assert truncated
        expected_remaining = 100 - OPT_MAX_ROWS_WITH_FOOTER
        assert f"... and {expected_remaining} more items" in descs[0]

    def test_single_embed_exactly_max_rows_no_truncation(self):
        """exactly OPT_MAX_ROWS_WITH_FOOTER items should fit without truncation."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_WITH_FOOTER)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert len(descs) == 1
        assert not truncated

    def test_single_embed_one_over_max_triggers_truncation(self):
        """OPT_MAX_ROWS_WITH_FOOTER + 1 items should trigger truncation."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_WITH_FOOTER + 1)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert len(descs) == 1
        assert truncated
        assert "... and 1 more item." in descs[0]

    def test_multi_embed_pagination(self):
        """show_all mode should paginate at OPT_MAX_ROWS_PER_EMBED rows per embed."""
        recs = [make_rec(name=f"Item {i}", item_id=f"item_{i}") for i in range(130)]
        descs, truncated = format_recommendations(recs, show_all=True)

        expected_pages = math.ceil(130 / OPT_MAX_ROWS_PER_EMBED)
        assert len(descs) == expected_pages
        assert not truncated

    def test_multi_embed_exactly_max_rows(self):
        """exactly OPT_MAX_ROWS_PER_EMBED items should produce 1 page."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_PER_EMBED)
        ]
        descs, truncated = format_recommendations(recs, show_all=True)

        assert len(descs) == 1
        assert not truncated

    def test_multi_embed_one_over_max_rows(self):
        """OPT_MAX_ROWS_PER_EMBED + 1 items should produce 2 pages."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_PER_EMBED + 1)
        ]
        descs, truncated = format_recommendations(recs, show_all=True)

        assert len(descs) == 2
        assert not truncated

    def test_footer_text_uses_command_hint(self):
        """truncation footer should use the provided command_hint."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_recommendations(
            recs, show_all=False, command_hint="%arcsell all"
        )

        assert truncated
        assert "%arcsell all" in descs[0]

    def test_footer_text_with_arcrecycle_hint(self):
        """truncation footer should reflect arcrecycle command_hint."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_recommendations(
            recs, show_all=False, command_hint="%arcrecycle all"
        )

        assert truncated
        assert "%arcrecycle all" in descs[0]

    def test_footer_singular_item_grammar(self):
        """truncation footer should say 'item' (not 'items') when remaining == 1."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_WITH_FOOTER + 1)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert truncated
        assert "1 more item." in descs[0]
        assert "1 more items" not in descs[0]

    def test_footer_plural_items_grammar(self):
        """truncation footer should say 'items' when remaining > 1."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(OPT_MAX_ROWS_WITH_FOOTER + 3)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert truncated
        assert "3 more items." in descs[0]


# -- tests for format_sell_recommendations --


class TestFormatSellRecommendations:
    """tests for sell-specific 3-column formatter."""

    def test_empty_recommendations(self):
        """should return 'No items to display.' for empty list."""
        descs, truncated = format_sell_recommendations([])

        assert descs[0] == "No items to display."
        assert not truncated

    def test_has_sell_headers(self):
        """sell layout should have Item, Sell, Margin headers only."""
        rec = make_rec()
        descs, _ = format_sell_recommendations([rec])

        assert "Item" in descs[0]
        assert "Sell" in descs[0]
        assert "Margin" in descs[0]
        # should not have Qty or Rcl columns
        assert "Qty" not in descs[0]
        assert "Rcl" not in descs[0]

    def test_per_unit_sell_value(self):
        """sell column should show per-unit value (sell_value // quantity)."""
        rec = make_rec(sell_value=2400, quantity=8, recycle_value=800, margin=1600)
        descs, _ = format_sell_recommendations([rec])

        # per-unit sell = 2400 // 8 = 300
        assert "300" in descs[0]

    def test_per_unit_margin_value(self):
        """margin column should show per-unit margin (margin // quantity)."""
        rec = make_rec(sell_value=2400, quantity=8, recycle_value=800, margin=1600)
        descs, _ = format_sell_recommendations([rec])

        # per-unit margin = 1600 // 8 = 200
        assert "+200" in descs[0]

    def test_uses_ansi_code_block(self):
        """sell output should use ```ansi code block."""
        rec = make_rec()
        descs, _ = format_sell_recommendations([rec])

        assert descs[0].startswith("```ansi\n")

    def test_contains_ansi_item_color(self):
        """item name should be colored with bold blue."""
        rec = make_rec()
        descs, _ = format_sell_recommendations([rec])

        assert f"\x1b[{ANSI_BOLD_BLUE}m" in descs[0]

    def test_contains_ansi_sell_color(self):
        """sell value should be colored with red."""
        rec = make_rec()
        descs, _ = format_sell_recommendations([rec])

        assert f"\x1b[{ANSI_RED}m" in descs[0]

    def test_positive_margin_colored_green(self):
        """positive margin should be colored green."""
        rec = make_rec(margin=500)
        descs, _ = format_sell_recommendations([rec])

        assert f"\x1b[{ANSI_GREEN}m" in descs[0]

    def test_negative_margin_colored_red(self):
        """negative margin should be colored red."""
        rec = make_rec(margin=-500, sell_value=50, recycle_value=550)
        descs, _ = format_sell_recommendations([rec])

        # red appears for both sell value column and negative margin
        assert f"\x1b[{ANSI_RED}m" in descs[0]

    def test_zero_margin_not_colored(self):
        """zero margin should not have ansi coloring."""
        rec = make_rec(margin=0, sell_value=100, recycle_value=100)
        descs, _ = format_sell_recommendations([rec])

        # the "0" in the margin column should not be wrapped in green or red
        # check that we can find a plain "0" cell (not preceded by ansi green/red)
        # the zero margin means _margin_color returns None
        output = descs[0]
        # there should be no green escape in the output (only blue for item, red for sell)
        assert f"\x1b[{ANSI_GREEN}m" not in output

    def test_truncation_uses_sell_rcl_constants(self):
        """sell layout should use SELL_RCL_MAX_ROWS_WITH_FOOTER for truncation."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(SELL_RCL_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_sell_recommendations(recs, show_all=False)

        assert truncated
        expected_remaining = len(recs) - SELL_RCL_MAX_ROWS_WITH_FOOTER
        assert f"... and {expected_remaining} more items" in descs[0]

    def test_pagination_uses_sell_rcl_constants(self):
        """sell layout show_all should paginate at SELL_RCL_MAX_ROWS_PER_EMBED."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(SELL_RCL_MAX_ROWS_PER_EMBED + 1)
        ]
        descs, truncated = format_sell_recommendations(recs, show_all=True)

        assert len(descs) == 2
        assert not truncated

    def test_exactly_max_rows_no_truncation(self):
        """exactly SELL_RCL_MAX_ROWS_WITH_FOOTER items should fit without truncation."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(SELL_RCL_MAX_ROWS_WITH_FOOTER)
        ]
        descs, truncated = format_sell_recommendations(recs, show_all=False)

        assert len(descs) == 1
        assert not truncated

    def test_command_hint_in_footer(self):
        """sell footer should use provided command_hint."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(SELL_RCL_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_sell_recommendations(
            recs, show_all=False, command_hint="%arcsell all"
        )

        assert truncated
        assert "%arcsell all" in descs[0]


# -- tests for format_recycle_recommendations --


class TestFormatRecycleRecommendations:
    """tests for recycle-specific 3-column formatter."""

    def test_empty_recommendations(self):
        """should return 'No items to display.' for empty list."""
        descs, truncated = format_recycle_recommendations([])

        assert descs[0] == "No items to display."
        assert not truncated

    def test_has_recycle_headers(self):
        """recycle layout should have Item, Rcl, Margin headers only."""
        rec = make_rec()
        descs, _ = format_recycle_recommendations([rec])

        assert "Item" in descs[0]
        assert "Rcl" in descs[0]
        assert "Margin" in descs[0]
        # should not have Qty or Sell columns
        assert "Qty" not in descs[0]
        assert "Sell" not in descs[0]

    def test_per_unit_recycle_value(self):
        """rcl column should show per-unit value (recycle_value // quantity)."""
        rec = make_rec(sell_value=800, quantity=8, recycle_value=2400, margin=-1600)
        descs, _ = format_recycle_recommendations([rec])

        # per-unit rcl = 2400 // 8 = 300
        assert "300" in descs[0]

    def test_per_unit_margin_value(self):
        """margin column should show per-unit margin (margin // quantity)."""
        rec = make_rec(sell_value=800, quantity=8, recycle_value=2400, margin=-1600)
        descs, _ = format_recycle_recommendations([rec])

        # per-unit margin = -1600 // 8 = -200
        assert "-200" in descs[0]

    def test_uses_ansi_code_block(self):
        """recycle output should use ```ansi code block."""
        rec = make_rec()
        descs, _ = format_recycle_recommendations([rec])

        assert descs[0].startswith("```ansi\n")

    def test_negative_margin_colored_red(self):
        """negative margin (recycling wins) should be colored red."""
        rec = make_rec(margin=-500, sell_value=50, recycle_value=550)
        descs, _ = format_recycle_recommendations([rec])

        assert f"\x1b[{ANSI_RED}m" in descs[0]

    def test_positive_margin_colored_green(self):
        """positive margin (selling wins) should be colored green."""
        rec = make_rec(margin=500, sell_value=550, recycle_value=50)
        descs, _ = format_recycle_recommendations([rec])

        assert f"\x1b[{ANSI_GREEN}m" in descs[0]

    def test_truncation_uses_sell_rcl_constants(self):
        """recycle layout should use SELL_RCL_MAX_ROWS_WITH_FOOTER for truncation."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(SELL_RCL_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_recycle_recommendations(recs, show_all=False)

        assert truncated
        expected_remaining = len(recs) - SELL_RCL_MAX_ROWS_WITH_FOOTER
        assert f"... and {expected_remaining} more items" in descs[0]

    def test_pagination_uses_sell_rcl_constants(self):
        """recycle layout show_all should paginate at SELL_RCL_MAX_ROWS_PER_EMBED."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(SELL_RCL_MAX_ROWS_PER_EMBED + 1)
        ]
        descs, truncated = format_recycle_recommendations(recs, show_all=True)

        assert len(descs) == 2
        assert not truncated

    def test_command_hint_in_footer(self):
        """recycle footer should use provided command_hint."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(SELL_RCL_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_recycle_recommendations(
            recs, show_all=False, command_hint="%arcrecycle all"
        )

        assert truncated
        assert "%arcrecycle all" in descs[0]


# -- tests for format_recommendations_with_total --


class TestFormatRecommendationsWithTotal:
    """tests for recommendation formatting with totals row."""

    def test_empty_recommendations(self):
        """should return 'No items to display.' for empty list."""
        descs, truncated = format_recommendations_with_total([])

        assert descs[0] == "No items to display."
        assert not truncated

    def test_totals_row_present(self):
        """should include a TOTAL row at the bottom."""
        recs = [
            make_rec(
                name="Item A", quantity=3, sell_value=300, recycle_value=100, margin=200
            ),
            make_rec(
                name="Item B", quantity=2, sell_value=200, recycle_value=150, margin=50
            ),
        ]
        descs, _ = format_recommendations_with_total(recs)

        assert "TOTAL" in descs[0]

    def test_totals_values_computed_correctly(self):
        """totals row should sum all quantities, sell, recycle, margin."""
        recs = [
            make_rec(quantity=3, sell_value=300, recycle_value=100, margin=200),
            make_rec(quantity=2, sell_value=200, recycle_value=150, margin=50),
        ]
        descs, _ = format_recommendations_with_total(recs)

        # total qty = 5, total sell = 500, total rcl = 250, total margin = +250
        assert "500" in descs[0]
        assert "250" in descs[0]

    def test_totals_on_last_page_multi_embed(self):
        """in multi-embed mode, totals row should be on the last page only."""
        recs = [make_rec(name=f"Item {i}", item_id=f"item_{i}") for i in range(70)]
        descs, _ = format_recommendations_with_total(recs, show_all=True)

        assert len(descs) >= 2
        # TOTAL should only be on last page
        for page in descs[:-1]:
            assert "TOTAL" not in page
        assert "TOTAL" in descs[-1]

    def test_truncation_footer_uses_command_hint(self):
        """truncation footer should use the provided command_hint."""
        recs = [make_rec(name=f"Item {i}", item_id=f"item_{i}") for i in range(100)]
        descs, truncated = format_recommendations_with_total(
            recs, show_all=False, command_hint="%arcoptimize all"
        )

        assert truncated
        assert "%arcoptimize all" in descs[0]

    def test_uses_ansi_code_block(self):
        """format_recommendations_with_total should produce ```ansi code blocks."""
        rec = make_rec()
        descs, _ = format_recommendations_with_total([rec])

        assert descs[0].startswith("```ansi\n")

    def test_contains_ansi_escape_codes(self):
        """data rows should contain ansi escape sequences."""
        rec = make_rec()
        descs, _ = format_recommendations_with_total([rec])

        assert "\x1b[" in descs[0]


# -- tests for discord embed 4096 char limit --


class TestEmbedCharLimit:
    """tests that formatted output stays within discord's 4096 char embed limit."""

    def _worst_case_rec(self, i: int) -> Recommendation:
        """build a recommendation with worst-case wide data.

        uses 20-char names, large quantities, and large values to maximize
        the per-row character cost.

        Args:
            i: unique index for item_id

        Returns:
            Recommendation with wide data
        """
        return make_rec(
            name="A" * 20,
            quantity=999,
            sell_value=999_999,
            recycle_value=999_999,
            margin=999_999,
            item_id=f"worst_{i}",
        )

    # -- optimize layout (5 columns) --

    def test_opt_max_rows_with_footer_fits_in_4096(self):
        """OPT_MAX_ROWS_WITH_FOOTER worst-case rows + footer must fit in 4096 chars."""
        recs = [self._worst_case_rec(i) for i in range(OPT_MAX_ROWS_WITH_FOOTER + 5)]
        descs, truncated = format_recommendations(
            recs, show_all=False, command_hint="%arcoptimize all"
        )

        assert truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"embed description is {len(descs[0])} chars, exceeds 4096 limit"
        )

    def test_opt_max_rows_per_embed_fits_in_4096(self):
        """OPT_MAX_ROWS_PER_EMBED worst-case rows (no footer) must fit in 4096 chars."""
        recs = [self._worst_case_rec(i) for i in range(OPT_MAX_ROWS_PER_EMBED)]
        descs, truncated = format_recommendations(recs, show_all=True)

        assert not truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"embed description is {len(descs[0])} chars, exceeds 4096 limit"
        )

    def test_opt_max_rows_with_footer_plus_totals_fits_in_4096(self):
        """OPT_MAX_ROWS_WITH_FOOTER worst-case rows + totals + footer must fit."""
        recs = [self._worst_case_rec(i) for i in range(OPT_MAX_ROWS_WITH_FOOTER + 5)]
        descs, truncated = format_recommendations_with_total(
            recs, show_all=False, command_hint="%arcoptimize all"
        )

        assert truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"embed description is {len(descs[0])} chars, exceeds 4096 limit"
        )

    # -- sell layout (3 columns) --

    def test_sell_max_rows_with_footer_fits_in_4096(self):
        """SELL_RCL_MAX_ROWS_WITH_FOOTER worst-case sell rows + footer must fit."""
        recs = [
            self._worst_case_rec(i) for i in range(SELL_RCL_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_sell_recommendations(
            recs, show_all=False, command_hint="%arcsell all"
        )

        assert truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"sell embed is {len(descs[0])} chars, exceeds 4096 limit"
        )

    def test_sell_max_rows_per_embed_fits_in_4096(self):
        """SELL_RCL_MAX_ROWS_PER_EMBED worst-case sell rows (no footer) must fit."""
        recs = [self._worst_case_rec(i) for i in range(SELL_RCL_MAX_ROWS_PER_EMBED)]
        descs, truncated = format_sell_recommendations(recs, show_all=True)

        assert not truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"sell embed is {len(descs[0])} chars, exceeds 4096 limit"
        )

    # -- recycle layout (3 columns) --

    def test_recycle_max_rows_with_footer_fits_in_4096(self):
        """SELL_RCL_MAX_ROWS_WITH_FOOTER worst-case recycle rows + footer must fit."""
        recs = [
            self._worst_case_rec(i) for i in range(SELL_RCL_MAX_ROWS_WITH_FOOTER + 5)
        ]
        descs, truncated = format_recycle_recommendations(
            recs, show_all=False, command_hint="%arcrecycle all"
        )

        assert truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"recycle embed is {len(descs[0])} chars, exceeds 4096 limit"
        )

    def test_recycle_max_rows_per_embed_fits_in_4096(self):
        """SELL_RCL_MAX_ROWS_PER_EMBED worst-case recycle rows (no footer) must fit."""
        recs = [self._worst_case_rec(i) for i in range(SELL_RCL_MAX_ROWS_PER_EMBED)]
        descs, truncated = format_recycle_recommendations(recs, show_all=True)

        assert not truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"recycle embed is {len(descs[0])} chars, exceeds 4096 limit"
        )

    # -- constant values --

    def test_legacy_constants_are_correct(self):
        """verify legacy MAX_ROWS_WITH_FOOTER and MAX_ROWS_PER_EMBED values."""
        assert MAX_ROWS_WITH_FOOTER == 27
        assert MAX_ROWS_PER_EMBED == 28

    def test_opt_constants_are_correct(self):
        """verify OPT_MAX_ROWS_WITH_FOOTER and OPT_MAX_ROWS_PER_EMBED values."""
        assert OPT_MAX_ROWS_WITH_FOOTER == 20
        assert OPT_MAX_ROWS_PER_EMBED == 21

    def test_sell_rcl_constants_are_correct(self):
        """verify SELL_RCL_MAX_ROWS_WITH_FOOTER and SELL_RCL_MAX_ROWS_PER_EMBED values."""
        assert SELL_RCL_MAX_ROWS_WITH_FOOTER == 29
        assert SELL_RCL_MAX_ROWS_PER_EMBED == 30
