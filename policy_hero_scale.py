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
/* Match the shared Daily Yield kvP hero scale; do not enlarge rotating words. */
.kvP-hero .kvP-h1{font-size:clamp(30px,5vw,52px)!important;line-height:1.08!important}
.kvP-hero .kvP-flip i{font-size:.98em!important;line-height:1.08!important}
@media(max-width:640px){.kvP-hero .kvP-h1{font-size:clamp(24px,5.8vw,34px)!important}}
</style>""" + END


def ensure_policy_hero_scale(content, path):
    content = content or ""
    # Repair selectors previously damaged when prose punctuation cleanup treated
    # the dot in a CSS descendant class as punctuation.
    content = content.replace("#enhancedSite.kvP-in.kvP-h1", "#enhancedSite .kvP-in .kvP-h1")
    content = content.replace("#enhancedSite.kc-htop h1", "#enhancedSite .kc-htop h1")
    content = re.sub(re.escape(START) + r".*?" + re.escape(END), "", content, flags=re.S).rstrip()
    if path in TARGETS:
        content += "\n" + BLOCK
    return content
