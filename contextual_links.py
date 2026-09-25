"""Compact, contextual Daily Yield cross-links for articles and news stories."""
import html
import re

BLOG = "https://dailyyield.blogspot.com"
STYLE = """<!-- DY_CONTEXT_STYLE_START -->
<style id="dyContextStyle">
.dy-context{display:block;margin:12px 0 4px;padding:12px 14px;border:1px solid #eadcc8;border-left:3px solid #bc5b33;border-radius:10px;background:linear-gradient(135deg,#fffdf8,#fff8ee);color:#241610;text-decoration:none;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-sizing:border-box}
.dy-context:hover{border-color:#c99770;box-shadow:0 7px 18px rgba(75,43,20,.08);transform:translateY(-1px)}.dy-context:focus-visible{outline:3px solid rgba(156,69,34,.25);outline-offset:2px}.dy-context b{display:block;margin:0 0 3px;color:#9c4522;font-size:9px;line-height:1.3;letter-spacing:.14em;text-transform:uppercase}.dy-context strong{display:block;font:700 16px/1.25 Georgia,serif}.dy-context span{display:block;margin-top:4px;color:#6e5d4b;font-size:11px;line-height:1.45}.dy-context em{display:block;margin-top:6px;color:#9c4522;font-size:9px;font-style:normal;font-weight:900;letter-spacing:.1em;text-transform:uppercase}
</style>
<!-- DY_CONTEXT_STYLE_END -->"""

DESTINATIONS = [
    (r"\b(sip|systematic investment|mutual fund|monthly invest|recurring invest|compound(?:ing)?|rupee.cost)\b",
     "SIP Calculator", "/p/calculator_0908148622.html#kc-sip",
     "Model monthly contributions, time and expected growth."),
    (r"\b(mortgage|home loan|housing loan|emi|borrow|loan repayment|interest cost|debt payment)\b",
     "EMI & Loan Calculator", "/p/calculator_0908148622.html#kc-emi",
     "Test the payment, interest cost and repayment period."),
    (r"\b(retire|retirement|pension|fire|financial independence|future value)\b",
     "Retirement & Future Planning", "/p/calculator_0908148622.html#calc-future",
     "Turn a long-term goal into a measurable contribution plan."),
    (r"\b(stock|share|equity|bond|yield|trading|market|index|forex|currency|bitcoin|crypto|gold|oil|commodity|ipo)\b",
     "Markets Today", "/p/markets-today.html",
     "Check the wider cross-asset market picture and reference data."),
    (r"\b(company|corporate|earnings|merger|acquisition|cash flow|working capital|business|industry)\b",
     "For Corporate", "/p/for-corporate_01804417406.html",
     "Continue with Daily Yield resources for business decisions."),
    (r"\b(country|countries|economy|economic|inflation|gdp|central bank|policy rate|fiscal|unemployment|trade)\b",
     "Global Snapshot", "/p/global-snapshot.html",
     "Place this development in the broader global market context."),
    (r"\b(tax|budget|saving|emergency fund|insurance|net worth|personal finance|paycheck|salary)\b",
     "Daily Yield Calculators", "/p/calculator_0908148622.html",
     "Translate the idea into numbers with practical planning tools."),
]


def pick_destination(text, fallback="snapshot"):
    plain = re.sub(r"<[^>]+>", " ", text or "").lower()
    for pattern, title, path, description in DESTINATIONS:
        if re.search(pattern, plain, re.I):
            return title, BLOG + path, description
    if fallback == "articles":
        return ("Daily Article", BLOG + "/p/article.html",
                "Read the latest Daily Yield explainers and practical guides.")
    return ("Global Snapshot", BLOG + "/p/global-snapshot.html",
            "See the concise cross-asset context behind this development.")


def card(text, fallback="snapshot"):
    title, url, description = pick_destination(text, fallback)
    return (f'<a class="dy-context" href="{html.escape(url, quote=True)}" '
            f'aria-label="Continue to {html.escape(title, quote=True)}">'
            f'<b>Continue with Daily Yield</b><strong>{html.escape(title)}</strong>'
            f'<span>{html.escape(description)}</span><em>Open tool or page →</em></a>')
