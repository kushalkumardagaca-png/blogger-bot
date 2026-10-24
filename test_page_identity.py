import datetime as dt
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import page_identity  # noqa: E402


class NumberedAddresses(unittest.TestCase):
    """The `_0123456789` tail is a create that should have been an update, and it is detectable."""

    def test_the_collision_tail_is_recognised_and_a_clean_address_is_left_alone(self):
        self.assertEqual(page_identity.numbered_slug("/p/about-us_02080501126.html"), "_02080501126")
        self.assertEqual(page_identity.numbered_slug("/p/about-us.html"), "")
        self.assertEqual(page_identity.numbered_slug(""), "")

    def test_an_existing_name_is_updated_and_only_a_new_name_is_created(self):
        pages = [{"id": "9", "title": "Global Snapshot", "url": "https://dailyyield.blogspot.com/p/global-snapshot.html"}]
        page, action = page_identity.assert_creatable(pages, title="Global Snapshot")
        self.assertEqual((action, page["id"]), ("update", "9"), "a second copy of an existing name is how a numbered address is born")
        page, action = page_identity.assert_creatable(pages, title="Money Atlas")
        self.assertEqual((action, page), ("create", None), "a genuinely new name must still be creatable")

    def test_the_path_is_matched_before_the_title(self):
        pages = [{"id": "1", "title": "Markets Today", "url": "https://x/p/markets-today.html"},
                 {"id": "2", "title": "Markets Today - Archive", "url": "https://x/p/old.html"}]
        self.assertEqual(page_identity.find_page(pages, title="Markets Today", path="/p/old.html")["id"], "2")


class DatesInDeskNames(unittest.TestCase):
    """Owner's instruction, 24 October 2026: "yes, date in desk names"."""

    def test_the_named_and_addressed_form_both_carry_the_day(self):
        day = dt.date(2026, 10, 24)
        title = page_identity.edition_title("Markets Today", day)
        slug = page_identity.slug_for("Markets Today", day)
        self.assertEqual(title, "Markets Today - 24 October 2026")
        self.assertEqual(slug, "markets-today-2026-10-24")
        self.assertTrue(page_identity.edition_identity_is_dated(title, slug, day))

    def test_an_undated_edition_is_refused(self):
        self.assertFalse(page_identity.edition_identity_is_dated("Markets Today", "markets-today-2026-10-24",
                                                                  dt.date(2026, 10, 24)))
        self.assertFalse(page_identity.edition_identity_is_dated("Markets Today - 24 October 2026", "markets-today",
                                                                  dt.date(2026, 10, 24)))

    def test_the_americas_convention_of_two_days_still_counts(self):
        run, market = dt.date(2026, 10, 25), dt.date(2026, 10, 24)
        title = f"Americas Finance News - 24 October 2026"
        self.assertTrue(page_identity.edition_identity_is_dated(title, "americas-finance-news-2026-10-25",
                                                                 market, run))

    def test_the_pipeline_enforces_it_where_the_identity_is_built(self):
        source = (ROOT / "news_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("page_identity.edition_identity_is_dated", source,
                      "the daily desk edition rule must be enforced in the builder, not hoped for")
        self.assertIn("import page_identity", source)


if __name__ == "__main__":
    unittest.main()
