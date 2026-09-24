"""Shared, compact Daily Yield family directory for every active static page."""
import html
import re

BLOG = "https://dailyyield.blogspot.com"
FAMILY = [
    ("Daily Article", "/p/article.html", "Original explainers, practical guides and deep dives.", "READ"),
    ("Daily News", "/p/daily-news.html", "Current financial and economic developments.", "FOLLOW"),
    ("Calculators", "/p/calculator_0908148622.html", "Loan, investing, tax and planning tools.", "MODEL"),
    ("Markets Today", "/p/markets-today.html", "The complete global market command centre.", "ANALYSE"),
    ("Global Snapshot", "/p/global-snapshot.html", "A concise cross-asset market summary.", "SCAN"),
    ("Money Atlas", "/p/money-atlas_01486068069.html", "Country-by-country money and market context.", "EXPLORE"),
    ("For Corporate", "/p/for-corporate_01804417406.html", "Finance resources for business decisions.", "WORK"),
]
ACTIVE_PAGES = [p for _, p, _, _ in FAMILY] + [
    "/p/about-us_02080501126.html",
    "/p/contact-us_01883938366.html",
    "/p/disclaimer.html",
    "/p/privacy-policy.html",
]
START = "<!-- DY_PAGE_FAMILY_START -->"
END = "<!-- DY_PAGE_FAMILY_END -->"


def family_block(current_path=""):
    cards = []
    for name, path, description, verb in FAMILY:
        current = path == current_path
        attrs = ' aria-current="page"' if current else ""
        state = '<span class="dyf-here">You are here</span>' if current else f'<span class="dyf-open">{verb} →</span>'
        cards.append(
            f'<a class="dyf-card{" dyf-current" if current else ""}" href="{BLOG}{path}"{attrs}>'
            f'<strong>{html.escape(name)}</strong><small>{html.escape(description)}</small>{state}</a>'
        )
    return START + """
<style>
#dyPageFamily{--dyf-ink:#241610;--dyf-muted:#6e5d4b;--dyf-line:#eadcc8;--dyf-paper:#fffdf8;max-width:1180px;margin:clamp(48px,8vw,92px) auto 18px;padding:clamp(25px,5vw,46px);border:1px solid var(--dyf-line);border-radius:22px;background:linear-gradient(145deg,#fffdf8,#fff9ef);color:var(--dyf-ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-sizing:border-box}
#dyPageFamily *{box-sizing:border-box}#dyPageFamily .dyf-kicker{margin:0 0 9px;color:#9c4522;font-size:10px;font-weight:900;letter-spacing:.17em;text-transform:uppercase}#dyPageFamily h2{margin:0;font:700 clamp(29px,5vw,48px)/1.05 Georgia,serif;letter-spacing:-.025em}#dyPageFamily .dyf-intro{max-width:690px;margin:12px 0 24px;color:var(--dyf-muted);font-size:15px;line-height:1.65}#dyPageFamily .dyf-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}#dyPageFamily .dyf-card{min-width:0;min-height:154px;padding:17px;border:1px solid var(--dyf-line);border-radius:14px;background:#fff;color:var(--dyf-ink);text-decoration:none;display:flex;flex-direction:column;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}#dyPageFamily .dyf-card:hover{transform:translateY(-2px);border-color:#c99770;box-shadow:0 9px 24px rgba(75,43,20,.08)}#dyPageFamily .dyf-card:focus-visible{outline:3px solid rgba(156,69,34,.28);outline-offset:2px}#dyPageFamily .dyf-card strong{font:700 20px/1.15 Georgia,serif}#dyPageFamily .dyf-card small{display:block;margin:8px 0 15px;color:var(--dyf-muted);font-size:12px;line-height:1.5}#dyPageFamily .dyf-open,#dyPageFamily .dyf-here{margin-top:auto;color:#9c4522;font-size:9px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}#dyPageFamily .dyf-current{background:#241610;color:#fff;border-color:#241610;pointer-events:none}#dyPageFamily .dyf-current small{color:#d9c9ba}#dyPageFamily .dyf-current .dyf-here{color:#f1b383}#dyPageFamily .dyf-utility{margin:18px 0 0;padding-top:16px;border-top:1px solid var(--dyf-line);display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px}#dyPageFamily .dyf-utility a{color:var(--dyf-muted);text-decoration:none}#dyPageFamily .dyf-utility a:hover{color:#9c4522;text-decoration:underline}@media(max-width:900px){#dyPageFamily .dyf-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:540px){#dyPageFamily{margin-top:40px;padding:22px 16px;border-radius:16px}#dyPageFamily .dyf-grid{grid-template-columns:1fr}#dyPageFamily .dyf-card{min-height:128px}}
</style>
<section aria-labelledby="dyPageFamilyTitle" id="dyPageFamily">
<p class="dyf-kicker">One publication · connected desks</p><h2 id="dyPageFamilyTitle">The Daily Yield family</h2>
<p class="dyf-intro">Move between reporting, tools, complete market analysis and the concise Global Snapshot without losing your place in Daily Yield.</p>
<div class="dyf-grid">""" + "".join(cards) + """</div>
<nav aria-label="Daily Yield information" class="dyf-utility"><a href="https://dailyyield.blogspot.com/p/about-us_02080501126.html">About</a><a href="https://dailyyield.blogspot.com/p/contact-us_01883938366.html">Contact</a><a href="https://dailyyield.blogspot.com/p/disclaimer.html">Disclaimer</a><a href="https://dailyyield.blogspot.com/p/privacy-policy.html">Privacy</a></nav>
</section>
""" + END


def ensure_family(content, current_path=""):
    """Replace our prior block or append it once; also retire obsolete market links."""
    content = content.replace("/p/share-market_0718113516.html", "/p/global-snapshot.html")
    content = content.replace("MARKET EXPLORER", "GLOBAL SNAPSHOT").replace("Market Explorer", "Global Snapshot")
    content = content.replace("SHARE &amp; MARKET", "GLOBAL SNAPSHOT").replace("Share &amp; Market", "Global Snapshot")
    pattern = re.escape(START) + r".*?" + re.escape(END)
    content, count = re.subn(pattern, lambda _m: family_block(current_path), content, flags=re.S)
    if not count:
        content = content.rstrip() + "\n" + family_block(current_path)
    return content
