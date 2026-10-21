#!/usr/bin/env python3
"""Rules for the redesigned desk index.

The index is a navigation block, so these tests protect the things a reader and a
search engine both depend on: every tool keeps its link, its number, its name and
its icon; each group owns a full row instead of occupying a card slot; the block
stays keyboard-usable and calm on small screens.
"""
from __future__ import annotations

import re
import unittest

import desk_index_design as design
import desk_index_redesign as dx

BOARD = {
    "aria": "Calculator desk index", "eyebrow": "Desk index", "title": "Pick a desk",
    "note": "fourteen calculators, grouped by task", "chips": ["No sign-up", "45 countries"],
    "labels": {"open": "Open desk"},
    "groups": [
        {"name": "Borrow & repay", "items": [
            {"href": "#kc-emi", "num": "01", "title": "Loan EMI", "desc": "the world's no. 1 maths",
             "icon": '<svg viewBox="0 0 24 22" aria-hidden="true"><path d="M3 11 L11 4"></path></svg>'},
            {"href": "#kc-af", "num": "02", "title": "Can I afford it?", "desc": "know your ceiling", "icon": ""},
        ]},
        {"name": "Save & invest", "items": [
            {"href": "#kc-sip", "num": "03", "title": "SIP", "desc": "the quiet wealth machine", "icon": ""},
        ]},
    ],
}


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.block = design.render(BOARD)

    def test_group_rows_and_cards(self):
        self.assertEqual(self.block.count('class="dxi-group"'), 2)
        self.assertEqual(self.block.count('class="dxi-card"'), 3)
        self.assertNotIn("pr-index-heading", self.block)
        self.assertNotIn("kc-ilinks", self.block)

    def test_every_group_has_number_name_and_count(self):
        self.assertEqual(self.block.count('class="dxi-gnum"'), 2)
        self.assertEqual(self.block.count('class="dxi-gcount"'), 2)
        self.assertIn("2 desks", self.block)
        self.assertIn("1 desk<", self.block)

    def test_links_numbers_names_and_icons_are_kept(self):
        for item in (x for group in BOARD["groups"] for x in group["items"]):
            self.assertIn(f'href="{item["href"]}"', self.block)
            self.assertIn(f'class="dxi-num">{item["num"]}<', self.block)
            self.assertIn(item["title"].replace("&", "&amp;"), self.block)
            if item["icon"]:
                self.assertIn(design.drawing(item["icon"]), design.drawing(self.block))

    def test_board_is_accessible_and_self_contained(self):
        self.assertIn('aria-label="Calculator desk index"', self.block)
        self.assertIn("dyDeskIndexStyle", self.block)
        self.assertIn("data-dy-desk-index", self.block)
        self.assertIn("prefers-reduced-motion", self.block)
        self.assertIn(":focus-visible", self.block)

    def test_cards_share_one_anatomy(self):
        for part in ("dxi-top", "dxi-num", "dxi-ico", "dxi-name", "dxi-note2", "dxi-foot", "dxi-open", "dxi-arrow"):
            self.assertEqual(self.block.count(f'class="{part}"'), self.block.count('class="dxi-card"'), part)

    def test_responsive_breakpoints_exist(self):
        self.assertIn("@media (max-width:900px)", self.block)
        self.assertIn("@media (max-width:560px)", self.block)
        self.assertIn("auto-fit", self.block)


class ParseTests(unittest.TestCase):
    """The parser must survive the exact markup Blogger currently serves."""

    def test_old_markup_is_read_without_loss(self):
        page = """<div class="post-body"><nav aria-label="Calculator index" class="kc-index">
        <div class="kc-ihead"><b>boardroom index &#183; pick a desk</b><span class="kc-ihint">11 business tools</span></div>
        <div class="kc-ilinks"><a class="pr-index-heading" href="#g1">Operating performance &#8595;</a>
        <a class="kc-icard" href="#kc-be"><span class="kc-inum">01</span><svg viewBox="0 0 24 22"><path d="M4 17 L20 6"></path></svg><span class="kc-it">Break-even</span><span class="kc-id">where losses end</span><span class="kc-igo">&#8594;</span></a>
        </div></nav></div>"""
        current = dx.parse_index(page)
        self.assertEqual(len(current["groups"]), 1)
        self.assertEqual(current["groups"][0]["name"], "Operating performance")
        item = current["groups"][0]["items"][0]
        self.assertEqual((item["num"], item["title"], item["desc"], item["href"]), ("01", "Break-even", "where losses end", "#kc-be"))
        self.assertIn("<svg", item["icon"])

    def test_designed_markup_is_read_back_unchanged(self):
        page = f"<div>{design.render(BOARD)}</div>"
        current = dx.parse_index(page)
        self.assertEqual([g["name"] for g in current["groups"]], ["Borrow & repay", "Save & invest"])
        self.assertEqual(current["groups"][0]["items"][0]["href"], "#kc-emi")
        self.assertEqual(current["groups"][0]["items"][0]["title"], "Loan EMI")

    def test_validation_catches_a_lost_link(self):
        current = dx.parse_index(f"<div>{design.render(BOARD)}</div>")
        broken = design.render(BOARD).replace('href="#kc-sip"', 'href="#gone"')
        issues = dx.validate(broken, current)
        self.assertTrue(any("link lost" in issue for issue in issues))

    def test_validation_catches_a_lost_group(self):
        current = dx.parse_index(f"<div>{design.render(BOARD)}</div>")
        partial = design.render({**BOARD, "groups": BOARD["groups"][:1]})
        issues = dx.validate(partial, current)
        self.assertTrue(any("group count changed" in issue or "card count changed" in issue for issue in issues))

    def test_targets_cover_the_three_desks(self):
        self.assertEqual([t["key"] for t in dx.TARGETS], ["corporate", "snapshot", "calculator"])
        for target in dx.TARGETS:
            self.assertTrue(target["path"].startswith("/p/"))
            self.assertTrue(target["chips"])

    def test_rendered_block_has_no_external_assets(self):
        block = design.render(BOARD)
        self.assertNotIn("http://", block)
        self.assertNotIn("cdn", block.lower())
        self.assertNotIn("googleapis", block)


class IconsAreCentredAndImmune(unittest.TestCase):
    """Why the icons looked knocked out of place, and what the fitting guarantees.

    Blogger keeps the page's earlier index stylesheet in the document, and the icons were copied into
    the new board still carrying `class="kc-iic"`. That dead rule reads
    `.kc-iic{position:absolute;top:9px;right:10px;width:31px;height:28px}`, so every glyph was lifted
    out of its badge and pinned to the card's corner. Fitting also squares the view box around the
    drawing: an icon whose art spans 3 to 23 was squeezed beside one whose art spans 5 to 19, so the
    row of badges could never read as one family.
    """

    HOUSE = ('<svg aria-hidden="true" class="kc-iic" viewBox="0 0 24 22">'
             '<path d="M3 11 L11 4 L19 11 M6 9.2 V18.5 H16 V9.2"></path>'
             '<circle cx="19.6" cy="14.6" r="1.15"></circle>'
             '<circle cx="22.4" cy="18.6" r="1.15"></circle>'
             '<path d="M18.6 19.6 L23 13.4"></path></svg>')
    BARS = ('<svg aria-hidden="true" class="kc-iic" viewBox="0 0 24 22">'
            '<path d="M4 19 v-6 M9 19 v-10 M14 19 v-7 M19 19 V5 M3 19 h18"></path></svg>')
    GLOBE = ('<svg aria-hidden="true" class="kc-iic" viewBox="0 0 24 22"><circle cx="12" cy="11" r="7.5"></circle>'
             '<path d="M4.5 11 h15 M12 3.5 c3 3.4 3 11.6 0 15 M12 3.5 c-3 3.4 -3 11.6 0 15"></path></svg>')

    def box(self, markup):
        return [float(v) for v in re.search(r'viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"', markup).groups()]

    def test_the_dead_page_class_and_fixed_size_cannot_travel_with_the_icon(self):
        for raw in (self.HOUSE, self.BARS, self.GLOBE):
            head = design.fit_icon(raw).split(">")[0]
            self.assertNotIn("kc-iic", head)
            self.assertNotIn("width=", head)
            self.assertNotIn("height=", head)
            self.assertIn('preserveAspectRatio="xMidYMid meet"', head)

    def test_the_box_is_square_and_holds_every_point_the_glyph_draws(self):
        for raw in (self.HOUSE, self.BARS, self.GLOBE):
            fitted = design.fit_icon(raw)
            left, top, width, height = self.box(fitted)
            self.assertAlmostEqual(width, height, places=3, msg="a square box centres the glyph")
            for x, y in design.icon_points(fitted):
                self.assertGreaterEqual(x, left + 0.4, "the drawing is inside its own box")
                self.assertLessEqual(x, left + width - 0.4)
                self.assertGreaterEqual(y, top + 0.4)
                self.assertLessEqual(y, top + height - 0.4)

    def test_relative_curves_are_resolved_before_the_box_is_measured(self):
        # `c3 3.4 3 11.6 0 15` ends fifteen units below where it started: reading its numbers as
        # absolute coordinates would have placed the box near the bottom of the page instead.
        points = design.icon_points(self.GLOBE)
        self.assertIn((12.0, 18.5), [(round(x, 3), round(y, 3)) for x, y in points])

    def test_the_glyph_is_bigger_than_it_was(self):
        css = design.CSS
        self.assertIn(".dxi-ico{display:inline-flex", css)
        self.assertIn("clamp(44px,4.6vw,52px)", css, "the badge grew from 36px")
        self.assertIn("clamp(26px,2.9vw,32px)", css, "the glyph grew from 21px")
        self.assertNotIn("overflow:visible", css, "nothing may be painted outside the badge")
        self.assertIn("stroke-width:var(--dxi-sw,1.9)", css, "weight stays even at any box size")

    def test_fitting_twice_changes_nothing(self):
        for raw in (self.HOUSE, self.BARS, self.GLOBE):
            once = design.fit_icon(raw)
            self.assertEqual(design.fit_icon(once), once)

    def test_an_icon_with_nothing_to_measure_keeps_its_own_view_box(self):
        fallback = design.fit_icon('<svg viewBox="0 0 24 22"><rect fill="#000"/></svg>')
        self.assertIn("viewBox=", fallback)


class RowsEndSquarely(unittest.TestCase):
    """Each group is given the column count that wastes the fewest places.

    `auto-fit` gave every group as many tracks as the container could hold, so three cards at five
    tracks left a hole, and five cards at four left a row of one - the ragged bottom edge the owner
    saw. Fewest rows first, then fewest empty places, then widest: that is the whole rule.
    """

    def test_the_column_counts(self):
        self.assertEqual([design.layout_for(n)[0] for n in range(1, 11)], [1, 2, 3, 4, 3, 3, 4, 4, 3, 4])

    def test_no_row_of_a_real_group_ends_in_a_hole(self):
        for count in (1, 2, 3, 4, 6, 9):
            wide = design.layout_for(count)[0]
            self.assertEqual((wide - count % wide) % wide, 0, f"{count} cards at {wide} columns")

    def test_a_group_carries_its_own_counts_and_a_phone_rule_for_odd_rows(self):
        block = design.render(BOARD)
        self.assertIn('--dxi-cols:2;--dxi-cols-mid:2', block)
        self.assertIn('data-odd="1"', block, "one card left over at phone width should span the row")
        self.assertIn(".dxi-grid[data-odd=\"1\"] .dxi-card:last-child{grid-column:1/-1}", block)

    def test_the_grid_uses_the_count_it_asked_for(self):
        self.assertIn("repeat(var(--dxi-cols,4)", design.CSS)
        self.assertIn("repeat(var(--dxi-cols-mid,3)", design.CSS)


class CountsAreReadNotRemembered(unittest.TestCase):
    """The handwritten note used to assert a number this file had memorised."""

    def test_no_target_claims_a_number_of_its_own(self):
        # a count claim is a number standing in front of the thing being counted; "one board" and
        # "one tape" are the sentences' own nouns and must not be caught by this
        words = (r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
                 r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|\d+)\s+"
                 r"(tool|tools|desk|desks|calculator|calculators)\b")
        for target in dx.TARGETS:
            self.assertIn("{total}", target["note"], target["key"])
            stripped = target["note"].replace("{total}", "")
            self.assertIsNone(re.search(words, stripped),
                              f"{target['key']} hard-codes a count in '{target['note']}'")

    def test_the_note_agrees_with_the_count_chip(self):
        board = {**BOARD, "note": "{total} calculators, grouped by task",
                 "groups": [{"name": "G", "items": [{"href": f"#x{i}", "num": f"{i:02d}"} for i in range(15)]}]}
        block = design.render(board)
        self.assertIn("fifteen calculators, grouped by task", block)
        self.assertIn('<b>15</b> desks', block)

    def test_a_note_without_the_placeholder_is_left_alone(self):
        self.assertIn("fourteen calculators, grouped by task", design.render(BOARD))

    def test_count_words_cover_a_realistic_page(self):
        self.assertEqual(design.count_word(0), "zero")
        self.assertEqual(design.count_word(31), "31")


class IconsSurviveTheRebuild(unittest.TestCase):
    """The validator must still catch a lost glyph now that the tag is rebuilt."""

    def test_a_clean_rebuild_passes(self):
        current = dx.parse_index(f"<div>{design.render(BOARD)}</div>")
        self.assertEqual(dx.validate(design.render(BOARD), current), [])

    def test_a_stripped_glyph_is_reported(self):
        current = dx.parse_index(f"<div>{design.render(BOARD)}</div>")
        block = design.render(BOARD).replace('<path d="M3 11 L11 4"></path>', "")
        issues = dx.validate(block, current)
        self.assertTrue(any("icon lost" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
