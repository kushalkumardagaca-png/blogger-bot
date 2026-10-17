#!/usr/bin/env python3
"""A wide desk must fit the edition budget instead of failing the whole slot."""
from __future__ import annotations

import unittest

import news_pipeline as np


def article(sections, items_each, words_each=120):
    body = ['<article>']
    for name in sections:
        body.append(f'<h2 class="fbk-h2"><b>01</b> {name}</h2>')
        body.append('<p class="fbk-sub">Section.</p>')
        for index in range(items_each):
            filler = " ".join(["reported"] * words_each)
            body.append(
                '<div class="fbk-item"><span class="fbk-chip">Source</span>'
                f'<h3>{name} item {index}</h3><p>{filler}</p>'
                '<a class="fbk-src" href="https://example.com/x">Official source</a></div>')
    body.append("</article>")
    return "".join(body)


class TrimNewsItemsTests(unittest.TestCase):
    def test_an_overlong_edition_is_fitted_without_emptying_a_section(self):
        document = article(["Global", "India", "China"], items_each=12, words_each=120)
        before = np.editorial_word_count(document)
        self.assertGreater(before, np.NEWS_MAX_WORDS)
        trimmed, count = np.trim_news_items(document)
        self.assertLessEqual(count, np.NEWS_MAX_WORDS)
        for name in ("Global", "India", "China"):
            section_start = trimmed.index(f"{name}</h2>")
            following = trimmed[section_start:]
            next_heading = following.find('<h2 class="fbk-h2">', 10)
            block = following if next_heading == -1 else following[:next_heading]
            self.assertIn('<div class="fbk-item">', block, f"{name} lost every item")

    def test_a_document_already_inside_the_budget_is_untouched(self):
        document = article(["Global"], items_each=2, words_each=100)
        self.assertEqual(np.trim_news_items(document)[0], document)

    def test_attribution_survives_every_removal(self):
        document = article(["Global", "India"], items_each=10, words_each=150)
        trimmed, _ = np.trim_news_items(document)
        items = trimmed.count('<div class="fbk-item">')
        self.assertEqual(trimmed.count('class="fbk-src"'), items)


if __name__ == "__main__":
    unittest.main()
