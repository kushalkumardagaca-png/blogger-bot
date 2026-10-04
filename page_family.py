"""Shared, compact Daily Yield family directory for every active static page."""
import html
import re
from brand_identity import ensure_brand_identity
from social_identity import SOCIAL_PROFILES, ensure_social_identity

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
    "/p/terms-and-conditions.html",
]
START = "<!-- DY_PAGE_FAMILY_START -->"
END = "<!-- DY_PAGE_FAMILY_END -->"
PRIVACY_SUB_START = "<!-- DY_SUBSCRIPTION_PRIVACY_START -->"
PRIVACY_SUB_END = "<!-- DY_SUBSCRIPTION_PRIVACY_END -->"
SEO_START = "<!-- DY_SEO_META_START -->"
SEO_END = "<!-- DY_SEO_META_END -->"
PAGE_DESCRIPTIONS = {
    "/p/terms-and-conditions.html": "Read the rules, educational limits and acceptable-use terms governing Daily Yield.",
    "/p/privacy-policy.html": "Understand Daily Yield privacy choices, analytics, subscriptions and advertising disclosures.",
    "/p/disclaimer.html": "Review the educational, financial and advertising limitations that apply to Daily Yield content.",
    "/p/contact-us_01883938366.html": "Contact Daily Yield about corrections, privacy, advertising or editorial questions.",
    "/p/about-us_02080501126.html": "Learn how Daily Yield creates sourced financial education, reporting and practical reader tools.",
}


def ensure_page_meta(content, current_path=""):
    """Install a factual fallback description when a Page package has none."""
    if "metaDesc" in (content or "") or SEO_START in (content or ""):
        return content or ""
    description = PAGE_DESCRIPTIONS.get(
        current_path,
        "Explore Daily Yield financial education, current reporting, practical tools and reader guidance.",
    )
    block = SEO_START + """<script>(function(d){var metaDesc=%r,m=d.querySelector('meta[name="description"]');if(!m){m=d.createElement('meta');m.name='description';d.head.appendChild(m);}if(!m.content)m.content=metaDesc;})(document);</script>""" % description + SEO_END
    return (content or "").rstrip() + "\n" + block


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
    social = "".join(
        f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="me noopener noreferrer" '
        f'aria-label="Follow Daily Yield on {html.escape(name, quote=True)}"><strong>{html.escape(name)}</strong>'
        f'<span>{html.escape(handle)}</span></a>'
        for name, url, handle in SOCIAL_PROFILES
    )
    return START + """
<style>
#dyPageFamily{--dyf-ink:#241610;--dyf-muted:#6e5d4b;--dyf-line:#eadcc8;--dyf-paper:#fffdf8;max-width:1180px;margin:clamp(48px,8vw,92px) auto 18px;padding:clamp(25px,5vw,46px);border:1px solid var(--dyf-line);border-radius:22px;background:linear-gradient(145deg,#fffdf8,#fff9ef);color:var(--dyf-ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-sizing:border-box}
#dyPageFamily *{box-sizing:border-box}#dyPageFamily .dyf-kicker{margin:0 0 9px;color:#9c4522;font-size:10px;font-weight:900;letter-spacing:.17em;text-transform:uppercase}#dyPageFamily h2{margin:0;font:700 clamp(29px,5vw,48px)/1.05 Georgia,serif;letter-spacing:-.025em}#dyPageFamily .dyf-intro{max-width:690px;margin:12px 0 24px;color:var(--dyf-muted);font-size:15px;line-height:1.65}#dyPageFamily .dyf-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}#dyPageFamily .dyf-card{min-width:0;min-height:154px;padding:17px;border:1px solid var(--dyf-line);border-radius:14px;background:#fff;color:var(--dyf-ink);text-decoration:none;display:flex;flex-direction:column;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}#dyPageFamily .dyf-card:hover{transform:translateY(-2px);border-color:#c99770;box-shadow:0 9px 24px rgba(75,43,20,.08)}#dyPageFamily .dyf-card:focus-visible{outline:3px solid rgba(156,69,34,.28);outline-offset:2px}#dyPageFamily .dyf-card strong{font:700 20px/1.15 Georgia,serif}#dyPageFamily .dyf-card small{display:block;margin:8px 0 15px;color:var(--dyf-muted);font-size:12px;line-height:1.5}#dyPageFamily .dyf-open,#dyPageFamily .dyf-here{margin-top:auto;color:#9c4522;font-size:9px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}#dyPageFamily .dyf-current{background:#241610;color:#fff;border-color:#241610;pointer-events:none}#dyPageFamily .dyf-current small{color:#d9c9ba}#dyPageFamily .dyf-current .dyf-here{color:#f1b383}#dyPageFamily .dyf-utility{margin:18px 0 0;padding-top:16px;border-top:1px solid var(--dyf-line);display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px}#dyPageFamily .dyf-utility a{color:var(--dyf-muted);text-decoration:none}#dyPageFamily .dyf-utility a:hover{color:#9c4522;text-decoration:underline}#dyPageFamily .dyf-social{margin-top:18px;padding-top:18px;border-top:1px solid var(--dyf-line)}#dyPageFamily .dyf-social-label{margin:0 0 11px;color:#9c4522;font-size:10px;font-weight:900;letter-spacing:.15em;text-transform:uppercase}#dyPageFamily .dyf-social-links{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}#dyPageFamily .dyf-social-links a{min-width:0;padding:11px 12px;border:1px solid var(--dyf-line);border-radius:11px;background:#fff;color:var(--dyf-ink);text-decoration:none;display:flex;flex-direction:column;gap:3px;transition:border-color .18s ease,transform .18s ease}#dyPageFamily .dyf-social-links a:hover{border-color:#c99770;transform:translateY(-1px)}#dyPageFamily .dyf-social-links a:focus-visible{outline:3px solid rgba(156,69,34,.28);outline-offset:2px}#dyPageFamily .dyf-social-links strong{font-size:12px}#dyPageFamily .dyf-social-links span{overflow:hidden;color:var(--dyf-muted);font-size:10px;text-overflow:ellipsis;white-space:nowrap}#dyPageFamily .dyf-subscribe{position:relative;margin-top:18px;padding:16px 18px;border-radius:13px;background:linear-gradient(115deg,#241610,#512618);color:#fff8ee;text-decoration:none;display:flex;align-items:center;justify-content:space-between;gap:14px;overflow:hidden;transition:transform .2s ease,box-shadow .2s ease}#dyPageFamily .dyf-subscribe:before{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent,rgba(255,255,255,.12),transparent);transform:translateX(-120%);transition:transform .7s ease}#dyPageFamily .dyf-subscribe:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(75,43,20,.18)}#dyPageFamily .dyf-subscribe:hover:before{transform:translateX(120%)}#dyPageFamily .dyf-subscribe b{position:relative;font:700 15px/1.3 Georgia,serif}#dyPageFamily .dyf-subscribe span{position:relative;color:#f1b383;font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;white-space:nowrap}@media(max-width:900px){#dyPageFamily .dyf-grid,#dyPageFamily .dyf-social-links{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:540px){#dyPageFamily{margin-top:40px;padding:22px 16px;border-radius:16px}#dyPageFamily .dyf-grid,#dyPageFamily .dyf-social-links{grid-template-columns:1fr}#dyPageFamily .dyf-card{min-height:128px}}
</style>
<section aria-labelledby="dyPageFamilyTitle" id="dyPageFamily">
<p class="dyf-kicker">One publication · connected desks</p><h2 id="dyPageFamilyTitle">The Daily Yield family</h2>
<p class="dyf-intro">Move between reporting, tools, complete market analysis and the concise Global Snapshot without losing your place in Daily Yield.</p>
<div class="dyf-grid">""" + "".join(cards) + """</div>
<nav aria-label="Daily Yield information" class="dyf-utility"><a href="https://dailyyield.blogspot.com/p/about-us_02080501126.html">About</a><a href="https://dailyyield.blogspot.com/p/contact-us_01883938366.html">Contact</a><a href="https://dailyyield.blogspot.com/p/disclaimer.html">Disclaimer</a><a href="https://dailyyield.blogspot.com/p/privacy-policy.html">Privacy</a><a href="https://dailyyield.blogspot.com/p/terms-and-conditions.html">Terms</a></nav>
<div class="dyf-social"><p class="dyf-social-label">Follow Daily Yield</p><nav aria-label="Daily Yield social profiles" class="dyf-social-links">""" + social + """</nav></div>
<a class="dyf-subscribe" href="#dy-subscribe"><b>Make the next important story find you.</b><span>Choose your alerts →</span></a>
</section>
""" + END


def _remove_balanced_element(content, start, tag):
    """Remove one raw HTML element without reparsing or rewriting surrounding content."""
    token_re = re.compile(rf"</?{tag}\b[^>]*>", re.I)
    depth = 0
    for match in token_re.finditer(content, start):
        closing = match.group(0).lstrip().startswith("</")
        depth += -1 if closing else 1
        if depth == 0:
            end = match.end()
            # Remove the obsolete insertion anchor when it immediately precedes the block.
            prefix = content[:start]
            prefix = re.sub(r'<span id=["\']enh-added-start["\']></span>\s*$', '', prefix, flags=re.I)
            return prefix + content[end:]
    return content


def remove_legacy_explore_blocks(content):
    """Delete the older small connected-desk cards while preserving dyPageFamily."""
    while True:
        found = None
        # Most pages use explicit IDs.
        for rx, tag in [
            (r'<section\b[^>]*id=["\']enh-connected-desks["\'][^>]*>', 'section'),
            (r'<section\b[^>]*id=["\']enh-new-chapter["\'][^>]*>', 'section'),
        ]:
            m = re.search(rx, content, re.I)
            if m and (found is None or m.start() < found[0]):
                found = (m.start(), tag)
        # Daily News used an un-ID'd module beginning with this exact kicker.
        marker = re.search(r'<span\b[^>]*class=["\']enh-kicker["\'][^>]*>\s*Continue exploring\s*</span>', content, re.I)
        if marker:
            opener = list(re.finditer(r'<div\b[^>]*class=["\'][^"\']*\benh-module\b[^"\']*["\'][^>]*>', content[:marker.start()], re.I))
            if opener:
                candidate = (opener[-1].start(), 'div')
                if found is None or candidate[0] < found[0]:
                    found = candidate
        if found is None:
            return content
        updated = _remove_balanced_element(content, found[0], found[1])
        if updated == content:
            return content
        content = updated


def ensure_subscription_privacy(content, current_path=""):
    """Disclose the external opt-in processor on the Privacy Policy page."""
    pattern = re.escape(PRIVACY_SUB_START) + r".*?" + re.escape(PRIVACY_SUB_END)
    content = re.sub(pattern, "", content or "", flags=re.S).rstrip()
    if current_path != "/p/privacy-policy.html":
        return content
    block = PRIVACY_SUB_START + """
<section aria-labelledby="dySubscriptionPrivacyTitle" id="dy-subscription-privacy" style="margin:38px 0;padding:clamp(22px,4vw,34px);border:1px solid #eadcc8;border-radius:18px;background:#fffaf1;color:#241610">
<h2 id="dySubscriptionPrivacyTitle" style="margin-top:0">Email and notification subscriptions</h2>
<p>Daily Yield offers voluntary email and notification subscriptions through <a href="https://follow.it" rel="noopener" target="_blank">follow.it</a>, an external delivery provider. When you submit an email address, follow.it receives that address, sends a confirmation request and records the delivery choices you make. Depending on your selection, it may also process subscription status, delivery and engagement information needed to operate the service.</p>
<p>Browser alerts are enabled only after you make a separate choice and grant the relevant browser or provider permission. Following Daily Yield through Google/Blogger is also a separate action governed by your Google account and Blogger settings. Daily Yield does not silently activate either permission.</p>
<p>You can unsubscribe or change frequency through the controls included with the delivered messages or through follow.it. Do not submit another person’s address. For provider-specific retention, security and rights information, review <a href="https://follow.it/info/privacy" rel="noopener" target="_blank">follow.it’s privacy information</a>. The standard contact address for Daily Yield remains dailyyield.official@gmail.com.</p>
</section>
""" + PRIVACY_SUB_END
    return content + "\n" + block


def ensure_family(content, current_path=""):
    """Keep one full family directory, privacy disclosures and no obsolete cards."""
    content = ensure_page_meta(content, current_path)
    content = ensure_social_identity(content)
    content = ensure_brand_identity(content)
    content = ensure_subscription_privacy(content, current_path)
    content = remove_legacy_explore_blocks(content)
    content = content.replace("/p/share-market_0718113516.html", "/p/global-snapshot.html")
    content = content.replace("MARKET EXPLORER", "GLOBAL SNAPSHOT").replace("Market Explorer", "Global Snapshot")
    content = content.replace("SHARE &amp; MARKET", "GLOBAL SNAPSHOT").replace("Share &amp; Market", "Global Snapshot")
    pattern = re.escape(START) + r".*?" + re.escape(END)
    content, count = re.subn(pattern, lambda _m: family_block(current_path), content, flags=re.S)
    if not count:
        content = content.rstrip() + "\n" + family_block(current_path)
    return content
