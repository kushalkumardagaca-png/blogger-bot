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
                self.assertIn(item["icon"], self.block)

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


if __name__ == "__main__":
    unittest.main()
