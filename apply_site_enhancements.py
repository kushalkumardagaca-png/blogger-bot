#!/usr/bin/env python3
"""Idempotently add Daily Yield's accessibility, privacy and SEO experience layer."""
from pathlib import Path
import re

THEMES = [
    Path("theme/Daily-Yield-Theme-Subscription.xml"),
    Path("theme/Daily-Yield-Theme-v4-2026-10-01.xml"),
]

HEAD = r"""<!-- DY_SITE_ENHANCEMENTS_HEAD_START -->
<b:if cond='!data:view.isSearch'>
<meta content='index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1' name='robots'/>
<meta content='index,follow,max-image-preview:large,max-snippet:-1' name='googlebot'/>
<meta content='index,follow' name='bingbot'/>
<meta content='index,follow' name='ChatGPT-User'/>
<meta content='index,follow' name='OAI-SearchBot'/>
<b:else/>
<meta content='noindex,follow' name='robots'/>
</b:if>
<meta content='light' name='color-scheme'/>
<!-- Optional analytics stays denied until the reader explicitly allows it. -->
<script>//<![CDATA[
window.dataLayer=window.dataLayer||[];
window.gtag=window.gtag||function(){window.dataLayer.push(arguments);};
window.gtag('consent','default',{analytics_storage:'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',wait_for_update:500});
//]]></script>
<!-- Blogger's universal GA4 include reads the Measurement ID from Blogger Settings. -->
<b:include data='blog' name='google-analytics'/>
<script type='application/ld+json'>{"@context":"https://schema.org","@type":"WebSite","@id":"https://dailyyield.blogspot.com/#website","url":"https://dailyyield.blogspot.com/","name":"Daily Yield","alternateName":"DAILY YIELD","publisher":{"@type":"Person","name":"Kushal K. Daga","url":"https://dailyyield.blogspot.com/p/about-us_02080501126.html"},"potentialAction":{"@type":"SearchAction","target":{"@type":"EntryPoint","urlTemplate":"https://dailyyield.blogspot.com/search?q={search_term_string}"},"query-input":"required name=search_term_string"}}</script>
<b:if cond='data:view.isHomepage'>
<script type='application/ld+json'>{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"What does Daily Yield publish?","acceptedAnswer":{"@type":"Answer","text":"Daily Yield publishes sourced personal-finance articles, market explainers, calculators and clearly timed News editions."}},{"@type":"Question","name":"Is Daily Yield personal financial advice?","acceptedAnswer":{"@type":"Answer","text":"No. Daily Yield provides educational information and arithmetic tools; readers should consider their circumstances and use an appropriately qualified adviser when needed."}},{"@type":"Question","name":"How can I report a correction?","acceptedAnswer":{"@type":"Answer","text":"Use the Daily Yield Contact desk or email dailyyield.official@gmail.com with the page URL and the correction details."}}]}</script>
</b:if>
<!-- DY_SITE_ENHANCEMENTS_HEAD_END -->"""

CSS = r"""/* DY_SITE_ENHANCEMENTS_CSS_START */
:root{color-scheme:light;--dy-focus:#0b66c3}
/* Full-screen, dependency-free finance transition. It covers genuine navigation
   gaps but never claims that animation time is network/render time. */
.dy-load-screen{position:fixed;inset:0;z-index:2147483000;display:grid;place-items:center;overflow:hidden;background:radial-gradient(circle at 50% 34%,#fffdf8 0,#fbf2e5 46%,#f4e3cf 100%);color:#241610;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .18s ease,visibility 0s linear .18s;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.dy-load-screen[data-active='true']{opacity:1;visibility:visible;pointer-events:auto;transition:opacity .12s ease}
.dy-load-screen::before,.dy-load-screen::after{content:"";position:absolute;border:1px solid rgba(188,91,51,.13);border-radius:50%;width:min(76vw,680px);aspect-ratio:1;animation:dyOrbit 5s linear infinite}.dy-load-screen::after{width:min(54vw,460px);animation-direction:reverse;animation-duration:3.8s}
.dy-load-card{position:relative;z-index:2;width:min(88vw,440px);text-align:center;padding:28px 24px}.dy-load-kicker{display:block;margin-bottom:15px;color:#9c4522;font:800 10px/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.28em;text-transform:uppercase}.dy-load-mark{width:112px;height:112px;margin:0 auto 18px;position:relative;display:grid;place-items:center;border-radius:32px;background:#bc5b33;box-shadow:0 25px 60px -30px rgba(36,22,16,.72)}
.dy-load-mark::before{content:"DY";color:#fff8ee;font:700 35px/1 Georgia,"Times New Roman",serif;letter-spacing:-.08em}.dy-load-coin{position:absolute;width:18px;height:18px;right:-6px;top:8px;border-radius:50%;background:#f0b180;border:3px solid #fff8ee;animation:dyCoin 1.5s ease-in-out infinite}
.dy-load-chart{display:block;width:210px;height:58px;margin:0 auto 15px}.dy-load-chart .dy-axis{stroke:#eadcc8;stroke-width:1}.dy-load-chart .dy-line{fill:none;stroke:#bc5b33;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:260;stroke-dashoffset:260;animation:dyDraw 1.35s cubic-bezier(.22,.61,.36,1) infinite}.dy-load-chart .dy-dot{fill:#9c4522;transform-origin:center;animation:dyPulse 1.35s ease-in-out infinite}
.dy-load-title{margin:0;color:#241610;font:700 clamp(27px,7vw,38px)/1.05 Georgia,"Times New Roman",serif;letter-spacing:-.035em}.dy-load-copy{min-height:1.5em;margin:10px 0 17px;color:#7a6a58;font:600 12px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.06em}.dy-load-track{height:3px;width:min(72vw,280px);margin:auto;overflow:hidden;border-radius:999px;background:#eadcc8}.dy-load-track span{display:block;width:45%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#bc5b33,#f0b180);animation:dyTrack 1.05s ease-in-out infinite}
@keyframes dyOrbit{to{transform:rotate(360deg)}}@keyframes dyCoin{50%{transform:translateY(-8px) rotate(18deg)}}@keyframes dyDraw{0%{stroke-dashoffset:260}62%,100%{stroke-dashoffset:0}}@keyframes dyPulse{0%,100%{opacity:.35;transform:scale(.75)}60%{opacity:1;transform:scale(1.15)}}@keyframes dyTrack{0%{transform:translateX(-110%)}100%{transform:translateX(330%)}}
/* Keep below-fold modules out of initial layout/paint work where supported. */
.site-footer,.dy-site-faq,#sidebar_feed{content-visibility:auto;contain-intrinsic-size:1px 720px}
.item-post div.post-title{font:600 clamp(27px,2.9vw,40px)/1.14 var(--font-display);letter-spacing:-.02em;margin:0 0 18px;color:var(--ink);overflow-wrap:break-word}.dy-breadcrumb{display:flex;align-items:center;gap:8px;min-height:42px;padding:8px clamp(20px,4.5vw,48px);border-bottom:1px solid var(--line);color:var(--muted);font:600 11px/1.4 var(--font-body);letter-spacing:.06em}
.dy-breadcrumb a{color:var(--accent-dark);text-decoration:underline;text-underline-offset:3px}.dy-breadcrumb span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dy-site-faq{padding:clamp(40px,6vw,80px) clamp(20px,4.5vw,48px);background:var(--surface);border-top:1px solid var(--line)}
.dy-site-faq h2{font-size:clamp(28px,4vw,48px);margin-bottom:20px}.dy-site-faq details{max-width:900px;border-top:1px solid var(--line);padding:15px 0}.dy-site-faq details:last-child{border-bottom:1px solid var(--line)}
.dy-site-faq summary{cursor:pointer;font-weight:700;list-style-position:inside}.dy-site-faq p{margin:10px 0 0;color:var(--muted)}
.dy-updated{display:inline-flex;margin:10px 0 4px;padding:6px 10px;border-radius:999px;background:var(--accent-soft);color:var(--accent-dark);font:700 10px/1.2 var(--font-body);letter-spacing:.06em;text-transform:uppercase}.dy-form-status{min-height:1.5em;margin:10px 0 0;font-size:13px;font-weight:600;color:var(--muted)}.dy-form-status[data-state='error']{color:#a32222}.dy-form-status[data-state='success']{color:#20733a}
.dy-privacy{position:fixed;z-index:260;left:18px;right:18px;bottom:18px;max-width:760px;margin:auto;padding:18px;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:0 26px 80px -32px rgba(0,0,0,.7);display:none}
.dy-privacy.dy-open{display:block}.dy-privacy-kicker{display:block;margin:0 0 8px;color:var(--accent-dark);font:800 9px/1.4 var(--font-body);letter-spacing:.18em;text-transform:uppercase}.dy-privacy h2{font:700 20px/1.2 var(--font-display);margin:0 0 7px}.dy-privacy p{font-size:13px;line-height:1.55;margin:0;color:var(--muted)}.dy-privacy-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.dy-privacy button,.dy-privacy a{display:inline-flex;min-height:42px;align-items:center;padding:10px 14px;border:1px solid var(--line);border-radius:999px;font:700 12px/1 var(--font-body)}.dy-privacy .dy-primary{background:var(--accent-dark);color:#fff;border-color:var(--accent-dark)}.fk-home .dy-privacy{position:relative;left:auto;right:auto;bottom:auto;max-width:1080px;margin:24px auto;padding:clamp(20px,3.5vw,34px);border-radius:22px;background:linear-gradient(145deg,#fffaf0,#f5e5cf);box-shadow:0 24px 60px -42px rgba(36,22,16,.58)}.fk-home .dy-privacy h2{font-size:clamp(24px,3.4vw,38px);max-width:760px}.fk-home .dy-privacy p{max-width:850px;font-size:clamp(12px,1.4vw,14px);line-height:1.7}.fk-home .dy-privacy-actions{margin-top:18px}
.site-footer .ft-page-links .dy-privacy-manage{display:flex;width:100%;align-items:center;justify-content:space-between;gap:14px;min-height:46px;box-sizing:border-box;padding:10px 0;border:0;border-bottom:1px solid #b58e5d26;border-radius:0;background:transparent;color:#e8d7be;font:400 13px/1.6 var(--font-body,Inter,Arial,sans-serif);text-align:left;cursor:pointer}.site-footer .ft-page-links .dy-privacy-manage::after{content:'\2192';font-size:15px;color:#b58c5b;transition:transform .2s}.site-footer .ft-page-links .dy-privacy-manage:hover{color:#fff5e5;border-color:#c79860}.site-footer .ft-page-links .dy-privacy-manage:hover::after{transform:translateX(3px);color:#efbd7b}
.dy-password-wrap{position:relative}.dy-password-toggle{position:absolute;right:8px;top:50%;transform:translateY(-50%);padding:7px;border-radius:6px;font-size:12px;background:var(--surface);border:1px solid var(--line)}
@media print{.dy-privacy,.dy-privacy-manage,.dy-site-faq,.dy-breadcrumb,.dy-form-status{display:none!important}body{background:#fff!important;color:#000!important}.item-post .post-body,.page-body{font-size:11pt!important;line-height:1.5!important;color:#000!important}a[href]::after{content:" (" attr(href) ")";font-size:8pt;overflow-wrap:anywhere}}
@media(max-width:560px){.dy-privacy{left:8px;right:8px;bottom:8px}.fk-home .dy-privacy{left:auto;right:auto;bottom:auto;margin:14px 10px}.dy-privacy-actions>*{flex:1 1 140px;justify-content:center}.dy-breadcrumb{padding-right:58px}}
@media(prefers-reduced-motion:reduce){.dy-load-screen,.dy-load-screen *{animation:none!important;transition:none!important}.dy-load-chart .dy-line{stroke-dashoffset:0}.dy-load-track span{width:100%;transform:none}}
/* DY_SITE_ENHANCEMENTS_CSS_END */"""

LOADER = r"""<!-- DY_FINANCE_LOADER_START -->
<div aria-label='Daily Yield page transition' aria-live='polite' class='dy-load-screen' data-active='true' id='dyPageLoader' role='status'>
 <div class='dy-load-card'>
  <span class='dy-load-kicker'>Daily Yield</span>
  <span aria-hidden='true' class='dy-load-mark'><i class='dy-load-coin'/></span>
  <svg aria-hidden='true' class='dy-load-chart' viewBox='0 0 210 58'><path class='dy-axis' d='M4 50H206M4 32H206M4 14H206'/><path class='dy-line' d='M7 47 39 38 67 42 98 26 126 31 157 13 201 5'/><circle class='dy-dot' cx='201' cy='5' r='4'/></svg>
  <p class='dy-load-title'>Market momentum,<br/>beautifully measured.</p>
  <p class='dy-load-copy' id='dyLoadCopy'>Preparing your finance desk</p>
  <span aria-hidden='true' class='dy-load-track'><span/></span>
 </div>
</div>
<noscript><style>#dyPageLoader{display:none!important}</style></noscript>
<script>//<![CDATA[
window.__dyLoadStart=(window.performance&&performance.now)?performance.now():Date.now();
//]]></script>
<!-- DY_FINANCE_LOADER_END -->"""

COMMENT_LOADER = r"""<!-- DY_LAZY_COMMENT_LOADER_START -->
<script>//<![CDATA[
(function(){var done=false;function load(){if(done)return;done=true;var s=document.createElement('script');s.src='https://www.blogger.com/static/v1/jsbin/3790099508-comment_from_post_iframe.js';s.async=true;s.onload=function(){if(typeof BLOG_CMT_createIframe==='function')BLOG_CMT_createIframe('https://www.blogger.com/rpc_relay.html');};document.head.appendChild(s);}if('requestIdleCallback' in window)requestIdleCallback(load,{timeout:1800});else window.setTimeout(load,900);})();
//]]></script>
<!-- DY_LAZY_COMMENT_LOADER_END -->"""

BREADCRUMB = r"""<!-- DY_BREADCRUMB_START -->
<b:if cond='data:view.isSingleItem'>
<nav aria-label='Breadcrumb' class='dy-breadcrumb'><a expr:href='data:blog.homepageUrl'>Home</a><span aria-hidden='true'>&#8250;</span><span aria-current='page'><data:blog.pageName/></span></nav>
</b:if>
<!-- DY_BREADCRUMB_END -->"""

FAB = r"""<!-- DY_ENHANCED_FABS_START -->
<a aria-label='Contact Daily Yield' class='fab' data-tip='Contact' href='https://dailyyield.blogspot.com/p/contact-us_01883938366.html' title='Contact'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M4 5h16v12H8l-4 4Z'/><path d='M7 9h10M7 13h7'/></svg></a>
<!-- DY_ENHANCED_FABS_END -->"""

FAQ = r"""<!-- DY_VISIBLE_FAQ_START -->
<b:if cond='data:view.isHomepage'>
<section aria-labelledby='dyFaqTitle' class='dy-site-faq' id='dy-site-faq'><h2 id='dyFaqTitle'>Daily Yield, clearly answered</h2>
<details><summary>What does Daily Yield publish?</summary><p>Daily Yield publishes sourced personal-finance articles, market explainers, calculators and clearly timed News editions.</p></details>
<details><summary>Is Daily Yield personal financial advice?</summary><p>No. Daily Yield provides educational information and arithmetic tools. Consider your circumstances and use an appropriately qualified adviser when needed.</p></details>
<details><summary>How can I report a correction?</summary><p>Use the <a href='https://dailyyield.blogspot.com/p/contact-us_01883938366.html'>Contact desk</a> or email <a href='mailto:dailyyield.official@gmail.com'>dailyyield.official@gmail.com</a> with the page URL and correction details.</p></details></section>
</b:if>
<!-- DY_VISIBLE_FAQ_END -->"""

PRIVACY = r"""<!-- DY_PRIVACY_CHOICES_START -->
<section aria-labelledby='dyPrivacyTitle' aria-live='polite' class='dy-privacy' id='dyPrivacyPanel' role='dialog'><span class='dy-privacy-kicker'>Reader measurement choice</span><h2 id='dyPrivacyTitle'>Help Daily Yield understand what readers value</h2><p>Essential storage keeps your preferences. If you allow optional analytics, Google Analytics records visits and engagement so Daily Yield can improve its articles, News desks and tools. The complete site works either way, and you can change this choice in the footer.</p><div class='dy-privacy-actions'><button class='dy-primary' data-dy-consent='analytics' type='button'>Allow optional analytics</button><button data-dy-consent='essential' type='button'>Continue with essential only</button><a href='https://dailyyield.blogspot.com/p/privacy-policy.html'>Read Privacy Policy</a></div></section>
<!-- DY_PRIVACY_CHOICES_END -->"""

JS = r"""<!-- DY_SITE_ENHANCEMENTS_JS_START -->
<script>//<![CDATA[
(function(){'use strict';var D=document,H=D.documentElement,L=D.getElementById('dyPageLoader'),LC=D.getElementById('dyLoadCopy'),navTimer=0;
function safeGet(k){try{return localStorage.getItem(k)||'';}catch(e){return '';}}
function safeSet(k,v){try{localStorage.setItem(k,v);}catch(e){}}
try{localStorage.removeItem('dy-theme');}catch(e){}H.removeAttribute('data-dy-theme');var themeMeta=D.querySelector('meta[name="theme-color"]');if(themeMeta)themeMeta.content='#F8F0E3';
function showLoad(copy){if(!L)return;if(LC&&copy)LC.textContent=copy;L.removeAttribute('aria-hidden');L.setAttribute('data-active','true');H.setAttribute('data-dy-transitioning','true');}
function hideLoad(){if(!L)return;var start=window.__dyLoadStart||0,clock=(window.performance&&performance.now)?performance.now():Date.now(),wait=Math.max(0,260-(clock-start));setTimeout(function(){L.removeAttribute('data-active');L.setAttribute('aria-hidden','true');H.removeAttribute('data-dy-transitioning');if(window.performance&&performance.now){H.setAttribute('data-dy-interactive-ms',String(Math.round(performance.now())));}},wait);}
function ready(){hideLoad();}if(D.readyState==='loading')D.addEventListener('DOMContentLoaded',ready,{once:true});else ready();window.addEventListener('pageshow',ready);setTimeout(ready,1800);
D.addEventListener('click',function(e){if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;var a=e.target.closest?e.target.closest('a[href]'):null;if(!a||a.hasAttribute('download')||a.target==='_blank')return;var raw=a.getAttribute('href')||'';if(!raw||raw.charAt(0)==='#'||/^(?:mailto:|tel:|javascript:)/i.test(raw))return;var u;try{u=new URL(a.href,location.href);}catch(err){return;}if(!/^dailyyield\.blogspot\./i.test(u.hostname)||u.protocol!=='https:')return;if(u.href===location.href)return;e.preventDefault();var copy=u.pathname==='/'?'Returning to Daily Yield':u.pathname.indexOf('/p/')===0?'Opening the finance desk':'Loading the next analysis';showLoad(copy);clearTimeout(navTimer);navTimer=setTimeout(function(){location.assign(u.href);},70);setTimeout(hideLoad,10000);},true);
window.addEventListener('beforeunload',function(){showLoad('Securing your next view');});
window.addEventListener('load',function(){if(!window.performance)return;var n=performance.getEntriesByType&&performance.getEntriesByType('navigation')[0],ms=n?Math.round(n.loadEventEnd||performance.now()):Math.round(performance.now());H.setAttribute('data-dy-complete-ms',String(ms));H.setAttribute('data-dy-two-second-budget',ms<=2000?'met':'miss');});
var panel=D.getElementById('dyPrivacyPanel'),manage=D.getElementById('dyPrivacyManage');
function consentLabel(mode){return mode==='analytics'?'Privacy choices · Analytics allowed':mode==='essential'?'Privacy choices · Essential only':'Privacy choices';}function setConsentLabel(mode){if(manage){manage.textContent=consentLabel(mode);manage.setAttribute('data-consent',mode||'unset');}}function consent(mode){safeSet('dy-consent',mode);if(panel)panel.classList.remove('dy-open');if(manage)manage.setAttribute('aria-expanded','false');setConsentLabel(mode);window.dataLayer=window.dataLayer||[];window.dataLayer.push({event:'dy_consent_update',analytics_storage:mode==='analytics'?'granted':'denied'});if(typeof window.gtag==='function')window.gtag('consent','update',{analytics_storage:mode==='analytics'?'granted':'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});}
if(panel&&manage){var hero=D.querySelector('.fk-home .kv-hero');if(hero)hero.insertAdjacentElement('afterend',panel);var savedConsent=safeGet('dy-consent');setConsentLabel(savedConsent);if(savedConsent==='analytics'||savedConsent==='essential')consent(savedConsent);else panel.classList.add('dy-open');manage.addEventListener('click',function(){var open=!panel.classList.contains('dy-open');panel.classList.toggle('dy-open',open);manage.setAttribute('aria-expanded',open?'true':'false');if(open){if(hero)panel.scrollIntoView({behavior:'smooth',block:'center'});setTimeout(function(){panel.querySelector('button').focus();},hero?500:0);}});panel.querySelectorAll('[data-dy-consent]').forEach(function(b){b.addEventListener('click',function(){consent(b.getAttribute('data-dy-consent'));});});}
try{var q=new URLSearchParams(location.search),a={};['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(function(k){var v=q.get(k);if(v)a[k]=v.slice(0,160);});if(Object.keys(a).length){sessionStorage.setItem('dy-attribution',JSON.stringify(a));H.setAttribute('data-dy-attributed','true');}}catch(e){}
D.querySelectorAll('input[type="password"]').forEach(function(i){if(i.parentNode.classList.contains('dy-password-wrap'))return;var w=D.createElement('span');w.className='dy-password-wrap';i.parentNode.insertBefore(w,i);w.appendChild(i);var b=D.createElement('button');b.type='button';b.className='dy-password-toggle';b.textContent='Show';b.setAttribute('aria-label','Show password');b.addEventListener('click',function(){var show=i.type==='password';i.type=show?'text':'password';b.textContent=show?'Hide':'Show';b.setAttribute('aria-label',(show?'Hide':'Show')+' password');});w.appendChild(b);});
D.querySelectorAll('form').forEach(function(f){var s=f.querySelector('.dy-form-status');if(!s){s=D.createElement('p');s.className='dy-form-status';s.setAttribute('role','status');f.appendChild(s);}f.addEventListener('invalid',function(e){s.textContent='Please check the highlighted field and try again.';s.setAttribute('data-state','error');},true);f.addEventListener('submit',function(){if(f.checkValidity()){s.textContent=f.classList.contains('dy-sub-form')?'Opening the secure confirmation step in a new tab.':'Submitted. Please follow the next on-screen step.';s.setAttribute('data-state','success');}});});
D.querySelectorAll('img:not([alt]),img[alt=""]').forEach(function(img){var box=img.closest('a,article,figure'),label=box?(box.getAttribute('aria-label')||box.textContent||''):'';label=label.replace(/\s+/g,' ').trim().slice(0,160);img.alt=label||'Daily Yield editorial image';});
D.querySelectorAll('.post-body img,.page-body img').forEach(function(img,n){if(!img.hasAttribute('decoding'))img.setAttribute('decoding','async');if(n>0&&!img.hasAttribute('loading'))img.setAttribute('loading','lazy');if(n===0&&!img.hasAttribute('fetchpriority'))img.setAttribute('fetchpriority','high');});
var contentH1=D.querySelector('.item-post .post-body h1'),templateTitle=D.querySelector('.item-post .post-header .post-title-container');if(contentH1&&templateTitle)templateTitle.style.display='none';
function schemaModified(){var found='';D.querySelectorAll('script[type="application/ld+json"]').forEach(function(s){try{var data=JSON.parse(s.textContent),walk=function(x){if(!x||found)return;if(Array.isArray(x)){x.forEach(walk);return;}if(typeof x==='object'){if(x.dateModified)found=String(x.dateModified);Object.keys(x).forEach(function(k){walk(x[k]);});}};walk(data);}catch(e){}});return found;}
var modified=schemaModified(),titleBox=D.querySelector('.item-post .post-title-container,.page-body h1');if(modified&&titleBox){var dt=new Date(modified);if(!isNaN(dt.getTime())){var badge=D.createElement('p');badge.className='dy-updated';badge.textContent='Last reviewed '+dt.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});if(titleBox.parentNode)titleBox.parentNode.insertBefore(badge,titleBox.nextSibling);}}
var bc=D.querySelector('.dy-breadcrumb');if(bc){var parts=[{"@type":"ListItem","position":1,"name":"Home","item":"https://dailyyield.blogspot.com/"},{"@type":"ListItem","position":2,"name":D.title.split(/[|\u2014]/)[0].trim(),"item":location.href.split('#')[0]}],sc=D.createElement('script');sc.type='application/ld+json';sc.text=JSON.stringify({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":parts});D.head.appendChild(sc);}
})();
//]]></script>
<!-- DY_SITE_ENHANCEMENTS_JS_END -->"""


def replace_marked(text: str, start: str, end: str, package: str) -> str:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    if re.search(pattern, text, flags=re.S):
        return re.sub(pattern, lambda _: package, text, count=1, flags=re.S)
    return text


def inject(text: str) -> str:
    image_repairs = {
        "<img class='author-avatar' expr:src='data:comment.authorAvatarSrc' height='35' width='35'/>": "<img alt='Comment author profile photo' class='author-avatar' expr:src='data:comment.authorAvatarSrc' height='35' width='35'/>",
        "<img src='https://resources.blogblog.com/img/icon_delete13.gif'/>": "<img alt='Delete comment' src='https://resources.blogblog.com/img/icon_delete13.gif'/>",
        "<img class='author-image' expr:src='data:post.author.authorPhoto.url' width='50px'/>": "<img alt='Kushal K. Daga, Daily Yield author' class='author-image' expr:src='data:post.author.authorPhoto.url' width='50px'/>",
        "<img alt=\"\" loading=\"lazy\" src=\"'+esc(p.thumb)+'\" onerror=\"this.remove()\"/>": "<img alt=\"'+esc(p.title)+'\" loading=\"lazy\" src=\"'+esc(p.thumb)+'\" onerror=\"this.remove()\"/>",
        "im.alt='';im.loading='lazy'": "im.alt=it.title||'Daily Yield article preview';im.loading='lazy'",
        "<img loading=\"lazy\" alt=\"\" src=\"'+esc(it.img)+'\"/>": "<img loading=\"lazy\" alt=\"'+esc(it.title)+'\" src=\"'+esc(it.img)+'\"/>",
    }
    for old, new in image_repairs.items():
        text = text.replace(old, new, 1)
    text = text.replace("expr:dir='data:blog.languageDirection' xmlns='http://www.w3.org/1999/xhtml'", "expr:dir='data:blog.languageDirection' lang='en' xmlns='http://www.w3.org/1999/xhtml'", 1)
    old_title = "<title><data:blog.pageTitle/></title>"
    title_package = """<b:if cond='data:view.isHomepage'>
<title>Daily Yield | Finance, Markets, News &amp; Calculators</title>
<b:elseif cond='data:view.isSingleItem'/>
<title><data:blog.pageName/></title>
<b:else/>
<title><data:blog.pageTitle/></title>
</b:if>"""
    if 'Daily Yield | Finance, Markets, News &amp; Calculators' not in text:
        text = text.replace(old_title, title_package, 1)
    text = text.replace("<b:if cond='data:blog.metaDescription'>\n<meta expr:content='data:blog.metaDescription' name='description'/>\n</b:if>\n", "", 1)
    if "Bing-safe server-rendered fallback" not in text:
        fallback = """<b:include data='blog' name='all-head-content'/>
<!-- Bing-safe server-rendered fallback. Blogger's all-head-content remains the
     sole standard-description source when an editor-provided value exists. -->
<b:if cond='!data:blog.metaDescription'>
 <b:if cond='data:view.isHomepage'>
  <meta content='Daily Yield explains finance, markets and money with sourced news, practical calculators, clear analysis and educational tools for global readers.' name='description'/>
 <b:elseif cond='data:view.isSingleItem'/>
  <meta expr:content='data:blog.pageName + &quot; — Sourced financial context, practical explanations and clear takeaways from Daily Yield.&quot;' name='description'/>
 <b:else/>
  <meta content='Explore Daily Yield finance education, market coverage, practical money guides, calculators and sourced financial analysis.' name='description'/>
 </b:if>
</b:if>"""
        text = text.replace("<b:include data='blog' name='all-head-content'/>", fallback, 1)
    viewport = "<meta content='width=device-width, initial-scale=1, shrink-to-fit=no' name='viewport'/>"
    if "http-equiv='Content-Language'" not in text:
        text = text.replace(viewport, viewport + "\n<meta content='en' http-equiv='Content-Language'/>", 1)
    text = text.replace("<h1 class='post-title entry-title'><data:post.title/></h1>", "<div aria-level='2' class='post-title entry-title' role='heading'><data:post.title/></div>", 1)
    text = text.replace('.item-post h1.post-title{', '.item-post .post-title{').replace('.item-post h1.post-title::after{', '.item-post .post-title::after{').replace('.item-post h1.post-title,.item-post h1.post-title::after{', '.item-post .post-title,.item-post .post-title::after{')
    blocking_comment = re.compile(r"<script src='https://www\.blogger\.com/static/v1/jsbin/3790099508-comment_from_post_iframe\.js' type='text/javascript'/>\s*<script type='text/javascript'>BLOG_CMT_createIframe\(&#39;https://www\.blogger\.com/rpc_relay\.html&#39;\);</script>")
    if "DY_LAZY_COMMENT_LOADER_START" in text:
        text = replace_marked(text, "<!-- DY_LAZY_COMMENT_LOADER_START -->", "<!-- DY_LAZY_COMMENT_LOADER_END -->", COMMENT_LOADER)
    else:
        text = blocking_comment.sub(lambda _: COMMENT_LOADER, text, count=1)
    # Remove render-blocking web-font connections. Existing font stacks retain
    # the same editorial character through local system/Georgia fallbacks.
    text = re.sub(r"\n<link[^>]+href='https://fonts\.googleapis\.com[^']*'[^>]*/>", "", text)
    text = re.sub(r"\n<link[^>]+href='https://fonts\.gstatic\.com[^']*'[^>]*/>", "", text)
    # Three duplicate embedded PNG favicon variants added ~47 KB ahead of body
    # parsing. The compact inline SVG favicon remains authoritative.
    text = re.sub(r"\n\s*<link href='data:image/png;base64,[^']+'[^>]*/>", "", text)
    text = text.replace(';animation:pageIn .8s ease}', '}').replace('@keyframes pageIn{from{opacity:0}to{opacity:1}}\n', '')
    if "DY_SITE_ENHANCEMENTS_HEAD_START" in text:
        text = replace_marked(text, "<!-- DY_SITE_ENHANCEMENTS_HEAD_START -->", "<!-- DY_SITE_ENHANCEMENTS_HEAD_END -->", HEAD)
    else:
        text = text.replace("</head>", HEAD + "\n</head>", 1)
    if "DY_SITE_ENHANCEMENTS_CSS_START" in text:
        text = replace_marked(text, "/* DY_SITE_ENHANCEMENTS_CSS_START */", "/* DY_SITE_ENHANCEMENTS_CSS_END */", CSS)
    else:
        text = text.replace("]]></b:skin>", CSS + "\n]]></b:skin>", 1)
    if "DY_FINANCE_LOADER_START" in text:
        text = replace_marked(text, "<!-- DY_FINANCE_LOADER_START -->", "<!-- DY_FINANCE_LOADER_END -->", LOADER)
    else:
        text = re.sub(r"(<body\b[^>]*>)", lambda m: m.group(1) + "\n" + LOADER, text, count=1)
    if "DY_BREADCRUMB_START" not in text:
        anchor = " <!-- ================= Blog header : title and description ================= -->"
        text = text.replace(anchor, BREADCRUMB + "\n\n" + anchor, 1)
    if "DY_ENHANCED_FABS_START" not in text:
        anchor = " <button aria-label='Share this page' class='fab'"
        text = text.replace(anchor, " " + FAB + "\n" + anchor, 1)
    if "DY_VISIBLE_FAQ_START" not in text:
        anchor = " <!-- ================= Footer : attribution ================= -->"
        text = text.replace(anchor, FAQ + "\n\n" + anchor, 1)
    if "id='dyPrivacyManage'" not in text:
        footer_anchor = "<li><a href='https://dailyyield.blogspot.com/p/terms-and-conditions.html'>Terms &amp; Conditions</a></li>"
        footer_control = "<li><button aria-controls='dyPrivacyPanel' aria-expanded='false' class='dy-privacy-manage' id='dyPrivacyManage' type='button'>Privacy choices</button></li>"
        at = text.rfind(footer_anchor)
        if at < 0:
            raise RuntimeError('footer policy anchor not found')
        text = text[:at] + footer_control + text[at:]
    if "DY_PRIVACY_CHOICES_START" not in text:
        text = text.replace("</body>", PRIVACY + "\n</body>", 1)
    if "DY_SITE_ENHANCEMENTS_JS_START" in text:
        text = replace_marked(text, "<!-- DY_SITE_ENHANCEMENTS_JS_START -->", "<!-- DY_SITE_ENHANCEMENTS_JS_END -->", JS)
    else:
        text = text.replace("</body>", JS + "\n</body>", 1)
    return text


def main():
    for path in THEMES:
        original = path.read_text(encoding="utf-8")
        updated = inject(original)
        path.write_text(updated, encoding="utf-8")
        print(path, "updated" if updated != original else "already current")


if __name__ == "__main__":
    main()
