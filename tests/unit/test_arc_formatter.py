"""tests for arc discord table formatter."""

from plutarch.arc.formatter import (
    MAX_ROWS_PER_EMBED,
    MAX_ROWS_WITH_FOOTER,
    format_recommendations,
    format_recommendations_with_total,
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
    """tests for the basic ascii box table formatter."""

    def test_basic_table_with_headers_and_rows(self):
        """should produce a properly formatted box table."""
        headers = ["Name", "Value"]
        rows = [["Alpha", "100"], ["Beta", "200"]]

        result = format_table(headers, rows)

        lines = result.split("\n")
        # top separator, header, header separator, 2 data rows, bottom separator
        assert len(lines) == 6
        assert lines[0].startswith("+")
        assert lines[0].endswith("+")
        assert "Name" in lines[1]
        assert "Value" in lines[1]
        assert "Alpha" in lines[3]
        assert "Beta" in lines[4]

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
        # extract cell content between pipes
        cell = data_line.split("|")[1]
        assert cell.startswith(" Hi")

    def test_right_alignment(self):
        """right-aligned columns should pad on the left."""
        headers = ["Value"]
        rows = [["42"]]

        result = format_table(headers, rows, alignments=["r"])

        data_line = result.split("\n")[3]
        cell = data_line.split("|")[1]
        # "Value" is 5 chars, "42" right-aligned should have leading spaces
        assert cell.endswith("42 ")
        assert "  42" in cell

    def test_center_alignment(self):
        """center-aligned columns should pad on both sides."""
        headers = ["Header"]
        rows = [["Hi"]]

        result = format_table(headers, rows, alignments=["c"])

        data_line = result.split("\n")[3]
        cell = data_line.split("|")[1]
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
        cell = data_line.split("|")[1].strip()
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
        # should have 4 pipe characters (outer + between columns)
        assert header_line.count("|") == 4

    def test_max_width_caps_column_width(self):
        """max_widths should cap the column width even if content is wider."""
        headers = ["Name"]
        rows = [["ShortName"]]

        result = format_table(headers, rows, max_widths=[5])

        # column should be 5 chars wide, not 9
        sep_line = result.split("\n")[0]
        # +-------+ means 5 + 2 padding = 7 dashes
        assert "+-------+" in sep_line


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


# -- tests for format_recommendations --


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

    def test_single_embed_row_limit(self):
        """single-embed mode should cap at MAX_ROWS_WITH_FOOTER rows and show footer."""
        recs = [make_rec(name=f"Item {i}", item_id=f"item_{i}") for i in range(100)]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert len(descs) == 1
        assert truncated
        expected_remaining = 100 - MAX_ROWS_WITH_FOOTER
        assert f"... and {expected_remaining} more items" in descs[0]

    def test_single_embed_exactly_max_rows_no_truncation(self):
        """exactly MAX_ROWS_WITH_FOOTER items should fit without truncation."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(MAX_ROWS_WITH_FOOTER)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert len(descs) == 1
        assert not truncated

    def test_single_embed_one_over_max_triggers_truncation(self):
        """MAX_ROWS_WITH_FOOTER + 1 items should trigger truncation."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(MAX_ROWS_WITH_FOOTER + 1)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert len(descs) == 1
        assert truncated
        assert "... and 1 more item." in descs[0]

    def test_multi_embed_pagination(self):
        """show_all mode should paginate at MAX_ROWS_PER_EMBED rows per embed."""
        recs = [make_rec(name=f"Item {i}", item_id=f"item_{i}") for i in range(130)]
        descs, truncated = format_recommendations(recs, show_all=True)

        import math

        expected_pages = math.ceil(130 / MAX_ROWS_PER_EMBED)
        assert len(descs) == expected_pages
        assert not truncated

    def test_multi_embed_exactly_max_rows(self):
        """exactly MAX_ROWS_PER_EMBED items should produce 1 page."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(MAX_ROWS_PER_EMBED)
        ]
        descs, truncated = format_recommendations(recs, show_all=True)

        assert len(descs) == 1
        assert not truncated

    def test_multi_embed_one_over_max_rows(self):
        """MAX_ROWS_PER_EMBED + 1 items should produce 2 pages."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(MAX_ROWS_PER_EMBED + 1)
        ]
        descs, truncated = format_recommendations(recs, show_all=True)

        assert len(descs) == 2
        assert not truncated

    def test_footer_text_uses_command_hint(self):
        """truncation footer should use the provided command_hint."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(MAX_ROWS_WITH_FOOTER + 5)
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
            for i in range(MAX_ROWS_WITH_FOOTER + 5)
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
            for i in range(MAX_ROWS_WITH_FOOTER + 1)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert truncated
        assert "1 more item." in descs[0]
        assert "1 more items" not in descs[0]

    def test_footer_plural_items_grammar(self):
        """truncation footer should say 'items' when remaining > 1."""
        recs = [
            make_rec(name=f"Item {i}", item_id=f"item_{i}")
            for i in range(MAX_ROWS_WITH_FOOTER + 3)
        ]
        descs, truncated = format_recommendations(recs, show_all=False)

        assert truncated
        assert "3 more items." in descs[0]


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

        assert len(descs) == 2
        # TOTAL should only be on last page
        assert "TOTAL" not in descs[0]
        assert "TOTAL" in descs[1]

    def test_truncation_footer_uses_command_hint(self):
        """truncation footer should use the provided command_hint."""
        recs = [make_rec(name=f"Item {i}", item_id=f"item_{i}") for i in range(100)]
        descs, truncated = format_recommendations_with_total(
            recs, show_all=False, command_hint="%arcoptimize all"
        )

        assert truncated
        assert "%arcoptimize all" in descs[0]


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

    def test_max_rows_with_footer_fits_in_4096(self):
        """MAX_ROWS_WITH_FOOTER worst-case rows + footer must fit in 4096 chars."""
        recs = [self._worst_case_rec(i) for i in range(MAX_ROWS_WITH_FOOTER + 5)]
        descs, truncated = format_recommendations(
            recs, show_all=False, command_hint="%arcoptimize all"
        )

        assert truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"embed description is {len(descs[0])} chars, exceeds 4096 limit"
        )

    def test_max_rows_per_embed_fits_in_4096(self):
        """MAX_ROWS_PER_EMBED worst-case rows (no footer) must fit in 4096 chars."""
        recs = [self._worst_case_rec(i) for i in range(MAX_ROWS_PER_EMBED)]
        descs, truncated = format_recommendations(recs, show_all=True)

        assert not truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"embed description is {len(descs[0])} chars, exceeds 4096 limit"
        )

    def test_max_rows_with_footer_plus_totals_fits_in_4096(self):
        """MAX_ROWS_WITH_FOOTER worst-case rows + totals + footer must fit."""
        # format_recommendations_with_total reserves one row for totals,
        # so we need enough items to trigger truncation
        recs = [self._worst_case_rec(i) for i in range(MAX_ROWS_WITH_FOOTER + 5)]
        descs, truncated = format_recommendations_with_total(
            recs, show_all=False, command_hint="%arcoptimize all"
        )

        assert truncated
        assert len(descs) == 1
        assert len(descs[0]) <= 4096, (
            f"embed description is {len(descs[0])} chars, exceeds 4096 limit"
        )
