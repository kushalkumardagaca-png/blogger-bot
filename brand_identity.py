"""Idempotent Daily Yield browser branding for Blogger content.

Blogger's v3 content API cannot edit the theme head or native favicon setting. This
small zero-network runtime updates the already-rendered document head from every
Page/Post package. Embedding the SVG as a data URI avoids an external asset host
and cannot create a Daily Yield pageview.
"""
import base64
import re

START = "<!-- DY_BRAND_IDENTITY_START -->"
END = "<!-- DY_BRAND_IDENTITY_END -->"

_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="116" fill="#241610"/><rect x="21" y="21" width="470" height="470" rx="96" fill="none" stroke="#c86a3d" stroke-width="14"/><circle cx="402" cy="106" r="19" fill="#f0b180"/><text x="108" y="316" fill="#fff8ee" font-family="Georgia,serif" font-size="226" font-weight="700">D</text><text x="257" y="316" fill="#fff8ee" font-family="Georgia,serif" font-size="226" font-weight="700">Y</text><path d="M94 384c72-10 112-43 168-31 63 13 102-39 166-57" fill="none" stroke="#f0b180" stroke-width="18" stroke-linecap="round"/><path d="m389 286 43 7-20 38" fill="none" stroke="#f0b180" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/></svg>"""
FAVICON_DATA_URI = "data:image/svg+xml;base64," + base64.b64encode(_FAVICON_SVG.encode()).decode()


def brand_block():
    """Return the single self-contained head-branding runtime."""
    return START + """<script id="dyBrandIdentity">(function(){
var d=document,h=d.head||d.getElementsByTagName('head')[0],u=%r;
if(!h)return;
var icons=d.querySelectorAll('link[rel~="icon"]');
for(var i=0;i<icons.length;i++){icons[i].href=u;icons[i].type='image/svg+xml'}
if(!icons.length){var l=d.createElement('link');l.rel='icon';l.type='image/svg+xml';l.href=u;h.appendChild(l)}
var s=d.querySelector('link[rel="shortcut icon"]');if(!s){s=d.createElement('link');s.rel='shortcut icon';h.appendChild(s)}s.type='image/svg+xml';s.href=u;
var a=d.querySelector('link[rel="apple-touch-icon"]');if(!a){a=d.createElement('link');a.rel='apple-touch-icon';h.appendChild(a)}a.href=u;
function meta(n,v){var m=d.querySelector('meta[name="'+n+'"]');if(!m){m=d.createElement('meta');m.name=n;h.appendChild(m)}m.content=v}
meta('theme-color','#241610');meta('application-name','Daily Yield');
})();</script>""" % FAVICON_DATA_URI + END


def ensure_brand_identity(content):
    """Insert or replace the Daily Yield branding package exactly once."""
    block = brand_block()
    pattern = re.escape(START) + r".*?" + re.escape(END)
    content, count = re.subn(pattern, lambda _m: block, content or "", flags=re.S)
    return content if count else (content or "").rstrip() + "\n" + block
