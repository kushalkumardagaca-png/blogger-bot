"""Keep rotating-word policy-page heroes at the established Daily Yield scale."""
import re

START = "<!-- DY_POLICY_HERO_SCALE_START -->"
END = "<!-- DY_POLICY_HERO_SCALE_END -->"
TARGETS = {
    "/p/about-us_02080501126.html",
    "/p/contact-us_01883938366.html",
    "/p/privacy-policy.html",
    "/p/disclaimer.html",
}

BLOCK = START + """<style>
/* Match the shared Daily Yield hero: copy left, rotating ledger right. */
.kvP-hero>.kvP-in{display:grid!important;grid-template-columns:minmax(0,1.04fr) minmax(280px,.96fr)!important;gap:clamp(18px,4vw,52px)!important;align-items:center!important;max-width:1160px!important;margin:0 auto!important}
.kvP-hero>.kvP-in>.kvP-copy{min-width:0!important;text-align:left!important}
.kvP-hero>.kvP-in>.kvP-panel{width:100%!important;min-width:0!important;max-width:370px!important;justify-self:end!important}
.kvP-hero .kvP-h1{font-size:clamp(30px,5vw,52px)!important;line-height:1.08!important}
.kvP-hero .kvP-flip i{font-size:.98em!important;line-height:1.08!important}
/* Restore nested icon geometry and local-navigation spacing. */
.kvP-about .card .ico,.kvP-disclaimer .key .ico{display:grid!important;width:52px!important;height:52px!important;place-items:center;border-radius:14px;background:var(--accent-soft,#F5E7D6);color:var(--accent-dark,#9C4522);margin-bottom:18px}
.kvP-about .card .ico svg,.kvP-disclaimer .key .ico svg{display:block!important;width:24px!important;height:24px!important;fill:none!important;stroke:currentColor!important;stroke-width:1.7!important;stroke-linecap:round;stroke-linejoin:round}
.pr-local-nav{display:flex!important;align-items:center!important;flex-wrap:wrap!important;column-gap:8px!important;row-gap:4px!important}.pr-local-nav a{display:inline-flex!important;width:auto!important;padding:8px 10px!important}
/* Privacy switches: label and state must never collide. */
.kvP-privacy .kvP-switches .kvP-swrow{display:flex!important;align-items:center!important;justify-content:space-between!important;gap:12px!important}.kvP-privacy .kvP-swrow>.kvP-sw{display:inline-flex!important;flex:0 0 auto!important;align-items:center!important;gap:8px!important}
@media(max-width:640px){.kvP-hero{padding:20px 10px!important}.kvP-hero>.kvP-in{grid-template-columns:minmax(0,1fr) minmax(140px,.9fr)!important;gap:10px!important}.kvP-hero .kvP-h1{font-size:clamp(21px,6vw,28px)!important}.kvP-hero>.kvP-in>.kvP-panel{max-width:100%!important;padding:10px!important}.kvP-hero .kvP-slide{padding:12px 9px!important}.kvP-privacy .kvP-switches .kvP-swrow{display:block!important;padding:8px 0!important}.kvP-privacy .kvP-swrow>.kvP-sw{display:flex!important;justify-content:space-between!important;width:100%!important;margin-top:6px!important}.pr-local-nav{column-gap:4px!important}.pr-local-nav a{padding:7px 8px!important}}
</style>""" + END


def ensure_policy_hero_scale(content, path):
    content = content or ""
    # Repair selectors previously damaged when prose punctuation cleanup treated
    # the dot in a CSS descendant class as punctuation.
    repairs = {
        "#enhancedSite.kvP-in.kvP-h1": "#enhancedSite .kvP-in .kvP-h1",
        "#enhancedSite.kc-htop h1": "#enhancedSite .kc-htop h1",
        ".kvP-hero.kvP-in": ".kvP-hero .kvP-in",
        "#enhancedSite.kvP-in": "#enhancedSite .kvP-in",
        "#enhancedSite.kc-htop": "#enhancedSite .kc-htop",
        "#enhancedSite.pr-local-nav": "#enhancedSite .pr-local-nav",
        "#enhancedSite.pr-nav-label": "#enhancedSite .pr-nav-label",
        ".card:hover.ico": ".card:hover .ico",
        ".card.ico": ".card .ico",
        ".route:hover.rico": ".route:hover .rico",
        ".route.rico": ".route .rico",
        ".key:hover.ico": ".key:hover .ico",
        ".key.ico": ".key .ico",
        ".pledge:hover.ico": ".pledge:hover .ico",
        ".pledge.ico": ".pledge .ico",
        ".kvP-switches.kvP-swrow": ".kvP-switches .kvP-swrow",
        "#enhancedSite.kvP-swrow": "#enhancedSite .kvP-swrow",
        ".kvP-in.kvP-panel": ".kvP-in .kvP-panel",
    }
    for broken, fixed in repairs.items():
        content = content.replace(broken, fixed)
    content = re.sub(r"(\.kvP-swrow:nth-child\([^)]*\))\.kvP-sw", r"\1 .kvP-sw", content)
    content = re.sub(re.escape(START) + r".*?" + re.escape(END), "", content, flags=re.S).rstrip()
    if path in TARGETS:
        content += "\n" + BLOCK
    return content
