#!/usr/bin/env python3
"""The indexing-policy gate every publisher must pass before a URL is written to Blogger.

Why this file exists: on 22 October 2026 the first whole-corpus audit (search_index_policy_audit.py)
judged all 597 published URLs against Bing's Webmaster Guidelines and Google's indexability rules and
found five classes of defect that our own quality gates never looked at - a title in ALL CAPS, a title
clipped onto a comma, six URLs sharing one title, an image with no alt text, and posts created out of a
raw schema URL string. Repairing them once is not compliance. Compliance is a publisher being unable to
ship them, so every rule the audit measures is enforced here, at the point of writing.

The rules are deliberate about what they may not do. A title is normalised and, when it cannot be made
to fit, the *candidate* is rejected and the caller's own fallback applies: nothing here invents copy,
pads a headline, or edits an article's sourced sentences - which is also what Bing §14 asks of structured
data and what the per-paragraph source rule asks of the body.

Nothing in this module touches the network. Run ``--check`` for the offline proof.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter

# Both engines truncate a title in the search results at roughly this width, and Bing §13 asks for a
# title that describes the page rather than a sentence about it.
TITLE_MIN = 12
TITLE_MAX = 70
MIN_DOCUMENT_WORDS = 120         # below this, similarity is not a question a crawler can answer
NEAR_DUPLICATE_RATIO = 0.42      # Jaccard overlap of 8-word shingles: same document, different URL
STUFFING_MIN_REPEATS = 4         # one word, this many times, inside a single paragraph
STUFFING_PARAGRAPH_SHARE = 0.45  # ... and in this much of the page, which is what makes it stuffing
SEO_PACKAGE_MARKER = "<!-- DY_SEO_META_START -->"   # named so a test can prove nothing strips comments

CUT_TAIL = re.compile(
    r"(?:[,;:|\-–—/]$|\b(?:of|and|the|for|in|to|a|an|at|on|by|is|are|with|vs|versus|its|his|their)\b"
    r"[\s.,;:]*$|['’]s[\s.,;:]*$)", re.I)

STOPWORDS = frozenset(("a an the of and or to in for on at is are was were be been with by from as it "
                       "its this that these those new india global today will would can could about into "
                       "over under between why how what when where which who whose and").split())

# A page whose title is one of these is not an article, it is a mistake: a URL, a schema token, or a
# bare generic word that describes nothing. Bing §11 and §21 both push such URLs out of the eligibility
# pool, and §21 says they slow down the crawling of everything else.
JUNK_TITLE = re.compile(r"^(?:https?://|www\.|/p/|/\d{4}/)|\b(?:n/?a|null|untitled|indexnow-key)\b|"
                        r"^(?:article|post \d+|\d{1,4}|test|draft)$", re.I)

# Words that lose all meaning by repetition in a headline; everything else in ALL CAPS is a shouting
# brand we do not correct, so the exception list is short and explicit.
KEEP_CAPS = ("EMI", "SIP", "SWP", "GST", "GDP", "CAD", "USD", "EUR", "INR", "JPY", "CPI", "NIFTY",
              "SENSEX", "MCX", "SEBI", "RBI", "IRS", "APR", "APY", "ROI", "IPO", "ETF", "GIFT")


def strip_markup(markup: str) -> str:
    """The words a reader of this HTML would see.

    Comments are removed first, as whole blocks: the standing pages open with an HTML comment that
    contains "Blogger > Theme > Restore", and an ordinary tag regex stops at that first angle bracket
    and hands the rest of the note to the word counter. That is how a measurement bug once looked like a
    live leak on four pages that were fine.
    """
    markup = re.sub(r"<!--[\s\S]*?-->", " ", markup or "", flags=re.I)
    markup = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", markup, flags=re.I)
    markup = re.sub(r"<[^>]+>", " ", markup)
    return " ".join(html.unescape(markup).split())


def prose(markup: str) -> str:
    """The article's own sentences, with navigation removed.

    Bing's keyword-stuffing test is about prose. A hub page that lists twenty desks is allowed to say
    the word "article" in twenty link labels, and scoring that as stuffing would only teach us to delete
    useful navigation.
    """
    markup = re.sub(r"<!--[\s\S]*?-->", " ", markup or "", flags=re.I)
    markup = re.sub(r"<(script|style|noscript)[^>]*>[\s\S]*?</\1>", " ", markup, flags=re.I)
    markup = re.sub(r"<a\b[^>]*>[\s\S]*?</a>", " ", markup, flags=re.I)
    return strip_markup(markup)


def title_is_cut(title: str) -> bool:
    """True when a headline stops where a reader expected more."""
    return bool(CUT_TAIL.search((title or "").strip()))


# A ticker is not a shout. "EURUSD 1.1253 EURGBP 0.8438 EURJPY 177.4" is how the currency desk writes a
# headline, because ISO 4217 codes have no lowercase form, and "NIFTY 50" is the name of an index. Reading
# either as an all-caps display defect would hold a good post in CI and send the audit to demand a retitle
# of a page that should be left alone, so a token counts as a symbol only on shapes we can name.
FX_PAIR = re.compile(r"[A-Z]{6}")                # EURUSD, GBPJPY
CURRENCY = re.compile(r"[A-Z]{3}")               # USD, INR, EUR
INDEX_SYMBOL = frozenset(("NIFTY", "SENSEX", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTY50", "VIX",
                          "DXY", "HSI", "NIKKEI", "KOSPI", "STOXX50E", "FTSE100", "DAX40", "CAC40",
                          "IBEX35", "NIFTYBANK", "GIFTNIFTY", "BTC", "ETH", "GOLD", "SILVER", "CRUDE"))
MACHINE_ONLY_SLUGS = ("indexnow-key",)   # the audit's EXEMPT_UTILITY_SLUGS: an endpoint, not a page


def is_symbol(token: str) -> bool:
    token = token.strip(" .:;,()")
    return bool(token) and (token in INDEX_SYMBOL or bool(FX_PAIR.fullmatch(token))
                            or bool(CURRENCY.fullmatch(token))
                            or bool(re.fullmatch(r"[A-Z]{3,6}\d{1,3}", token)))


def is_shouting(title: str) -> bool:
    """True when the title is written in caps as an act of shouting, not because its words are symbols.

    Known limitation, stated rather than hidden: a four or five-letter exchange ticker that is not in
    INDEX_SYMBOL (a company code on its own, say) still reads as shouting here and would be sentence-cased.
    That is the safe direction to be wrong in - the code lowers a word a reader can still read, where
    lowering "EURUSD" would have broken the page.
    """
    if not is_all_caps(title):
        return False
    letters = [token for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", title or "") if not token.isdigit()]
    return any(not is_symbol(token.upper()) for token in letters)


def is_all_caps(title: str) -> bool:
    letters = [ch for ch in title or "" if ch.isalpha()]
    return len(letters) > 5 and all(ch.isupper() for ch in letters)


def sentence_case(title: str) -> str:
    """TERMS AND CONDITIONS -> Terms and conditions, without wrecking acronyms or proper names.

    Google's display-quality guidance treats an all-caps title as something we should not be shipping,
    and Bing §13 wants the title written for the person reading the results page.
    """
    title = re.sub(r"\s+", " ", html.unescape((title or "").strip()))
    if not title:
        return ""
    if not is_shouting(title):
        # leave a ticker headline exactly as written: lowercasing "EURUSD" would be the real defect
        return title
    lowered = title.lower()
    for token in KEEP_CAPS:
        lowered = re.sub(rf"\b{token.lower()}\b", token, lowered)
    lowered = re.sub(r"\b([a-z]{1,4})\b(?=\s*[\d.]{2,})", lambda m: m.group(1).upper(), lowered)
    out = lowered[:1].upper() + lowered[1:]
    # A proper noun we lowercased by accident is worth keeping capital - but only where the source wrote
    # it in mixed case. In an ALL-CAPS title every word looks capitalised, and restoring them all would
    # hand back the shouting title we were asked to fix.
    for word in {row for row in re.findall(r"\b[A-Z][a-z][A-Za-z'’.-]*\b", title)}:
        out = re.sub(rf"\b{re.escape(word.lower())}\b", word, out, count=1)
    return out


def uncut_title(title: str, limit: int = TITLE_MAX) -> str:
    """Whole words only, and never a headline left ending on a comma, a preposition or a possessive.

    This is the shape our own 46-character master-title clip used to produce - `Billionaire Mukesh
    Ambani launches India's` - so the rule lives in one place and both the clip and this gate share it.
    """
    tokens = " ".join((title or "").split()).split()
    whole = " ".join(tokens)
    if len(whole) <= limit:
        # Nothing had to be cut, so nothing can be dangling. An earlier version trimmed here anyway and
        # turned a finished headline - "Build Your Layoff Plan Before You Need It" - into a truncated one
        # by treating the closing "It" as an orphan. Only a title that this function actually clipped can
        # be left ending on a preposition, and only then is the trim the right medicine.
        return whole.rstrip(" ,;:.—–-…")
    kept = ""
    for token in tokens:
        trial = f"{kept} {token}".strip()
        if len(trial) > limit:
            break
        kept = trial
    while kept:
        tail = kept.rsplit(" ", 1)[-1].lower().strip(" ,;:.\u2014\u2013-")
        if tail.endswith("'s") or tail.endswith("\u2019s"):
            kept = kept.rsplit(" ", 1)[0] if " " in kept else ""
            continue
        if tail not in {"a", "an", "and", "as", "at", "but", "by", "for", "from", "if", "in", "into",
                        "its", "of", "on", "or", "our", "per", "the", "to", "vs", "with", "that", "this",
                        "these", "those", "it", "is", "are", "was", "were", "be", "been", "after",
                        "before", "over", "under", "between", "&"}:
            break
        kept = kept.rsplit(" ", 1)[0] if " " in kept else ""
    return kept.rstrip(" ,;:.\u2014\u2013-\u2026")


def title_problems(title: str, *, minimum: int = TITLE_MIN, maximum: int = TITLE_MAX) -> list[str]:
    """Every reason this title may not go out as it stands. An empty list means it is compliant."""
    problems = []
    clean = " ".join((title or "").split())
    if not clean:
        return ["empty title"]
    if len(clean) < minimum:
        problems.append(f"title is {len(clean)} characters, under the {minimum}-character floor")
    if len(clean) > maximum:
        problems.append(f"title is {len(clean)} characters, past the {maximum}-character limit both "
                        "engines truncate at")
    if is_shouting(clean):
        problems.append("title is written entirely in upper case")
    if title_is_cut(clean):
        problems.append("title stops mid-phrase")
    if JUNK_TITLE.search(clean.strip(" .:")):
        problems.append("title is a raw token (a URL, a schema string, or a placeholder), not a headline")
    return problems


def key(title: str) -> str:
    """The comparison key for "is this the same title as that URL's". """
    return re.sub(r"[^a-z0-9 ]", "", " ".join((title or "").split()).lower()).strip()


def publish_title(title: str, taken: set[str] | None = None, *, limit: int = TITLE_MAX,
                  minimum: int = TITLE_MIN, number_if_taken: bool = True) -> str:
    """Return a compliant title for this URL, or "" when the candidate cannot be repaired.

    An empty string is a real answer, not a failure: the caller has its own fallback for the slot, and
    padding a headline to clear a check is how two URLs end up sharing one.
    """
    candidate = uncut_title(sentence_case(title).strip(" -–—:,.,"), limit)
    if not candidate or is_shouting(candidate) or JUNK_TITLE.search(candidate.strip(" .:")):
        return ""
    if title_is_cut(candidate):
        candidate = uncut_title(candidate, max(minimum, len(candidate) - 8))
    if not candidate or title_is_cut(candidate) or len(candidate) > limit:
        return ""
    if len(candidate) < minimum:
        return ""
    if taken:
        keys = {key(row) for row in taken}
        if key(candidate) in keys:
            if not number_if_taken:
                # The caller asked not to be handed a numbered title: it has its own idea of what the
                # second edition should be called, and "" tells it to use that idea.
                return ""
            for ordinal in range(2, 10):
                suffix = f" ({ordinal})"
                attempt = uncut_title(candidate, limit - len(suffix)) + suffix
                if key(attempt) not in keys:
                    return attempt
            return ""
    return candidate


def page_title(body: str, fallback: str = "", *, limit: int = TITLE_MAX) -> str:
    """A page's title should be the heading the page already shows.

    The standing pages carry titles like `DAILY NEWS` and `CALCULATOR` while their own markup contains
    a line such as "EMI, SIP and loan calculators". Bing §13 wants the title to describe the page, and
    the sentence the page already displays is a better description than anything a script could invent -
    it is the site's own words, which is also the rule this repository applies to headlines.
    """
    for pattern in (r"<h1\b[^>]*>([\s\S]*?)</h1>", r"<h2\b[^>]*>([\s\S]*?)</h2>",
                    r"class=[\"'][^\"']*(?:eyebrow|kicker|lede|hero-title|page-title)[^\"']*[\"'][^>]*>"
                    r"([\s\S]*?)<"):
        for match in re.finditer(pattern, body or "", flags=re.I):
            text = sentence_case(strip_markup(match.group(1))).strip(" \u00b7-\u2014\u2013:,.")
            text = re.sub(r"^\W{0,3}", "", text)
            if len(text) > limit:
                # The heading is the page's own words, but a heading too long for a title stays a
                # heading. Clipping one to 70 characters is how "ABOUT US" came back as
                # "Money, explained with clarity evidence numbers honesty context maths" on the first
                # repair run of 22 October: every comma belonged to markup, and the tail was severed
                # mid-list. A title must read finished or not be borrowed at all.
                continue
            if len(text.split()) >= 6 and not re.search(r"[,.;:—–]", text):
                # A run of six words with no punctuation anywhere is not a headline somebody wrote, it is
                # a list of items or a row of buttons - the shape that made the first repair pass borrow
                # a page's greeting strip ("Say hello namaste bonjour hola ciao salaam") as its title.
                continue
            if len(text) >= TITLE_MIN and not title_is_cut(text) and not JUNK_TITLE.search(text):
                return text
    return ""


def shingles(text: str, size: int = 8) -> set[str]:
    tokens = text.split()
    if len(tokens) < size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def similarity(left: str, right: str) -> float:
    """Jaccard overlap of 8-word shingles: how alike two documents read to a crawler.

    Measured on distinct shingles, which is why the guard is on document length and not on the size of
    the signature: a page of one repeated word has a signature of size 1 and no opinion worth having.
    """
    if len((left or "").split()) < MIN_DOCUMENT_WORDS or len((right or "").split()) < MIN_DOCUMENT_WORDS:
        return 0.0
    a, b = shingles((left or "").lower()), shingles((right or "").lower())
    return len(a & b) / max(1, len(a | b))


def near_duplicate(text: str, published: list[str], ratio: float = NEAR_DUPLICATE_RATIO) -> tuple[float, int]:
    """Worst similarity of this article against the recent ones, and which index it matched.

    -1 means no match. Bing §6 and the abuse list both name the same thing - the same content at several
    URLs - and the desk templates make it easy to reproduce by accident: two country editions, one day,
    one template, four swapped numbers. The publisher measures it before the URL exists.
    """
    signature = shingles((text or "").lower())
    worst, index = 0.0, -1
    for position, other in enumerate(published):
        if len((other or "").split()) < MIN_DOCUMENT_WORDS:
            continue
        other_signature = shingles((other or "").lower())
        score = len(signature & other_signature) / max(1, len(signature | other_signature))
        if score > worst:
            worst, index = score, position
    return (worst, index) if worst >= ratio else (worst, -1)


def alt_failures(content: str, minimum: int = 6) -> int:
    """Images with no usable alt text (Bing §5 §12)."""
    failures = 0
    for tag in re.findall(r"<img\b[^>]*>", content or "", flags=re.I):
        match = re.search(r"alt=['\"]([^'\"]*)['\"]", tag, flags=re.I)
        if not match or len(match.group(1).strip()) < minimum:
            failures += 1
    return failures


def most_used_word(markup: str) -> tuple[str, float]:
    """The word a page hammers through its paragraphs, and how much of the page does it. "" if none.

    Not "the most frequent word as a share of prose". When the audit measured that share it reported 12
    stuffed URLs that were not stuffed: "china" on the China edition, "insurance" on a guide to types of
    insurance, "social" on a Social Security article. A page about a thing names that thing, and a
    publisher that holds those articles is a publisher that stops publishing. Bing's abuse is a term
    pushed into the sentences themselves, so this counts repetition inside a paragraph
    (STUFFING_MIN_REPEATS or more of the same word) and asks how many paragraphs do it. Same rule as
    search_index_policy_audit.stuffing_burst, kept here so the two can never disagree about what to hold.
    """
    paragraphs = [prose(block) for block in re.split(r"</p>|<br\s*/?>", markup or "") if len(block) > 40]
    if len(paragraphs) < 4:
        return "", 0.0
    across: Counter[str] = Counter()
    for block in paragraphs:
        tally: Counter[str] = Counter()
        for token in re.findall(r"[A-Za-z][a-z']+", block.lower()):
            if token not in STOPWORDS and len(token) > 3:
                tally[token] += 1
        across.update({token: 1 for token, hits in tally.items() if hits >= STUFFING_MIN_REPEATS})
    if not across:
        return "", 0.0
    word, blocks = across.most_common(1)[0]
    share = blocks / len(paragraphs)
    return (word, share) if share >= STUFFING_PARAGRAPH_SHARE else ("", 0.0)


def canonical_url(value: str) -> tuple[str, bool]:
    """The one address a Blogger URL has, and whether this one had to be corrected.

    Blogger serves the same document at `?m=1` and declares the parameterless URL as its canonical, which
    is right for readers and wrong to submit: an IndexNow or Bing submission of a parameterised URL asks a
    crawler to fetch a redirect, and Google answers that pattern with "Redirect error" or "Alternate page
    with proper canonical" instead of indexing anything. So every URL leaving this repository for a search
    engine is normalised here first - https where it has a host, no mobile parameter, no fragment - and
    the second value says whether a change was made, so the run can report it instead of silently editing.

    Parsed by hand, deliberately: this module imports nothing but html, json, re and collections, which is
    what lets a source scan prove the gate never reaches the network (test_index_policy_gate.Boundaries),
    and the rule only has to tell a scheme, a host, a path, a query and a fragment apart. A query parameter
    we do not recognise is left alone: this is a de-duplicator, not a cleaner with opinions about analytics.
    """
    raw = str(value or "").strip()
    if not raw:
        return "", False
    scheme, sep, rest = raw.partition("://")
    if not sep:
        scheme, rest = "", raw
    rest = rest.split("#", 1)[0]
    query = ""
    if "?" in rest:
        rest, _, query = rest.partition("?")
    keep = [pair for pair in query.split("&") if pair and not re.fullmatch(r"m=[01]", pair)]
    if not sep:
        path = rest
        netloc = ""
    else:
        netloc = rest.split("/", 1)[0]
        path = rest[len(netloc):]
    if sep and scheme.lower() == "http":
        scheme = "https"
    out = (f"{scheme}://{netloc}" if sep else "") + (path or ("/" if sep else ""))
    if keep:
        out += "?" + "&".join(keep)
    return out, out != raw


def asset_file_name(slug: str, placement: int) -> str:
    """Name a photo after its subject, in its own words (Bing §12: unique, relevant file names).

    `assets/master/gold-rate-in-india/gold-rate-in-india-1.jpg` is what a crawler reads. `photo-1.jpg`
    inside that folder was the same string on 473 URLs. Posts already published keep pointing at files
    that stay in the repository, so this changes only what goes out from now on.
    """
    slug = re.sub(r"[^a-z0-9-]+", "-", (slug or "daily-yield").lower()).strip("-") or "daily-yield"
    return f"{slug}-{int(placement)}.jpg"


def check_article(title: str, content: str, *, taken_titles: set[str] | None = None,
                  siblings: list[str] | None = None, ratio: float = NEAR_DUPLICATE_RATIO,
                  minimum_words: int = 300) -> list[str]:
    """Everything a publisher must know before it writes this URL. An empty list means ship it."""
    problems = title_problems(title)
    body = strip_markup(content)
    if len(body.split()) < minimum_words:
        problems.append(f"page carries {len(body.split())} words of visible text, under the "
                        f"{minimum_words}-word line Bing §11 calls thin")
    missing = alt_failures(content)
    if missing:
        problems.append(f"{missing} image(s) without usable alt text (Bing §5 §12)")
    word, share = most_used_word(content)
    if word:
        problems.append(f"{word!r} appears {STUFFING_MIN_REPEATS}+ times in {share:.0%} of paragraphs, "
                        "which is the keyword stuffing Bing's abuse list names")
    if siblings:
        score, index = near_duplicate(body, siblings, ratio)
        if index >= 0:
            problems.append(f"this is {score:.0%} the same document as another published URL (Bing §6); "
                            "it needs its own facts, not the shared template")
    if taken_titles and key(title) in {key(row) for row in taken_titles}:
        problems.append("another live URL already carries this exact title (Bing §6 §13)")
    return problems


def self_test() -> dict:
    long = ("Student Loan Interest Rates: Federal, Private, And Public Compared Across Every "
            "Product Offered This Quarter")
    possessive = "Billionaire Mukesh Ambani launches India's largest retail fund in a decade of dealmaking"
    cases = [
        (publish_title("TERMS AND CONDITIONS"), "Terms and conditions"),
        (publish_title("article"), ""),
        (publish_title("http://schema.org"), ""),
        (page_title('<h2>EMI, SIP and loan calculators</h2><p>' + "filler words " * 60 + "</p>",
                    "CALCULATOR"), "EMI, SIP and loan calculators"),
        (publish_title(long).endswith(","), False),
        (len(publish_title(long)) <= TITLE_MAX, True),
        (title_is_cut(publish_title(long)), False),
        (len(publish_title(possessive)) < len(possessive), True),
        (publish_title(possessive).lower().endswith("'s"), False),
        (publish_title("Gold rate today in India", {"Gold rate today in India"}),
         "Gold rate today in India (2)"),
        (similarity("alpha beta gamma delta " * 40, "alpha beta gamma delta " * 40), 1.0),
        (similarity("alpha beta gamma delta " * 4, "alpha beta gamma delta " * 4), 0.0),
        (alt_failures('<img src="/a.jpg" alt="Desk at the BSE floor"><img src="/b.jpg">'), 1),
        (asset_file_name("Gold Rate 2026!", 2), "gold-rate-2026-2.jpg"),
        (sentence_case("How Nifty and SENSEX moved today"), "How Nifty and SENSEX moved today"),
        (is_all_caps("Gold rate today in India"), False),
        (title_problems("Daily articles: every desk index"), []),
    ]
    failures = [{"value": repr(got), "wanted": repr(want)} for got, want in cases if got != want]

    same = " ".join(f"settlement {index} moved on the desk before the bell" for index in range(30))
    other = " ".join(f"treasury {index} settled after the reserve bank decision today" for index in range(30))
    if near_duplicate(same, [same])[1] != 0:
        failures.append({"value": near_duplicate(same, [same]), "wanted": "identical bodies must match"})
    if near_duplicate(same, [other])[1] != -1:
        failures.append({"value": near_duplicate(same, [other]), "wanted": "different bodies must not match"})

    leaked = '<div><!--\n Install the XML via Blogger > Theme > Restore. The pill switches.\n-->\n' \
             '<p>Real words here.</p></div>'
    if strip_markup(leaked) != "Real words here.":
        failures.append({"value": strip_markup(leaked),
                         "wanted": "an HTML comment is invisible, so the word counter may not read it - "
                                   "this was once reported as a live leak on four pages that were fine"})
    if "DY_SEO_META_START" not in SEO_PACKAGE_MARKER:
        failures.append({"value": SEO_PACKAGE_MARKER, "wanted": "the meta package marker stays named here"})
    hub = '<p>' + " ".join(f"gold {index} rate in india today" for index in range(40)) + "</p>" \
          + "".join(f'<a href="/x{i}">article {i}</a>' for i in range(30))
    if most_used_word(hub)[0]:
        failures.append({"value": most_used_word(hub), "wanted": "a page naming its own subject between "
                                                                  "navigation labels is not stuffing"})
    hammered = "<p>" + "best loan best loan best loan best loan at the counter</p>" * 6
    if most_used_word(hammered)[0] not in ("best", "loan"):
        failures.append({"value": most_used_word(hammered),
                         "wanted": "a term pushed through every paragraph must be caught"})
    normalised, changed = canonical_url("http://dailyyield.blogspot.com/p/daily-news.html?m=1#top")
    if normalised != "https://dailyyield.blogspot.com/p/daily-news.html" or not changed:
        failures.append({"value": [normalised, changed],
                         "wanted": "a search-engine submission must carry the canonical address only - "
                                    "the ?m=1 variant is a redirect away from the page Google indexes"})
    kept, _ = canonical_url("https://dailyyield.blogspot.com/2026/10/x.html?utm_source=rss&m=1")
    if kept != "https://dailyyield.blogspot.com/2026/10/x.html?utm_source=rss":
        failures.append({"value": kept,
                         "wanted": "only the mobile parameter goes; another query is not ours to judge"})
    relative, changed = canonical_url("/p/about-us.html#frag")
    if relative != "/p/about-us.html" or not changed:
        # the fragment really was dropped, so it counts as a change; what must not happen is inventing
        # a host for an address that never had one, because that is how a path becomes a wrong URL
        failures.append({"value": [relative, changed],
                         "wanted": "a hostless address stays hostless, fragment removed"})
    if page_title("<h1>Say hello namaste bonjour hola ciao salaam</h1>"):
        failures.append({"value": page_title("<h1>Say hello namaste bonjour hola ciao salaam</h1>"),
                         "wanted": "a punctuation-free list of six words is a banner, not a title"})
    if page_title("<h1>" + " ".join(f"word{index}" for index in range(9)) + "</h1>"):
        failures.append({"value": "borrowed a nine-word list",
                         "wanted": "the same, whatever the words are"})
    if page_title("<h1>The Country Money Atlas</h1>") != "The Country Money Atlas":
        failures.append({"value": page_title("<h1>The Country Money Atlas</h1>"),
                         "wanted": "a page's own short name is a title and should be used"})
    problems = check_article("Gold rate today in India", "<p>one two three</p>")
    if not any("thin" in row for row in problems):
        failures.append({"value": problems, "wanted": "a three-word page must not pass as content"})

    return {"status": "OK" if not failures else "FAIL", "mode": "offline self-test",
            "cases": len(cases) + 8, "fail": len(failures), "details": failures[:5], "siteWrites": 0,
            "networkRequests": 0}


def main() -> int:
    import sys
    report = self_test()
    print(json.dumps(report))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
