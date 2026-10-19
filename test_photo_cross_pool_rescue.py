#!/usr/bin/env python3
"""A substituted topic has no photo pool of its own; verified unused photographs exist.

19 October 2026, 21:33 IST: the 19:45 Evergreen slot was written and then abandoned
because the live Commons search returned 54 candidates and none passed the content
match, while the article's own key had no prepared pool. Elsewhere in the repository
295 licence-checked photographs sat unused. These tests keep the rescue honest: the
registry of published images still excludes everything that already ran.
"""
import io, json, shutil, tempfile, unittest
from pathlib import Path
from unittest import mock

import photo_library
from PIL import Image


def _entry(source_id, title, width=2400, height=1350):
    return {"source_id": source_id, "title": title, "description": title,
            "query": "market stall cash", "creator": "Named photographer",
            "licence": "CC BY 4.0", "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_page": "https://commons.wikimedia.org/wiki/File:" + source_id + ".jpg",
            "download_url": "https://upload.example/" + source_id + ".jpg",
            "original_url": "https://upload.example/" + source_id + ".jpg",
            "width": width, "height": height}


class PoolReserve(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "master").mkdir(); (self.tmp / "news").mkdir()
        (self.tmp / "PHOTO_USAGE_REGISTRY.json").write_text(json.dumps(
            {"version": 1, "baseline_complete": True,
             "items": [{"source_id": "commons:used"}]}))
        photo_library.save_pool(self.tmp / "master" / "one.json",
                                {"entries": [_entry("commons:free", "Vendor counting cash at a market stall"),
                                             _entry("commons:used", "Same photograph already published")],
                                 "taken": [_entry("commons:used", "Already taken by another article")],
                                 "rotation": 0})
        photo_library.save_pool(self.tmp / "news" / "desk.json",
                                 {"entries": [_entry("commons:tiny", "Market stall", width=700, height=400)],
                                  "rotation": 0})
        self._dirs = (photo_library.MASTER_DIR, photo_library.NEWS_DIR, photo_library.ROOT)
        photo_library.MASTER_DIR = self.tmp / "master"
        photo_library.NEWS_DIR = self.tmp / "news"
        photo_library.ROOT = self.tmp

    def tearDown(self):
        photo_library.MASTER_DIR, photo_library.NEWS_DIR, photo_library.ROOT = self._dirs
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_verified_unpublished_photograph_is_available_as_a_reserve(self):
        entry = photo_library.reserve_unused_pool_entry("Vendor counting cash at a market stall")
        self.assertIsNotNone(entry, "the unused pool entry should have been usable")
        self.assertEqual(entry["source_id"], "commons:free")
        self.assertTrue(entry.get("pool_rescue"))

    def test_nothing_may_be_taken_twice(self):
        first = photo_library.reserve_unused_pool_entry("Vendor counting cash at a market stall")
        self.assertTrue(first)
        self.assertIsNone(photo_library.reserve_unused_pool_entry("Vendor counting cash at a market stall"),
                          "a rescued photograph must be marked taken in its own pool")

    def test_already_published_and_undersized_images_are_refused(self):
        pool = photo_library.load_pool(self.tmp / "master" / "one.json")
        pool["entries"] = [_entry("commons:used", "Already published elsewhere"),
                           _entry("commons:tiny", "Market stall cash", width=700, height=400)]
        pool["taken"] = []
        photo_library.save_pool(self.tmp / "master" / "one.json", pool)
        self.assertIsNone(photo_library.reserve_unused_pool_entry("Vendor counting cash at a market stall"))


class SelectionUsesTheReserve(unittest.TestCase):
    """choose_photos must not abandon a finished article over a missing picture."""

    def test_a_borrowed_image_passes_every_safety_check(self):
        import photo_selector

        briefs = ["Vendor counting cash at a market stall", "Household budgeting at a kitchen table",
                  "Small business shop owner handing over a receipt"]
        import random
        images = []
        for index in range(3):
            generator = random.Random(1000 + index)
            image = Image.new("RGB", (2400, 1350))
            pixels = image.load()
            blocks = [[(generator.randrange(2) * 255,) * 3 for _ in range(80)] for _ in range(45)]
            for by, row in enumerate(blocks):     # coarse random blocks: high contrast,
                for bx, colour in enumerate(row):
                    for dy in range(30):
                        for dx in range(30):
                            pixels[bx * 30 + dx, by * 30 + dy] = colour
            buffer = io.BytesIO(); image.save(buffer, "JPEG", quality=90)
            images.append(buffer.getvalue())

        taken = []

        def fake_get(url, headers=None, timeout=None):
            response = mock.Mock()
            response.raise_for_status = lambda: None
            response.content = images[min(len(taken), 2)]
            taken.append(url)
            return response

        slug = "test-cross-pool-rescue"
        folder = photo_selector.ROOT / "assets" / "master" / slug
        with mock.patch.object(photo_selector, "load_registry",
                               return_value={"version": 1, "baseline_complete": True, "items": []}), \
             mock.patch.object(photo_selector, "save_registry", lambda registry: None), \
             mock.patch.object(photo_selector, "commons_candidates", lambda brief: []), \
             mock.patch.object(photo_selector, "requests") as requests, \
             mock.patch.object(photo_library, "reserve_master_entry",
                               return_value=None), \
             mock.patch.object(photo_library, "reserve_unused_pool_entry",
                               side_effect=lambda brief, avoid=None: _entry("commons:rescued%d" % len(taken),
                                                                             "Vendor counting cash at a market stall")):
            requests.get = fake_get
            try:
                selected = photo_selector.choose_photos(briefs, slug, "test-key")
            finally:
                shutil.rmtree(folder, ignore_errors=True)

        self.assertEqual(len(selected), 3, "all three placements should be filled from the reserve")
        for row in selected:
            self.assertIn("creativecommons.org", row["license_url"])
            self.assertTrue(row["url"].endswith(".jpg"))


class PublishStepCarriesTheSameInputs(unittest.TestCase):
    """A step that can write an article must be able to search demand for its topic."""

    def test_both_master_publish_steps_have_search_console_inputs(self):
        for workflow in ("master_evergreen_writer.yml", "master_trending_writer.yml"):
            text = (Path(".github/workflows") / workflow).read_text()
            block = text.split("name: Publish after successful validated preparation", 1)[1]
            block = block.split("run:", 1)[0]
            for name in ("GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN"):
                self.assertIn(name, block, f"{workflow}: the publish step is missing {name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
