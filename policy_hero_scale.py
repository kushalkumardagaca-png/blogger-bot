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
@media(max-width:640px){.kvP-hero{padding:20px 10px!important}.kvP-hero>.kvP-in{grid-template-columns:minmax(0,1fr) minmax(140px,.9fr)!important;gap:10px!important}.kvP-hero .kvP-h1{font-size:clamp(21px,6vw,28px)!important}.kvP-hero>.kvP-in>.kvP-panel{max-width:100%!important;padding:10px!important}.kvP-hero .kvP-slide{padding:12px 9px!important}}
</style>""" + END


def ensure_policy_hero_scale(content, path):
    content = content or ""
    # Repair selectors previously damaged when prose punctuation cleanup treated
    # the dot in a CSS descendant class as punctuation.
    content = content.replace("#enhancedSite.kvP-in.kvP-h1", "#enhancedSite .kvP-in .kvP-h1")
    content = content.replace("#enhancedSite.kc-htop h1", "#enhancedSite .kc-htop h1")
    content = content.replace(".kvP-hero.kvP-in", ".kvP-hero .kvP-in")
    content = content.replace("#enhancedSite.kvP-in", "#enhancedSite .kvP-in")
    content = content.replace("#enhancedSite.kc-htop", "#enhancedSite .kc-htop")
    content = re.sub(re.escape(START) + r".*?" + re.escape(END), "", content, flags=re.S).rstrip()
    if path in TARGETS:
        content += "\n" + BLOCK
    return content
