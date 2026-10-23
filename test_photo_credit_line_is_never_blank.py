#!/usr/bin/env python3
"""A photograph's licence credit is functional attribution: it must be visible, it may repeat, and it
must never be able to blank a live article's figures again.

These cases were written on 23 October 2026, the morning three Master articles were live with two of
their three photographs credited by an empty anchor - a link to the source file with no words inside it -
because the anti-plagiarism repair had deleted the "repeated" licence credit. The whole-site image-rights
audit called that a gap, the corpus status dropped to WARNING, and the green operating gate then refused
every news desk and every Master slot for the morning: 0 of 21 published, four slots overdue. So the
rules tested here are not decoration. A credit that cannot be read is treated as no credit at all, in
the builder, in the repetition measure, in the live-corpus repair, and at the door before publication.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# harden_live_corpus reads its blog id at import, the way every publisher in this repository does.
import os
os.environ.setdefault("BLOGGER_BLOG_ID", "1")

import content_policy_guard
import editorial_integrity
import master_article_v2
import photo_credit
import publication_preflight
from publication_preflight import assert_publishable

# A real asset this site published, and the rights row its selector recorded for it.
ASSET = ("https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/assets/master/"
         "chancellor-rejects-calls-to-raise-capital/photo-2.jpg")
WIKI = "https://commons.wikimedia.org/wiki/File:City_of_Canterbury_budget_2010%E2%88%922011_067.jpg"


def package_photo(**extra):
    row = {"url": ASSET, "alt": "Illustrative photograph titled: City of Canterbury budget",
           "caption": "Photo: Linda Spashett ( Storye book ) / CC BY 3.0",
           "source_page": WIKI, "license": "CC BY 3.0",
           "license_url": "https://creativecommons.org/licenses/by/3.0",
           "creator": "Linda Spashett ( Storye book )", "width": 1600, "height": 900}
    row.update(extra)
    return row


class TheBuilderNeverRendersABlankCredit(unittest.TestCase):
    def test_a_full_rights_row_renders_the_credit_and_both_links(self):
        figure = master_article_v2.photo(package_photo(), 2)
        caption = re.search(r"<figcaption>(.*?)</figcaption>", figure, re.S).group(1)
        self.assertIn("Photo: Linda Spashett", caption)
        self.assertIn('rel="license noopener"', caption)
        self.assertIn(WIKI, caption)

    def test_a_package_that_lost_its_caption_still_gets_a_real_credit(self):
        # The registry holds the creator and licence for this address, so the figure is credited from the
        # site's own record - not from a template, and not by leaving the anchor empty.
        figure = master_article_v2.photo(package_photo(caption="", license="", license_url="", creator=""), 3)
        caption = re.search(r"<figcaption>(.*?)</figcaption>", figure, re.S).group(1)
        self.assertTrue(photo_credit.caption_is_visible(re.sub(r"<[^>]+>", " ", caption)),
                        f"credit is not readable: {caption!r}")
        self.assertIn("Linda Spashett", caption)

    def test_a_picture_with_no_rights_record_anywhere_is_not_published(self):
        with self.assertRaises(ValueError) as refused:
            master_article_v2.photo({"url": "https://example.org/mystery.png", "caption": "", "alt": "x",
                                     "width": 1600, "height": 900}, 1)
        self.assertIn("no visible rights line", str(refused.exception))


class ARepeatedCreditIsNotPlagiarism(unittest.TestCase):
    """The exact damage of 22 October: three identical credits, one article."""

    def body(self):
        figures = "".join(
            f'<figure class="dy2-photo"><img src="{ASSET.replace("photo-2", f"photo-{n}")}" '
            f'alt="Illustrative photograph titled: City of Canterbury budget 2010 0{n}">'
            f'<figcaption><a href="{WIKI}" rel="noopener" target="_blank">'
            f'Photo: Linda Spashett ( Storye book ) / CC BY 3.0</a> · '
            f'<a href="https://creativecommons.org/licenses/by/3.0" rel="license noopener" '
            f'target="_blank">Licence</a></figcaption></figure>' for n in (1, 2, 3))
        prose = "".join(f'<p>{"Opening context for the reader about capital gains in the United Kingdom " * 6}</p>'
                        for _ in range(3))
        return f"<article class='dy2'>{prose}{figures}</article>"

    def test_the_repetition_repair_leaves_every_caption_intact(self):
        cleaned, removed = editorial_integrity.scrub_repeated_sentences(self.body())
        self.assertEqual(cleaned.count("<figcaption>"), 3, "a figure lost its caption element")
        self.assertEqual(cleaned.count("Photo: Linda Spashett"), 3,
                         "a licence credit was deleted as if it were duplicated reporting")
        self.assertNotIn("></a></figcaption>", cleaned, "an anchor was left with nothing to read")

    def test_the_repeated_paragraph_fall_back_also_spares_captions(self):
        cleaned, removed = editorial_integrity.repair_repeated_prose(self.body())
        self.assertEqual(cleaned.count("Photo: Linda Spashett"), 3)

    def test_the_gate_does_not_count_a_credit_as_a_duplicated_sentence(self):
        issues = content_policy_guard.audit_text("Chancellor rejects calls to raise Capital", self.body(),
                                                 "master-package", False)
        self.assertNotIn("repeated substantive sentence within the content", issues)


class PreflightStopsAnUncaptionedFigure(unittest.TestCase):
    """The measurement the door applies, taken on its own."""

    def body(self, caption_inner):
        figures = "".join(f'<figure class="dy2-photo"><img src="{ASSET.replace("photo-2", f"photo-{n}")}"'
                          f' alt="A photograph">{caption_inner}</figure>' for n in (1, 2, 3))
        return f'<article class="dy2">{figures}</article>'

    def test_an_empty_anchor_counts_as_a_missing_credit(self):
        self.assertEqual(publication_preflight.uncaptioned_photo_figures(
            self.body('<figcaption><a href="' + WIKI + '" rel="noopener"></a></figcaption>')), 3)

    def test_a_readable_credit_counts_as_none(self):
        self.assertEqual(publication_preflight.uncaptioned_photo_figures(
            self.body('<figcaption><a href="' + WIKI + '">Photo: Linda Spashett / CC BY 3.0</a> · '
                      '<a href="https://creativecommons.org/licenses/by/3.0" rel="license">Licence</a>'
                      '</figcaption>')), 0)

    def test_a_caption_that_is_not_a_link_is_still_a_credit(self):
        self.assertEqual(publication_preflight.uncaptioned_photo_figures(
            self.body('<figcaption>Photo: Linda Spashett / CC BY 3.0</figcaption>')), 0)

    def test_the_gate_calls_this_measure_before_it_publishes(self):
        source = (ROOT / "publication_preflight.py").read_text(encoding="utf-8")
        self.assertIn("uncaptioned_photo_figures(content)", source)


class TheLiveCorpusRepairFillsWhatItFinds(unittest.TestCase):
    def test_an_empty_caption_is_repaired_from_the_registry(self):
        import harden_live_corpus
        body = (f'<figure class="dy2-photo"><img src="{ASSET}" alt="A photograph">'
                f'<figcaption><a href="{WIKI}" rel="noopener" target="_blank"></a></figcaption></figure>')
        repaired, count = harden_live_corpus.ensure_figure_rights(body)
        self.assertEqual(count, 1)
        self.assertIn("Photo:", re.sub(r"<[^>]+>", " ", repaired))
        self.assertNotIn("></a></figcaption>", repaired)

    def test_a_figure_that_is_already_credited_is_left_alone(self):
        import harden_live_corpus
        figure = (f'<figure class="dy2-photo"><img src="{ASSET}" alt="A photograph"><figcaption>'
                  f'<a href="{WIKI}" rel="noopener" target="_blank">Photo: Linda Spashett / CC BY 3.0</a>'
                  f'</figcaption></figure>')
        repaired, count = harden_live_corpus.ensure_figure_rights(figure)
        self.assertEqual(count, 0)
        self.assertEqual(repaired, figure)

    def test_a_commons_asset_with_no_registry_row_is_credited_by_its_source_record(self):
        import harden_live_corpus
        thumb = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Datacenter_Server_Racks.jpg/800px-Datacenter_Server_Racks.jpg"
        body = f'<figure><img src="{thumb}" alt="A photograph"></figure>'
        repaired, count = harden_live_corpus.ensure_figure_rights(body)
        self.assertEqual(count, 1)
        self.assertIn("Wikimedia Commons", re.sub(r"<[^>]+>", " ", repaired))
        self.assertIn("commons.wikimedia.org/wiki/File:Datacenter_Server_Racks.jpg", repaired)

    def test_the_rights_entry_still_calls_an_empty_caption_a_gap(self):
        import harden_live_corpus
        row = harden_live_corpus.rights_entry({"id": "1", "url": "x"},
                                              f'<figure><img src="{ASSET}" alt="A photograph">'
                                              f'<figcaption><a href="{WIKI}"></a></figcaption></figure>')
        self.assertFalse(row["complete"])


class TheReleasedScopeCannotDoAnythingElse(unittest.TestCase):
    """The owner released one narrow repair; the freeze still holds everything next to it."""

    def _reload(self, scope):
        import importlib
        import os
        saved = {key: os.environ.get(key) for key in ("APPLY_CORPUS_REMEDIATION", "CORPUS_REPAIR_SCOPE")}
        os.environ["BLOGGER_BLOG_ID"] = "1"
        os.environ["APPLY_CORPUS_REMEDIATION"] = "true"
        os.environ["CORPUS_REPAIR_SCOPE"] = scope
        try:
            import harden_live_corpus
            importlib.reload(harden_live_corpus)
            return harden_live_corpus.APPLY, harden_live_corpus.SCOPE
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_the_released_rights_scope_can_apply_while_the_site_is_frozen(self):
        import site_change_control
        self.assertTrue(site_change_control.is_frozen(), "the freeze must still stand for this to mean anything")
        apply, scope = self._reload("rights")
        self.assertTrue(apply)
        self.assertEqual(scope, "rights")

    def test_full_remediation_stays_held_by_the_freeze(self):
        apply, scope = self._reload("full")
        self.assertFalse(apply, "whole-site remediation must not run while the freeze stands")

    def test_no_apply_request_writes_anything(self):
        import importlib
        import os
        saved = os.environ.get("APPLY_CORPUS_REMEDIATION")
        os.environ["APPLY_CORPUS_REMEDIATION"] = ""
        try:
            import harden_live_corpus
            importlib.reload(harden_live_corpus)
            self.assertFalse(harden_live_corpus.APPLY)
        finally:
            if saved is None:
                os.environ.pop("APPLY_CORPUS_REMEDIATION", None)
            else:
                os.environ["APPLY_CORPUS_REMEDIATION"] = saved

    def test_the_release_names_its_own_scope_and_the_owner_instruction(self):
        policy = json.loads((ROOT / "SITE_CHANGE_POLICY.json").read_text(encoding="utf-8"))
        entry = next((row for row in policy.get("releasedCorrections") or []
                      if row.get("action") == "corpus_figure_rights_repair"), {})
        self.assertTrue(str(entry.get("ownerInstruction", "")).strip())
        self.assertIn("figcaption", str(entry.get("scope", "")))
        self.assertIn("delete", json.dumps(entry.get("limits", {}).get("forbidden", [])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
