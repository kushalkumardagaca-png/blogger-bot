"""Build the site-wide Daily Yield subscription experience into a Blogger theme.

This module performs an idempotent source-to-output transformation. It does not
publish the theme: Blogger's API does not support theme writes, so the validated
output must be uploaded through Blogger Theme > Restore.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from lxml import etree

BLOG_ID = "8911514070006792465"
START_CSS = "/* DY_SUBSCRIPTION_CSS_START */"
END_CSS = "/* DY_SUBSCRIPTION_CSS_END */"
START_HTML = "<!-- DY_SUBSCRIPTION_PANEL_START -->"
END_HTML = "<!-- DY_SUBSCRIPTION_PANEL_END -->"
START_JS = "<!-- DY_SUBSCRIPTION_JS_START -->"
END_JS = "<!-- DY_SUBSCRIPTION_JS_END -->"

CSS = r'''/* DY_SUBSCRIPTION_CSS_START */
.dy-follow-lock,.dy-follow-lock body{overflow:hidden!important}.dy-follow-lock body::before{content:"";position:fixed;z-index:235;inset:0;background:rgba(248,240,227,.22);-webkit-backdrop-filter:blur(13px) saturate(.78);backdrop-filter:blur(13px) saturate(.78);pointer-events:auto}
.dy-follow-popup{position:fixed;z-index:240;left:50%;top:50%;width:min(560px,calc(100% - 28px));transform:translate(-50%,-50%);padding:clamp(30px,5vw,42px);text-align:center;border:1px solid #d9b985;border-radius:26px;background:rgba(255,248,239,.95);box-shadow:0 38px 120px rgba(56,31,15,.40);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px);display:none;overflow:hidden}.dy-follow-popup.dy-open{display:block}.dy-follow-popup::before{content:"";position:absolute;inset:0;border-radius:inherit;background:linear-gradient(120deg,rgba(255,255,255,.68),transparent 48%);pointer-events:none}.dy-follow-popup>*{position:relative}
.dy-follow-close{position:absolute;z-index:2;right:14px;top:14px;width:40px;height:40px;display:grid;place-items:center;border:1px solid #dbc6aa;border-radius:50%;background:rgba(255,255,255,.78);color:#4e392b;font:500 24px/1 var(--font-body)}
.dy-follow-icon{width:62px;height:62px;margin:0 auto 17px;border-radius:19px;display:grid;place-items:center;color:#fff;background:linear-gradient(145deg,var(--accent),var(--accent-dark));box-shadow:0 14px 28px -16px rgba(156,69,34,.9)}.dy-follow-icon svg{width:30px;height:30px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.dy-follow-kicker{margin:0 44px 10px;color:var(--accent-dark);font:800 9px/1.3 var(--font-body);letter-spacing:.2em;text-transform:uppercase}.dy-follow-popup h2{margin:0 36px 0;color:var(--ink);font:700 clamp(31px,5vw,44px)/1.06 var(--font-display);letter-spacing:-.035em}.dy-follow-copy{max-width:430px;margin:14px auto 22px;color:var(--muted);font-size:13px;line-height:1.65}
.dy-follow-button{display:flex;width:100%;min-height:62px;align-items:center;justify-content:center;gap:10px;border:1px solid var(--accent-dark);border-radius:15px;background:linear-gradient(120deg,var(--accent-dark),var(--accent),#d67c50);color:#fff8ee;font:800 15px/1 var(--font-body);letter-spacing:.06em;text-transform:uppercase;box-shadow:0 16px 32px -18px rgba(156,69,34,.9);transition:transform .25s,box-shadow .25s}.dy-follow-button:hover{transform:translateY(-2px);box-shadow:0 19px 36px -17px rgba(156,69,34,.95)}.dy-follow-button svg{width:21px;height:21px;fill:none;stroke:currentColor;stroke-width:1.8}.dy-follow-note{margin:13px 0 0;color:#887664;font-size:10px;line-height:1.45}
@media(max-width:560px){.dy-follow-popup{width:calc(100% - 18px);padding:29px 19px 24px}.dy-follow-popup h2{font-size:31px;margin-inline:26px}.dy-follow-close{right:10px;top:10px}.dy-follow-button{min-height:58px}}
@media(prefers-reduced-motion:reduce){.dy-follow-button{transition:none}}
/* DY_SUBSCRIPTION_CSS_END */'''

HTML = r'''<!-- DY_SUBSCRIPTION_PANEL_START -->
<section aria-labelledby='dyFollowTitle' aria-modal='true' class='dy-follow-popup' id='dyFollowPopup' role='dialog'>
 <button aria-label='Close follow invitation' class='dy-follow-close' id='dyFollowClose' type='button'>&#215;</button>
 <span aria-hidden='true' class='dy-follow-icon'><svg viewBox='0 0 24 24'><path d='M7 4h6a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3v4a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8a4 4 0 0 1 3-4Z'/><path d='M8 9h5M8 15h8'/></svg></span>
 <p class='dy-follow-kicker'>Follow Daily Yield</p>
 <h2 id='dyFollowTitle'>Keep the next useful story within reach.</h2>
 <p class='dy-follow-copy'>Add Daily Yield to the Blogger Reading List connected to your Google account.</p>
 <a class='dy-follow-button' href='https://www.blogger.com/followers/follow/8911514070006792465' id='dyFollowButton' rel='noopener' target='_blank'><span>Follow</span><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M5 12h14M13 6l6 6-6 6'/></svg></a>
 <p class='dy-follow-note'>Google may ask you to sign in or confirm the follow.</p>
</section>
<!-- DY_SUBSCRIPTION_PANEL_END -->'''

JS = r'''<!-- DY_SUBSCRIPTION_JS_START -->
<script>//<![CDATA[
(function(){'use strict';var D=document,H=D.documentElement,popup=D.getElementById('dyFollowPopup'),close=D.getElementById('dyFollowClose'),follow=D.getElementById('dyFollowButton');if(!popup||!close||!follow||!/^\/\d{4}\/\d{2}\/[^/]+\.html$/.test(location.pathname))return;var key='dy-google-follow-intent-v1',dismissed=false,opened=false;try{if(localStorage.getItem(key)==='followed')return}catch(e){}function setOpen(open){opened=open;popup.classList.toggle('dy-open',open);H.classList.toggle('dy-follow-lock',open);if(open)setTimeout(function(){follow.focus()},0)}function eligible(){var max=Math.max(1,D.documentElement.scrollHeight-innerHeight),progress=scrollY/max;if(!dismissed&&!opened&&progress>=.20&&!H.classList.contains('dy-privacy-lock'))setOpen(true)}close.addEventListener('click',function(){dismissed=true;setOpen(false)});follow.addEventListener('click',function(){try{localStorage.setItem(key,'followed')}catch(e){}setOpen(false)});D.addEventListener('keydown',function(e){if(!opened)return;if(e.key==='Escape'){e.preventDefault();dismissed=true;setOpen(false)}else if(e.key==='Tab'){var first=close,last=follow;if(e.shiftKey&&D.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&D.activeElement===last){e.preventDefault();first.focus()}}});addEventListener('scroll',eligible,{passive:true});new MutationObserver(eligible).observe(H,{attributes:true,attributeFilter:['class']});eligible();H.setAttribute('data-dy-follow','article-20-percent');})();
//]]></script>
<!-- DY_SUBSCRIPTION_JS_END -->'''

ACTIVE_SOCIAL = '''<div class='fd-soc'>
 <a aria-label='Facebook' href='https://www.facebook.com/1303333369533572' rel='me noopener' target='_blank'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M13.5 21v-8h2.8l.4-3h-3.2V8.1c0-.9.3-1.6 1.7-1.6H17V3.8c-.3 0-1.4-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2H7.5v3h2.8v8'/></svg></a>
 <a aria-label='Bluesky' href='https://bsky.app/profile/dailyyield.bsky.social' rel='me noopener' target='_blank'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M12 11c-1.2-2.5-4.4-6-7.3-8C2 1.2 1 1.5 1 4.2c0 .6.3 5.2.5 5.9.8 2.6 3.7 3.5 6.3 3-4.5.7-5.7 3-3.2 5.3 4.8 4.4 6.8-1 7.4-2.7.6 1.7 2.1 7.1 7.3 2.7 2.7-2.3 1.2-4.6-3.3-5.3 2.6.5 5.5-.4 6.3-3 .2-.7.5-5.3.5-5.9C23 1.5 22 1.2 19.3 3 16.4 5 13.2 8.5 12 11Z'/></svg></a>
 <a aria-label='Tumblr' href='https://www.tumblr.com/dailyyield-official' rel='me noopener' target='_blank'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M14 21c-4.1 0-6-2.4-6-5.8V10H5V6.7c3.2-1.1 4.6-3.5 4.8-5.7H13v5h4v4h-4v4.5c0 1.7.9 2.3 2.1 2.3.7 0 1.3-.2 1.9-.5V20c-.8.6-1.8 1-3 1Z'/></svg></a>
 <a aria-label='Mastodon' href='https://mastodon.social/@dailyyield' rel='me noopener' target='_blank'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M20 15c-.4 2.1-3.8 2.3-5.8 2.6-1.1.1-2.2.1-3.3-.1.2 1.7 1.3 2.4 3 2.5 1.8.1 3.4-.4 4.5-1l.1 2.3c-1.3.7-3.1 1-4.8 1-5.2-.2-8.6-3.2-8.9-8.8-.1-1.2 0-4.7 0-5.6C4.9 4 7.5 2.8 12 2.8S19.1 4 19.4 7.9c.1 1 .1 5.4-.4 7.1Z'/><path d='M8.5 13V8.3c0-2.4 3.1-2.5 3.5-.5.4-2 3.5-1.9 3.5.5V13M12 8v4.3'/></svg></a>
 <a aria-label='Email' href='mailto:dailyyield.official@gmail.com'><svg aria-hidden='true' viewBox='0 0 24 24'><rect height='13' rx='1.5' width='18' x='3' y='5.5'/><path d='m4 7.5 8 5.5 8-5.5'/></svg></a>
 </div>'''

NEW_ENGAGE = '''<section class='kd-sec kd-engage' id='kd-engage'><h2>Read it? Question it.</h2><p>Challenge the arithmetic, request a correction or suggest the next tool. Every serious note reaches the Daily Yield editorial desk.</p>
<div class='kd-eg-row'>
<a class='kd-eg' href='mailto:dailyyield.official@gmail.com'><span class='kd-eg-icon'><svg aria-hidden='true' viewBox='0 0 24 24'><rect height='14' rx='2' width='18' x='3' y='5'/><path d='m4.5 7 7.5 5.5L19.5 7'/></svg></span><span class='kd-eg-copy'><strong>Email the editorial desk</strong><small>dailyyield.official@gmail.com</small></span><span aria-hidden='true' class='kd-eg-arrow'>&#8594;</span></a>
<a class='kd-eg' href='https://dailyyield.blogspot.com/p/contact-us_01883938366.html'><span class='kd-eg-icon'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M5 5h14v11H9l-4 4Z'/><path d='M8 9h8M8 12h5'/></svg></span><span class='kd-eg-copy'><strong>Open the contact desk</strong><small>Corrections, questions and partnership enquiries</small></span><span aria-hidden='true' class='kd-eg-arrow'>&#8594;</span></a>
</div><p class='kd-eg-fine'>Replies usually arrive within 24&#8211;48 hours &#183; comments remain open on every Post</p></section>'''


def _replace_marked(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    return re.sub(pattern, lambda _: replacement, text, flags=re.S)


def build(source: Path, output: Path) -> dict[str, int]:
    text = source.read_text(encoding="utf-8")
    # Idempotently remove a prior build.
    text = _replace_marked(text, START_CSS, END_CSS, "")
    text = _replace_marked(text, START_HTML, END_HTML, "")
    text = _replace_marked(text, START_JS, END_JS, "")

    skin_close = "]]></b:skin>"
    if skin_close not in text:
        raise ValueError("Blogger skin closing marker not found")
    text = text.replace(skin_close, "\n" + CSS + "\n" + skin_close, 1)

    footer_marker = "<!-- ================= Footer : attribution ================= -->"
    if footer_marker not in text:
        raise ValueError("Footer insertion marker not found")
    text = text.replace(footer_marker, HTML + "\n\n " + footer_marker, 1)

    body_close = "</body>"
    if body_close not in text:
        raise ValueError("Closing body not found")
    text = text.replace(body_close, JS + "\n" + body_close, 1)

    # Sync footer promotion with the four currently active profiles.
    identity_pos = text.find("<span class='ft-by'>By Kushal K. Daga</span>")
    if identity_pos < 0:
        raise ValueError("Footer identity anchor not found")
    old_social = re.search(r"<div class='fd-soc'>.*?</div>", text[identity_pos:], re.S)
    if not old_social:
        raise ValueError("Footer social block not found")
    a, b = identity_pos + old_social.start(), identity_pos + old_social.end()
    text = text[:a] + ACTIVE_SOCIAL + text[b:]

    # Replace the small text-only homepage contact pills with a visual contact desk.
    engage_pattern = r"<section class='kd-sec kd-engage' id='kd-engage'>.*?</section>"
    text, engage_count = re.subn(engage_pattern, NEW_ENGAGE, text, count=1, flags=re.S)
    if engage_count != 1:
        raise ValueError("Homepage engagement section not found")

    # Expose Blogger's real featured image on each Popular Posts link. The home
    # rail can then reuse it without opening Posts or creating synthetic views.
    popular_anchor = "<a expr:href='data:post.url'><data:post.title/></a>"
    popular_anchor_new = "<a expr:href='data:post.url'><b:attr cond='data:post.featuredImage' expr:value='resizeImage(data:post.featuredImage, 640, &quot;16:9&quot;)' name='data-kd-img'/><data:post.title/></a>"
    popular_widget = text.find("<b:widget id='PopularPosts1'")
    popular_link = text.find(popular_anchor, popular_widget)
    if popular_widget < 0 or popular_link < 0:
        raise ValueError("Popular Posts anchor not found")
    text = text[:popular_link] + popular_anchor_new + text[popular_link + len(popular_anchor):]

    # X is closed and LinkedIn is paused: remove their legacy Post share actions.
    text = re.sub(r"\s*<a\s+expr:href='&quot;https://twitter\.com/intent/tweet\?text=.*?</a>", "", text, flags=re.S)
    text = re.sub(r"\s*<a\s+expr:href='&quot;https://www\.linkedin\.com/sharing/share-offsite/\?url=.*?</a>", "", text, flags=re.S)

    # Give both Master Article rails continuous, swipe-safe movement. The rail
    # clones only already-rendered cards and pauses after reader interaction.
    fill_code = """function fill(row,items){
 row.innerHTML='';
 if(!items.length)return false;
 items.forEach(function(it){row.appendChild(card(it));});
 return true;
}"""
    rail_code = fill_code + """
function autoRail(row,speed){
 if(!row||row.children.length<2)return;
 [].slice.call(row.querySelectorAll('[data-kd-clone]')).forEach(function(n){n.remove();});
 var originals=[].slice.call(row.children);
 originals.forEach(function(n){var c=n.cloneNode(true);c.setAttribute('data-kd-clone','1');c.setAttribute('aria-hidden','true');c.tabIndex=-1;row.appendChild(c);});
 row.setAttribute('data-kd-auto','1');
 requestAnimationFrame(function(){row._kdLoop=row.children[originals.length].offsetLeft-row.children[0].offsetLeft;});
 if(row._kdWired)return;row._kdWired=true;
 var pauseUntil=0,last=0;
 function pause(){pauseUntil=Date.now()+4500;}
 row.addEventListener('pointerdown',pause,{passive:true});row.addEventListener('touchstart',pause,{passive:true});row.addEventListener('wheel',pause,{passive:true});
 row.addEventListener('mouseenter',function(){pauseUntil=Infinity;});row.addEventListener('mouseleave',function(){pauseUntil=Date.now()+900;});
 function tick(ts){if(!last)last=ts;var dt=Math.min(.05,(ts-last)/1000);last=ts;
 if(!rm&&Date.now()>pauseUntil&&row._kdLoop>0&&D.visibilityState==='visible'){row.scrollLeft+=speed*dt;if(row.scrollLeft>=row._kdLoop)row.scrollLeft-=row._kdLoop;}
 requestAnimationFrame(tick);}
 requestAnimationFrame(tick);
}"""
    if text.count(fill_code) != 1:
        raise ValueError("Homepage article fill function not found")
    text = text.replace(fill_code, rail_code, 1)

    old_popular = """var items=parse(j,false).slice(0,10);
 if(!fill(latest,items))emptyBox(latest,'Waiting for your first post','This row fills with your latest general articles the moment you publish \\u2014 no placeholders, no invented headlines.');
 var pp=D.getElementById('PopularPosts1');
 var links=pp?[].slice.call(pp.querySelectorAll('a[href]')).slice(0,8):[];
 if(links.length){fill(pop,links.map(function(a){return {title:a.textContent.replace(/\\s+/g,' ').trim(),href:a.getAttribute('href'),meta:'Reader favourite \\u00b7 most-visited',letter:(a.textContent.trim()||'\\u2733').charAt(0).toUpperCase(),img:''};}));}
 else emptyBox(pop,'No popular picks yet','Popularity follows readership \\u2014 until then the latest row above keeps this desk company.');"""
    new_popular = """var items=parse(j,false).slice(0,10);
 if(!fill(latest,items))emptyBox(latest,'Waiting for your first post','This row fills with your latest general articles the moment you publish \\u2014 no placeholders, no invented headlines.');
 else autoRail(latest,31);
 var pp=D.getElementById('PopularPosts1');
 var links=pp?[].slice.call(pp.querySelectorAll('a[href]')).slice(0,8):[];
 if(links.length){fill(pop,links.map(function(a){var title=a.textContent.replace(/\\s+/g,' ').trim();return {title:title,href:a.getAttribute('href'),meta:'Reader favourite \\u00b7 most-visited',letter:(title||'\\u2733').charAt(0).toUpperCase(),img:a.getAttribute('data-kd-img')||''};}));autoRail(pop,24);}
 else emptyBox(pop,'No popular picks yet','Popularity follows readership \\u2014 until then the latest row above keeps this desk company.');"""
    if text.count(old_popular) != 1:
        raise ValueError("Homepage Popular Posts builder not found")
    text = text.replace(old_popular, new_popular, 1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")

    parser = etree.XMLParser(recover=False, huge_tree=True)
    etree.fromstring(text.encode("utf-8"), parser)
    checks = {
        "all_head_content": text.count("name='all-head-content'"),
        "canonical_references": text.count("data:blog.canonicalUrl"),
        "noindex_tokens": len(re.findall(r"\bnoindex\b", text, re.I)),
        "subscription_panels": text.count(START_HTML),
        "subscription_css": text.count(START_CSS),
        "subscription_js": text.count(START_JS),
        "follow_it_forms": text.count("https://api.follow.it/subscribe"),
        "blogger_follow_links": text.count(f"https://www.blogger.com/followers/follow/{BLOG_ID}"),
        "all_linkedin_links": len(re.findall(r"linkedin\.com", text, re.I)),
        "popular_featured_images": text.count("name='data-kd-img'"),
        "moving_article_rails": text.count("function autoRail"),
        "contact_email_cards": text.count("Email the editorial desk"),
        "contact_page_cards": text.count("Open the contact desk"),
        "css_checkmark_escape": text.count(r'content:"\2713"'),
    }
    required = {
        "all_head_content": 1,
        "canonical_references": 1,
        "noindex_tokens": 0,
        "subscription_panels": 1,
        "subscription_css": 1,
        "subscription_js": 1,
        "follow_it_forms": 0,
        "blogger_follow_links": 1,
        "legacy_twitter_shares": 0,
        "legacy_linkedin_shares": 0,
        "all_linkedin_links": 0,
        "popular_featured_images": 1,
        "moving_article_rails": 1,
        "contact_email_cards": 1,
        "contact_page_cards": 1,
        "css_checkmark_escape": 0,
    }
    if checks != required:
        raise ValueError(f"Theme invariant failure: {checks!r} != {required!r}")
    return checks


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    checks = build(args.source, args.output)
    print("Valid Blogger XML generated:", args.output)
    for key, value in checks.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
