import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import front_page_compaction as compact_module  # noqa: E402

ITEMS = [{"title": "Story %d" % i, "url": "https://dailyyield.blogspot.com/2026/10/story-%d.html" % i,
          "published": (dt.datetime(2026, 10, 24, 20, 0) - dt.timedelta(hours=i)).isoformat() + "Z"}
         for i in range(1, 61)]


def hub_document(items=None, linked=None, with_enh=True):
    """A hub page in the shape the live ones arrived in: the same list in two script blocks, and a visible
    list of anchors that the desk actually renders."""
    items = items if items is not None else ITEMS
    payload = json.dumps(items, separators=(",", ":"))
    anchors = "".join('<a href="%s">%s</a>' % (row["url"], row["title"]) for row in (linked or items[:20]))
    scripts = ('<script>(function(w,d){var items=' + payload +
               ";d.title=items.length})(window,document)</script>")
    if with_enh:
        scripts += "<script>window.ENH_NEWS_SNAPSHOT=" + payload + ";</script>"
    return "<html><head><title>Daily news</title></head><body><h1>Daily news</h1>" + anchors + scripts + "</body></html>"


def reader_links(document):
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", " ", document, flags=re.S | re.I)
    return {m for m in re.findall(r"""href\s*=\s*["']([^"'#]+)["']""", without_scripts)}


class CollapsingThePayload(unittest.TestCase):
    def test_two_copies_become_one_and_the_page_gets_lighter(self):
        document = hub_document()
        self.assertEqual(len(compact_module.payload_spans(document)), 2, "the fixture must carry the bug")
        new_document, report = compact_module.compact(document)
        self.assertTrue(report["changed"], report["reason"])
        self.assertLess(len(new_document), int(len(document) * 0.85))
        self.assertEqual(compact_module.canonical_payload(new_document) is not None, True)
        self.assertEqual(report["bytesSaved"], len(document) - len(new_document))

    def test_the_desk_keeps_everything_it_links_to(self):
        new_document, report = compact_module.compact(hub_document())
        kept = [row["url"] for row in compact_module.canonical_payload(new_document)]
        for row in ITEMS[:20]:
            self.assertIn(row["url"], kept, "a story the page links to was dropped from the list")
        self.assertEqual(reader_links(new_document), reader_links(hub_document()), "a reader link moved")

    def test_both_consumers_still_find_their_name(self):
        new_document, report = compact_module.compact(hub_document())
        self.assertTrue(report["changed"], report["reason"])
        self.assertIn("var items=", new_document)
        self.assertIn("window.ENH_NEWS_SNAPSHOT=", new_document)
        self.assertIn("window.DY_HUB_SNAPSHOT=", new_document)

    def test_a_page_without_a_payload_is_left_exactly_as_found(self):
        document = hub_document().split("<script>")[0] + "</body></html>"
        new_document, report = compact_module.compact(document)
        self.assertFalse(report["changed"])
        self.assertIn("no inline story list", report["reason"])
        self.assertEqual(new_document, document, "an untouched page must come back byte-identical")

    def test_an_edit_that_saves_little_is_refused(self):
        # Three items in a page mostly made of prose: collapsing the copies is true, but it is not worth
        # a write on a live hub, so the controller says so and hands back the original bytes.
        tiny = ITEMS[:3]
        filler = "<p>" + ("The desk reports the tape, the filings and the market's own reaction. " * 900) + "</p>"
        document = hub_document(tiny, linked=tiny).replace("<h1>Daily news</h1>", "<h1>Daily news</h1>" + filler)
        new_document, report = compact_module.compact(document)
        self.assertFalse(report["changed"], report)
        self.assertIn("smaller after collapsing", report["reason"])
        self.assertEqual(new_document, document)

    def test_a_refusal_never_leaves_a_half_written_page(self):
        # `var items` written but never assigned an array: the parser cannot read it back, so the whole
        # edit has to be refused rather than published in the state the repair left it in.
        document = hub_document()
        broken = document.replace("window.ENH_NEWS_SNAPSHOT=[", "window.ENH_NEWS_SNAPSHOT=")
        new_document, report = compact_module.compact(broken)
        self.assertFalse(report["changed"])
        self.assertEqual(new_document, broken)


class BackupsAndGuards(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.directory = Path(tempfile.mkdtemp())
        self.original = compact_module.BACKUP_DIR
        compact_module.BACKUP_DIR = self.directory

    def tearDown(self):
        compact_module.BACKUP_DIR = self.original

    def test_the_before_copy_is_byte_exact_or_the_run_stops(self):
        document = hub_document()
        path = compact_module.backup_page("daily-news", document, stamp="20261024T150000Z")
        self.assertEqual(path.read_text(encoding="utf-8"), document)
        self.assertEqual(path.parent, compact_module.BACKUP_DIR)
        self.assertTrue(path.name.startswith("daily-news-"))

    def test_the_balance_check_runs_on_the_rebuilt_page(self):
        new_document, report = compact_module.compact(hub_document())
        balance = compact_module.balance_report(new_document)
        self.assertEqual(sorted(balance), ["balanceReportOk", "unbalancedTags"])
        self.assertTrue(balance["balanceReportOk"], balance)

    def test_the_job_is_guarded_and_its_owner_release_is_recorded(self):
        source = (ROOT / "front_page_compaction.py").read_text(encoding="utf-8")
        self.assertIn("_dy_stop_if_frozen('front_page_compaction')", source,
                      "the controller must answer to the owner's site-change freeze")
        workflow = (ROOT / ".github/workflows/front_page_compaction.yml").read_text(encoding="utf-8")
        for needle in ("contents: write", "FRONT_PAGE_BACKUP/", "--apply", "test_front_page_compaction"):
            self.assertIn(needle, workflow, f"the job file lost {needle}")
        policy = json.loads((ROOT / "SITE_CHANGE_POLICY.json").read_text(encoding="utf-8"))
        releases = {row.get("action"): row for row in policy.get("releasedCorrections", []) if isinstance(row, dict)}
        self.assertIn("front_page_compaction", releases, "a live-page edit needs the owner's words on record")
        self.assertIn("rebuild the four pages", releases["front_page_compaction"]["ownerInstruction"])


if __name__ == "__main__":
    unittest.main()
