#!/usr/bin/env python3
"""Idempotently add Daily Yield's accessibility, privacy and SEO experience layer."""
from pathlib import Path
import json
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
<!-- Connection setup only: no document or asset is requested. -->
<link crossorigin='anonymous' href='https://blogger.googleusercontent.com' rel='preconnect'/>
<link crossorigin='anonymous' href='https://lh3.googleusercontent.com' rel='preconnect'/>
<!-- Optional analytics stays denied until the reader explicitly allows it. -->
<script>//<![CDATA[
window.dataLayer=window.dataLayer||[];
window.gtag=window.gtag||function(){window.dataLayer.push(arguments);};
window.gtag('consent','default',{analytics_storage:'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',wait_for_update:500});
/* Feed-only session cache. It cannot request Page, Post, label or archive documents. */
(function(){var memory={};function safe(url){try{var u=new URL(url,location.href);return u.origin===location.origin&&/^\/feeds\//.test(u.pathname);}catch(e){return false;}}function get(url,ttl){if(!safe(url))return Promise.reject(Error('document requests prohibited'));var key='dy-feed-cache:'+url,now=Date.now(),saved=null;try{saved=JSON.parse(sessionStorage.getItem(key)||'null');}catch(e){}if(saved&&now-saved.at<ttl)return Promise.resolve(saved.data);if(memory[url])return memory[url];memory[url]=fetch(url,{credentials:'same-origin'}).then(function(r){if(!r.ok)throw Error('feed');return r.json();}).then(function(data){try{sessionStorage.setItem(key,JSON.stringify({at:Date.now(),data:data}));}catch(e){}return data;}).then(function(data){delete memory[url];return data;},function(err){delete memory[url];throw err;});return memory[url];}var inlineIndex=__DY_EXACT_IMAGE_INDEX__;function asset(){return Promise.resolve(inlineIndex)}window.DYFeedCache={get:get,asset:asset,isSafeFeed:safe};if(/^\/search\/label\//.test(location.pathname))document.documentElement.classList.add('dy-label-page');})();
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
/* Full-screen selected Option 1: a dense, dependency-free finance sticker wall
   with one lightweight centre-ring animation and one composited field drift. */
.dy-load-screen{position:fixed;inset:0;z-index:2147483000;display:grid;place-items:center;overflow:hidden;isolation:isolate;contain:strict;background:radial-gradient(circle at 50% 42%,#fffaf1 0,#f8ecda 58%,#efd8bd 100%);color:#241610;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .24s ease-out,visibility 0s linear .24s;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.dy-load-screen[data-active='true']{opacity:1;visibility:visible;pointer-events:auto;transition:opacity .22s ease-out,visibility 0s;animation:dyLoaderFadeIn .24s ease-out both}.dy-symbol-field{position:absolute;z-index:0;inset:-6%;display:grid;grid-template-columns:repeat(12,minmax(58px,1fr));grid-template-rows:repeat(9,minmax(58px,1fr));align-items:center;justify-items:center;gap:5px;transform:rotate(-3deg) scale(1.07);animation:dyFieldDrift 5s ease-in-out infinite;will-change:transform}.dy-symbol-field span{display:grid;place-items:center;min-width:42px;min-height:42px;padding:5px;color:#9c4522;font:800 clamp(20px,3vw,42px)/1 Georgia,"Times New Roman",serif;opacity:.18}.dy-symbol-field span:nth-child(3n){color:#315d4b;transform:rotate(8deg)}.dy-symbol-field span:nth-child(4n){color:#bc7d22;transform:rotate(-9deg)}.dy-symbol-field span:nth-child(5n){border:1px solid currentColor;border-radius:12px;background:rgba(255,253,248,.42);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;font-size:clamp(10px,1.5vw,17px);letter-spacing:.04em}.dy-symbol-field span:nth-child(7n){border-radius:50%;outline:1px solid currentColor;outline-offset:5px}
.dy-sticker-field{position:absolute;z-index:2;inset:0;pointer-events:none}.dy-sticker{--s:1;position:absolute;display:flex;align-items:center;justify-content:center;gap:7px;padding:9px 13px;border:2px solid currentColor;border-radius:15px;background:#fffdf8;color:#9c4522;box-shadow:4px 6px 0 rgba(36,22,16,.13);font:800 clamp(10px,1.25vw,15px)/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.03em;white-space:nowrap;transform:rotate(var(--r,0deg)) scale(var(--s));transform-origin:center}.dy-sticker:nth-child(3n){color:#315d4b;background:#f3f5e9}.dy-sticker:nth-child(4n){color:#80571d;background:#fff1c9}.dy-sticker:nth-child(5n){border-radius:999px}.dy-load-card{position:relative;z-index:5;width:min(78vw,310px);aspect-ratio:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border:2px solid #eadcc8;border-radius:50%;background:rgba(255,253,248,.97);box-shadow:0 28px 90px -40px rgba(36,22,16,.65)}.dy-load-kicker{display:block;margin-bottom:14px;color:#241610;font:800 10px/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.32em;text-transform:uppercase}.dy-load-ring{position:relative;width:86px;height:86px;border-radius:50%}.dy-load-ring::before,.dy-load-ring::after{content:"";position:absolute;border-radius:50%}.dy-load-ring::before{inset:0;border:6px solid rgba(188,91,51,.16);border-top-color:#bc5b33;border-right-color:#f0b180;animation:dyRing 1s linear infinite}.dy-load-ring::after{inset:19px;background:#bc5b33;box-shadow:inset 0 0 0 6px #fff8ee}.dy-load-ring b{position:absolute;inset:0;z-index:2;display:grid;place-items:center;color:#fff8ee;font:700 18px/1 Georgia,"Times New Roman",serif}.dy-load-title{margin:17px 20px 8px;color:#241610;font:700 clamp(27px,7vw,38px)/1.05 Georgia,"Times New Roman",serif;letter-spacing:-.035em}.dy-load-copy{min-height:1.5em;margin:0 18px;color:#7a6a58;font:700 11px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.07em}
@keyframes dyLoaderFadeIn{from{opacity:0}to{opacity:1}}@keyframes dyRing{to{transform:rotate(360deg)}}@keyframes dyFieldDrift{0%,100%{transform:rotate(-3deg) scale(1.07) translateY(0)}50%{transform:rotate(-2deg) scale(1.07) translateY(-8px)}}
@media(max-width:640px){.dy-symbol-field{inset:-3%;grid-template-columns:repeat(7,1fr);grid-template-rows:repeat(16,1fr);gap:0;transform:rotate(-2deg) scale(1.03);animation-name:dyFieldDriftMobile}.dy-symbol-field span{min-width:28px;min-height:28px;font-size:24px;opacity:.21}.dy-sticker{--s:.62;padding:8px 10px}.dy-load-card{width:235px}.dy-load-title{font-size:28px;margin-top:13px}.dy-load-ring{width:70px;height:70px}.dy-load-ring::after{inset:15px}}
@keyframes dyFieldDriftMobile{0%,100%{transform:rotate(-2deg) scale(1.03) translateY(0)}50%{transform:rotate(-1deg) scale(1.03) translateY(-6px)}}
/* Compact high-density layout: more dated content remains visible per screen. */
html,body{max-width:100%;overflow-x:clip}.fk-home main,.fk-home #enhancedHome,.kd-sec,.kd-row,.kd-mqwrap{max-width:100%;min-width:0}.kd-row,.kd-mqwrap{overflow-x:auto;overscroll-behavior-inline:contain}.fk-home #Blog1 .blog-posts,.fk-home #blog-pager{display:none!important}
.fk-rest .blog-posts{grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.fk-rest .blog-posts .post{padding:18px}.fk-rest .blog-posts h3.post-title{font-size:21px}.fk-rest .blog-posts .post-snippet{font-size:13px;line-height:1.6;-webkit-line-clamp:3}.blog-posts .snippet-thumbnail-container{aspect-ratio:16/9}.dy-label-page #blog-pager{display:none!important}.dy-label-page .blog-posts{width:min(1180px,100%);margin-inline:auto;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:22px!important;padding:12px clamp(16px,4vw,46px) 28px!important}.dy-label-page .blog-posts .post{display:flex!important;min-width:0!important;min-height:430px;padding:0!important;overflow:hidden;border:1px solid var(--line);border-radius:18px;background:var(--surface);box-shadow:0 14px 38px -30px rgba(36,22,16,.55)}.dy-label-card{flex-direction:column}.dy-label-image{display:block;width:100%;aspect-ratio:16/9;overflow:hidden;background:linear-gradient(135deg,#ead8bc,#f8f0e3);color:var(--accent-dark)}.dy-label-image img{display:block;width:100%;height:100%;margin:0!important;padding:0!important;object-fit:cover;object-position:center}.dy-label-image span{display:grid;width:100%;height:100%;place-items:center;font:700 38px/1 var(--font-display)}.dy-label-card .post-title-container,.dy-label-card .post-header,.dy-label-card .post-body-container{padding-inline:20px}.dy-label-card .post-title-container{padding-top:19px}.dy-label-card .post-title{margin:0!important;font-size:22px!important;line-height:1.2!important}.dy-label-card .post-header{margin-top:12px}.dy-label-card .post-labels{display:flex;flex-wrap:wrap;gap:6px}.dy-label-card .post-labels a{margin:0!important}.dy-label-card .post-body-container{display:flex;flex:1;flex-direction:column;padding-bottom:20px}.dy-label-card .post-snippet{display:-webkit-box!important;margin:13px 0 17px!important;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:3}.dy-label-card .jump-link{margin-top:auto}.dy-label-status{grid-column:1/-1;min-height:86px;display:grid;place-items:center;padding:22px;color:var(--muted);font:800 10px/1.5 var(--font-body);letter-spacing:.13em;text-align:center;text-transform:uppercase}.dy-label-status:before{content:"";width:28px;height:28px;margin-bottom:9px;border:3px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:dyRing .85s linear infinite}.dy-label-status[data-finished='true']:before,.dy-label-status[data-error='true']:before{display:none}.dy-label-status[data-finished='true']{min-height:52px;opacity:.74}
/* Five tool benches share one compact row as one navigational unit. */
#kd-tools{padding-top:34px!important;padding-bottom:34px!important}#kd-tools .kd-head{margin-bottom:16px!important}#kd-tools .kd-digest{grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:8px!important}#kd-tools .kd-dg{min-width:0;padding:12px 10px!important;border-radius:11px!important}#kd-tools .kd-dg b{font-size:14px!important}#kd-tools .kd-dg span{font-size:10px!important;line-height:1.4!important}#kd-tools .kd-dg i{font-size:8px!important}
/* Preserve the established brand header, moving rails and compact contact desk. */
.topbar-inner{height:clamp(92px,10vw,112px)!important}.topbar-title{gap:2px!important;padding:5px 0 13px!important;max-width:calc(100vw - 120px)}.topbar-title .tb-a{font:800 clamp(32px,4.7vw,50px)/.94 var(--font-display)!important;letter-spacing:.095em!important;white-space:nowrap}.topbar-title .tb-line{min-height:15px!important}.topbar-title .tb-b{font:500 clamp(10px,1.25vw,13px)/1.1 var(--font-body)!important;letter-spacing:.08em!important;color:var(--accent-dark)!important}.topbar-title .tb-caret{height:11px!important}.topbar-title .tb-squig{bottom:-8px!important;width:58px!important}
.kd-sec{width:100%;min-width:0;overflow:hidden}#kd-articles .kd-row{cursor:grab;scroll-snap-type:none;overscroll-behavior-inline:contain}#kd-articles .kd-row.kd-grabbing{cursor:grabbing;user-select:none}#kd-articles .kd-row[data-kd-auto='1']{scrollbar-width:none}#kd-articles .kd-row[data-kd-auto='1']::-webkit-scrollbar{display:none}
.kd-engage{position:relative;overflow:hidden!important;padding:clamp(30px,5vw,54px)!important;background:radial-gradient(480px 230px at 0 0,rgba(188,91,51,.12),transparent 65%),linear-gradient(145deg,#fffaf0,#f4e1c4)!important}.kd-engage::before{content:"?";position:absolute;right:-.04em;bottom:-.36em;color:rgba(156,69,34,.055);font:700 clamp(170px,27vw,330px)/1 var(--font-display);pointer-events:none}.kd-engage h2{font-size:clamp(32px,4.8vw,54px)!important;letter-spacing:-.035em}.kd-engage>p{max-width:760px!important;font-size:clamp(13px,1.5vw,16px)!important}.kd-eg-row{position:relative;display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px!important;max-width:760px;margin:25px auto 12px!important}.kd-eg{min-height:96px;padding:18px!important;border-radius:18px!important;display:flex!important;align-items:center;gap:15px;text-align:left;background:rgba(255,253,248,.92)!important;box-shadow:0 13px 32px -28px rgba(36,22,16,.75);font:inherit!important}.kd-eg-icon{width:52px;height:52px;flex:none;border-radius:15px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-dark)}.kd-eg-icon svg{display:block!important;width:26px!important;height:26px!important;stroke:currentColor!important;fill:none!important;stroke-width:1.65;stroke-linecap:round;stroke-linejoin:round}.kd-eg-copy{min-width:0}.kd-eg-copy strong{display:block;color:var(--ink);font:700 17px/1.2 var(--font-display)}.kd-eg-copy small{display:block;margin-top:6px;color:var(--muted);font:500 10px/1.45 var(--font-body);overflow-wrap:anywhere}.kd-eg-arrow{margin-left:auto;color:var(--accent-dark);font-size:22px;transition:transform .25s}.kd-eg:hover .kd-eg-arrow{transform:translateX(4px)}
@media(max-width:560px){.topbar-inner{height:88px!important}.topbar-title{max-width:calc(100vw - 104px)}.topbar-title .tb-a{font-size:27px!important;letter-spacing:.075em!important}.topbar-title .tb-b{font-size:10px!important}.kd-eg-row{grid-template-columns:1fr}.kd-eg{min-height:84px;padding:15px!important}.kd-eg-icon{width:46px;height:46px}.kd-engage{padding:30px 16px!important}}
@media(max-device-width:760px){.topbar-inner{height:88px!important}.topbar-title .tb-a{font-size:27px!important}.topbar-title .tb-b{font-size:10px!important}.kd-eg-row{grid-template-columns:1fr!important}}
@media(max-width:760px){.fk-rest .blog-posts,.fk-home .blog-posts{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:9px!important;padding:0 9px!important}.blog-posts .post{padding:11px!important}.blog-posts h3.post-title{font-size:15px!important}.blog-posts .post-header-line-1{font-size:8px!important}.blog-posts .post-labels a{padding:4px 7px!important;font-size:7px!important}.blog-posts .post-snippet{display:none!important}.dy-label-page .blog-posts{grid-template-columns:1fr!important;gap:16px!important;padding-inline:12px!important}.dy-label-page .blog-posts .post{min-height:440px!important}.dy-label-page .blog-posts .post-snippet{display:-webkit-box!important}.dy-label-card .post-title-container,.dy-label-card .post-header,.dy-label-card .post-body-container{padding-inline:18px}#kd-tools{padding:24px 8px!important}#kd-tools .kd-digest{grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:4px!important}#kd-tools .kd-dg{padding:8px 4px!important;text-align:center}#kd-tools .kd-dg b{font-size:9px!important;line-height:1.15!important;overflow-wrap:anywhere}#kd-tools .kd-dg span,#kd-tools .kd-dg i{display:none!important}}
/* Keep below-fold modules out of initial layout/paint work where supported. */
.site-footer,.dy-site-faq,#sidebar_feed,.item-post .dy2>section,.item-post .dy2>figure{content-visibility:auto;contain-intrinsic-size:1px 720px}.dya-desk,.dy-auth-desk{content-visibility:auto;contain-intrinsic-size:1px 560px}
.item-post div.post-title{font:600 clamp(27px,2.9vw,40px)/1.14 var(--font-display);letter-spacing:-.02em;margin:0 0 18px;color:var(--ink);overflow-wrap:break-word}.dy-breadcrumb{display:flex;align-items:center;gap:8px;min-height:42px;padding:8px clamp(20px,4.5vw,48px);border-bottom:1px solid var(--line);color:var(--muted);font:600 11px/1.4 var(--font-body);letter-spacing:.06em}
.dy-breadcrumb a{color:var(--accent-dark);text-decoration:underline;text-underline-offset:3px}.dy-breadcrumb span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dy-site-faq{padding:clamp(40px,6vw,80px) clamp(20px,4.5vw,48px);background:var(--surface);border-top:1px solid var(--line)}
.dy-site-faq h2{font-size:clamp(28px,4vw,48px);margin-bottom:20px}.dy-site-faq details{max-width:900px;border-top:1px solid var(--line);padding:15px 0}.dy-site-faq details:last-child{border-bottom:1px solid var(--line)}
.dy-site-faq summary{cursor:pointer;font-weight:700;list-style-position:inside}.dy-site-faq p{margin:10px 0 0;color:var(--muted)}
.dy-updated{display:inline-flex;margin:10px 0 4px;padding:6px 10px;border-radius:999px;background:var(--accent-soft);color:var(--accent-dark);font:700 10px/1.2 var(--font-body);letter-spacing:.06em;text-transform:uppercase}.dy-form-status{min-height:1.5em;margin:10px 0 0;font-size:13px;font-weight:600;color:var(--muted)}.dy-form-status[data-state='error']{color:#a32222}.dy-form-status[data-state='success']{color:#20733a}
.dy-privacy-lock,.dy-privacy-lock body{overflow:hidden!important}.dy-privacy-lock body::after{content:"";position:fixed;z-index:250;inset:0;background:rgba(248,240,227,.20);-webkit-backdrop-filter:blur(15px) saturate(.72);backdrop-filter:blur(15px) saturate(.72);pointer-events:auto}
.dy-privacy{position:fixed;z-index:260;left:50%;top:50%;width:min(620px,calc(100% - 30px));transform:translate(-50%,-50%);padding:clamp(30px,4vw,42px);background:rgba(255,248,239,.94);border:1px solid #d9b985;border-radius:28px;box-shadow:0 38px 120px rgba(56,31,15,.42);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px);display:none;overflow:hidden}.dy-privacy::before{content:"";position:absolute;inset:0;border-radius:inherit;background:linear-gradient(120deg,rgba(255,255,255,.68),transparent 48%);pointer-events:none}.dy-privacy>*{position:relative}
.dy-privacy.dy-open{display:block}.dy-privacy-close{position:absolute;z-index:2;right:16px;top:16px;width:42px;height:42px;display:grid;place-items:center;border:1px solid #dbc6aa;border-radius:50%;background:rgba(255,255,255,.78);color:#4e392b;font:500 25px/1 var(--font-body)}.dy-privacy-kicker{display:block;margin:0 52px 12px 0;color:#98502d;font:800 10px/1.4 var(--font-body);letter-spacing:.19em;text-transform:uppercase}.dy-privacy h2{font:700 clamp(32px,4.4vw,44px)/1.08 var(--font-display);margin:0 50px 14px 0}.dy-privacy p{font-size:15px;line-height:1.68;margin:0;color:#6c594c}.dy-privacy-actions{display:grid;gap:12px;margin-top:24px}.dy-privacy-actions button{display:flex;width:100%;min-height:54px;align-items:center;justify-content:center;padding:14px 18px;border:1px solid #d8c3a7;border-radius:14px;background:rgba(255,255,255,.12);color:#332319;font:800 13px/1.2 var(--font-body)}.dy-privacy-actions .dy-primary{min-height:68px;background:linear-gradient(135deg,#bd5a33,#9a4323);color:#fff;border-color:#9a4323;font-size:15px;box-shadow:0 14px 30px -14px #873718}.dy-privacy-actions button:not(.dy-primary){min-height:34px;padding:8px;background:transparent;border:0;border-radius:0;box-shadow:none;color:#5c493d}.dy-privacy-policy{display:block;margin-top:15px;color:#98502d;font:700 11px/1.4 var(--font-body);text-align:center;text-decoration:underline;text-underline-offset:3px}
.site-footer .ft-page-links .dy-privacy-manage{display:flex;width:100%;align-items:center;justify-content:space-between;gap:14px;min-height:46px;box-sizing:border-box;padding:10px 0;border:0;border-bottom:1px solid #b58e5d26;border-radius:0;background:transparent;color:#e8d7be;font:400 13px/1.6 var(--font-body,Inter,Arial,sans-serif);text-align:left;cursor:pointer}.site-footer .ft-page-links .dy-privacy-manage::after{content:'\2192';font-size:15px;color:#b58c5b;transition:transform .2s}.site-footer .ft-page-links .dy-privacy-manage:hover{color:#fff5e5;border-color:#c79860}.site-footer .ft-page-links .dy-privacy-manage:hover::after{transform:translateX(3px);color:#efbd7b}
.dy-password-wrap{position:relative}.dy-password-toggle{position:absolute;right:8px;top:50%;transform:translateY(-50%);padding:7px;border-radius:6px;font-size:12px;background:var(--surface);border:1px solid var(--line)}
@media print{.dy-privacy,.dy-privacy-manage,.dy-site-faq,.dy-breadcrumb,.dy-form-status{display:none!important}body{background:#fff!important;color:#000!important}.item-post .post-body,.page-body{font-size:11pt!important;line-height:1.5!important;color:#000!important}a[href]::after{content:" (" attr(href) ")";font-size:8pt;overflow-wrap:anywhere}}
@media(max-width:560px){.dy-privacy{width:calc(100% - 18px);padding:28px 20px 24px}.dy-privacy h2{font-size:31px;margin-right:36px}.dy-privacy p{font-size:13px}.dy-privacy-actions .dy-primary{min-height:62px}.dy-privacy-actions button{min-height:50px}.dy-privacy-close{right:10px;top:10px}.dy-breadcrumb{padding-right:58px}}
@media(prefers-reduced-motion:reduce){.dy-load-screen,.dy-load-screen *{animation:none!important;transition:none!important}}
/* DY_SITE_ENHANCEMENTS_CSS_END */"""

LOADER = r"""<!-- DY_FINANCE_LOADER_START -->
<div aria-label='Daily Yield page transition' aria-live='polite' class='dy-load-screen' data-active='true' id='dyPageLoader' role='status'>
 <div aria-hidden='true' class='dy-symbol-field'><span>₹</span><span>↗</span><span>EPS</span><span>24H</span><span>£</span><span>📉</span><span>CASH</span><span>₹</span><span>↗</span><span>EPS</span><span>24H</span><span>£</span><span>🪙</span><span>CASH</span><span>₹</span><span>↗</span><span>EPS</span><span>24H</span><span>¥</span><span>🪙</span><span>CASH</span><span>₹</span><span>↗</span><span>EPS</span><span>+</span><span>¥</span><span>🪙</span><span>CASH</span><span>₹</span><span>↗</span><span>IPO</span><span>+</span><span>¥</span><span>🪙</span><span>CASH</span><span>₹</span><span>↘</span><span>IPO</span><span>+</span><span>¥</span><span>🪙</span><span>CASH</span><span>$</span><span>↘</span><span>IPO</span><span>+</span><span>¥</span><span>🪙</span><span>FUND</span><span>$</span><span>↘</span><span>IPO</span><span>+</span><span>¥</span><span>ROI</span><span>FUND</span><span>$</span><span>↘</span><span>IPO</span><span>+</span><span>₿</span><span>ROI</span><span>FUND</span><span>$</span><span>↘</span><span>IPO</span><span>−</span><span>₿</span><span>ROI</span><span>FUND</span><span>$</span><span>↘</span><span>TAX</span><span>−</span><span>₿</span><span>ROI</span><span>FUND</span><span>$</span><span>📈</span><span>TAX</span><span>−</span><span>₿</span><span>ROI</span><span>FUND</span><span>€</span><span>📈</span><span>TAX</span><span>−</span><span>₿</span><span>ROI</span><span>DIV</span><span>€</span><span>📈</span><span>TAX</span><span>−</span><span>₿</span><span>P/E</span><span>DIV</span><span>€</span><span>📈</span><span>TAX</span><span>−</span><span>%</span><span>P/E</span><span>DIV</span><span>€</span><span>📈</span><span>TAX</span><span>=</span><span>%</span><span>P/E</span><span>DIV</span></div>
 <div aria-hidden='true' class='dy-sticker-field'><span class='dy-sticker' style='left:2%;top:8%;--r:-8deg'>📈 MARKET UP</span><span class='dy-sticker' style='left:22%;top:5%;--r:5deg'>▥ PORTFOLIO</span><span class='dy-sticker' style='left:44%;top:2%;--r:-3deg'>BUY LOW · HOLD LONG</span><span class='dy-sticker' style='right:20%;top:5%;--r:9deg'>₹ RUPEE</span><span class='dy-sticker' style='right:2%;top:9%;--r:-5deg'>💳 CREDIT</span><span class='dy-sticker' style='left:4%;top:24%;--r:5deg'>IPO</span><span class='dy-sticker' style='left:16%;top:27%;--r:-6deg'>$ CASH FLOW</span><span class='dy-sticker' style='right:18%;top:25%;--r:7deg'>P/E 18.4</span><span class='dy-sticker' style='right:2%;top:29%;--r:-4deg'>🧮 CALCULATE</span><span class='dy-sticker' style='left:2%;top:43%;--r:-7deg'>DIVIDENDS</span><span class='dy-sticker' style='left:14%;top:54%;--r:7deg'>✳ COMPOUND</span><span class='dy-sticker' style='right:13%;top:51%;--r:-6deg'>↗ GROWTH</span><span class='dy-sticker' style='right:2%;top:46%;--r:-7deg'>% YIELD</span><span class='dy-sticker' style='left:2%;top:67%;--r:8deg'>BULL ↗</span><span class='dy-sticker' style='left:17%;bottom:14%;--r:-5deg'>🪙 SAVINGS</span><span class='dy-sticker' style='left:36%;bottom:5%;--r:4deg'>EMERGENCY FUND</span><span class='dy-sticker' style='left:2%;bottom:5%;--r:6deg'>🏦 INVEST</span><span class='dy-sticker' style='right:37%;bottom:4%;--r:-5deg'>INDEX FUNDS</span><span class='dy-sticker' style='right:18%;bottom:13%;--r:6deg'>TAX ↓</span><span class='dy-sticker' style='right:2%;bottom:5%;--r:-8deg'>💹 YIELD</span><span class='dy-sticker' style='right:2%;top:68%;--r:5deg'>BEAR ↘</span><span class='dy-sticker' style='left:39%;top:18%;--r:-5deg'>ASSET MIX</span><span class='dy-sticker' style='right:38%;top:18%;--r:4deg'>LOW FEES</span><span class='dy-sticker' style='left:43%;bottom:18%;--r:-3deg'>BUILD WEALTH</span></div>
 <div class='dy-load-card'><span class='dy-load-kicker'>Daily Yield</span><div aria-hidden='true' class='dy-load-ring'><b>DY</b></div><p class='dy-load-title'>Money in motion.</p><p class='dy-load-copy' id='dyLoadCopy'>Preparing your finance desk</p></div>
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
<section aria-labelledby='dyPrivacyTitle' aria-live='polite' aria-modal='true' class='dy-privacy' id='dyPrivacyPanel' role='dialog'><button aria-label='Close and use essential cookies only' class='dy-privacy-close' data-dy-consent='essential' type='button'>&#215;</button><span class='dy-privacy-kicker'>A more useful Daily Yield</span><h2 id='dyPrivacyTitle'>Choose how we improve your experience</h2><p>Essential cookies operate the site. Optional analytics help measure performance and guide meaningful improvements to articles, News desks and tools. You can change your choice later in the footer.</p><div class='dy-privacy-actions'><button class='dy-primary' data-dy-consent='all' type='button'>Allow all cookies</button><button data-dy-consent='essential' type='button'>Remind me later</button></div><a class='dy-privacy-policy' href='https://dailyyield.blogspot.com/p/privacy-policy.html'>Read Privacy Policy</a></section>
<!-- DY_PRIVACY_CHOICES_END -->"""

JS = r"""<!-- DY_SITE_ENHANCEMENTS_JS_START -->
<script>//<![CDATA[
(function(){'use strict';var D=document,H=D.documentElement,L=D.getElementById('dyPageLoader'),LC=D.getElementById('dyLoadCopy'),navTimer=0;
function safeGet(k){try{return localStorage.getItem(k)||'';}catch(e){return '';}}
function safeSet(k,v){try{localStorage.setItem(k,v);}catch(e){}}
try{localStorage.removeItem('dy-theme');}catch(e){}H.removeAttribute('data-dy-theme');var themeMeta=D.querySelector('meta[name="theme-color"]');if(themeMeta)themeMeta.content='#F8F0E3';
function showLoad(copy){if(!L)return;if(LC&&copy)LC.textContent=copy;L.removeAttribute('aria-hidden');L.setAttribute('data-active','true');H.setAttribute('data-dy-transitioning','true');}
function hideLoad(){if(!L)return;var start=window.__dyLoadStart||0,clock=(window.performance&&performance.now)?performance.now():Date.now(),wait=Math.max(0,300-(clock-start));setTimeout(function(){L.removeAttribute('data-active');L.setAttribute('aria-hidden','true');H.removeAttribute('data-dy-transitioning');if(window.performance&&performance.now){H.setAttribute('data-dy-interactive-ms',String(Math.round(performance.now())));}},wait);}
function ready(){hideLoad();}if(D.readyState==='loading')D.addEventListener('DOMContentLoaded',ready,{once:true});else ready();window.addEventListener('pageshow',ready);setTimeout(ready,1800);
D.addEventListener('click',function(e){if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;var a=e.target.closest?e.target.closest('a[href]'):null;if(!a||a.hasAttribute('download')||a.target==='_blank')return;var raw=a.getAttribute('href')||'';if(!raw||raw.charAt(0)==='#'||/^(?:mailto:|tel:|javascript:)/i.test(raw))return;var u;try{u=new URL(a.href,location.href);}catch(err){return;}if(!/^dailyyield\.blogspot\./i.test(u.hostname)||u.protocol!=='https:')return;if(u.href===location.href)return;e.preventDefault();var copy=u.pathname==='/'?'Returning to Daily Yield':u.pathname.indexOf('/p/')===0?'Opening the finance desk':'Loading the next analysis';showLoad(copy);clearTimeout(navTimer);navTimer=setTimeout(function(){location.assign(u.href);},260);setTimeout(hideLoad,10000);},true);
window.addEventListener('beforeunload',function(){showLoad('Securing your next view');});
window.addEventListener('load',function(){if(!window.performance)return;var n=performance.getEntriesByType&&performance.getEntriesByType('navigation')[0],ms=n?Math.round(n.loadEventEnd||performance.now()):Math.round(performance.now());H.setAttribute('data-dy-complete-ms',String(ms));H.setAttribute('data-dy-two-second-budget',ms<=2000?'met':'miss');});
var panel=D.getElementById('dyPrivacyPanel'),manage=D.getElementById('dyPrivacyManage'),privacyPage=1;
function privacySession(){var key='dy-privacy-session-v1',now=Date.now(),tab='';try{tab=sessionStorage.getItem('dy-tab-id')||('t'+now.toString(36)+Math.random().toString(36).slice(2));sessionStorage.setItem('dy-tab-id',tab);}catch(e){tab='t'+Math.random().toString(36).slice(2)}var state={id:'',count:0,tabs:{}},own='';try{state=JSON.parse(localStorage.getItem(key)||'null')||state;own=sessionStorage.getItem('dy-session-id')||'';}catch(e){}state.tabs=state.tabs||{};Object.keys(state.tabs).forEach(function(k){if(now-state.tabs[k]>20000)delete state.tabs[k]});var active=Object.keys(state.tabs).length;if(!state.id||(own&&own!==state.id)||(!own&&!active)){state={id:'s'+now.toString(36)+Math.random().toString(36).slice(2),count:0,tabs:{}};}state.count=(Number(state.count)||0)+1;state.tabs[tab]=now;privacyPage=state.count;try{sessionStorage.setItem('dy-session-id',state.id);localStorage.setItem(key,JSON.stringify(state));}catch(e){}var beat=setInterval(function(){try{var x=JSON.parse(localStorage.getItem(key)||'null');if(!x||x.id!==state.id){clearInterval(beat);return}x.tabs=x.tabs||{};x.tabs[tab]=Date.now();localStorage.setItem(key,JSON.stringify(x));}catch(e){}},5000);window.addEventListener('pagehide',function(){clearInterval(beat);try{var x=JSON.parse(localStorage.getItem(key)||'null');if(x&&x.id===state.id){delete x.tabs[tab];localStorage.setItem(key,JSON.stringify(x));}}catch(e){}},{once:true});H.setAttribute('data-dy-privacy-page',String(privacyPage));return privacyPage===1||privacyPage%5===0;}
function setPrivacyOpen(open){if(panel)panel.classList.toggle('dy-open',open);H.classList.toggle('dy-privacy-lock',open);if(manage)manage.setAttribute('aria-expanded',open?'true':'false');}function consentLabel(mode){return mode==='all'?'Privacy choices · All cookies allowed':mode==='essential'?'Privacy choices · Essential only':'Privacy choices';}function setConsentLabel(mode){if(manage){manage.textContent=consentLabel(mode);manage.setAttribute('data-consent',mode||'unset');}}function consent(mode){var allow=mode==='all';safeSet('dy-consent',mode);setPrivacyOpen(false);setConsentLabel(mode);window.dataLayer=window.dataLayer||[];window.dataLayer.push({event:'dy_consent_update',analytics_storage:allow?'granted':'denied',ad_storage:allow?'granted':'denied',ad_user_data:allow?'granted':'denied',ad_personalization:allow?'granted':'denied'});if(typeof window.gtag==='function')window.gtag('consent','update',{analytics_storage:allow?'granted':'denied',ad_storage:allow?'granted':'denied',ad_user_data:allow?'granted':'denied',ad_personalization:allow?'granted':'denied'});}
if(panel&&manage){var scheduled=privacySession(),savedConsent=safeGet('dy-consent'),mustChoose=savedConsent!=='all'&&savedConsent!=='essential';setConsentLabel(savedConsent);if(!mustChoose)consent(savedConsent);if(mustChoose||(savedConsent!=='all'&&scheduled))setPrivacyOpen(true);manage.addEventListener('click',function(){var open=!panel.classList.contains('dy-open');setPrivacyOpen(open);if(open)setTimeout(function(){panel.querySelector('button').focus();},0);});panel.querySelectorAll('[data-dy-consent]').forEach(function(b){b.addEventListener('click',function(){consent(b.getAttribute('data-dy-consent'));});});D.addEventListener('keydown',function(e){if(!panel.classList.contains('dy-open'))return;if(e.key==='Escape'){e.preventDefault();consent('essential');return}if(e.key==='Tab'){var f=panel.querySelectorAll('button,a[href]'),first=f[0],last=f[f.length-1];if(e.shiftKey&&D.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&D.activeElement===last){e.preventDefault();first.focus()}}});if(mustChoose||(savedConsent!=='all'&&scheduled))setTimeout(function(){panel.querySelector('.dy-primary').focus();},0);}
try{var q=new URLSearchParams(location.search),a={};['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(function(k){var v=q.get(k);if(v)a[k]=v.slice(0,160);});if(Object.keys(a).length){sessionStorage.setItem('dy-attribution',JSON.stringify(a));H.setAttribute('data-dy-attributed','true');}}catch(e){}
D.querySelectorAll('input[type="password"]').forEach(function(i){if(i.parentNode.classList.contains('dy-password-wrap'))return;var w=D.createElement('span');w.className='dy-password-wrap';i.parentNode.insertBefore(w,i);w.appendChild(i);var b=D.createElement('button');b.type='button';b.className='dy-password-toggle';b.textContent='Show';b.setAttribute('aria-label','Show password');b.addEventListener('click',function(){var show=i.type==='password';i.type=show?'text':'password';b.textContent=show?'Hide':'Show';b.setAttribute('aria-label',(show?'Hide':'Show')+' password');});w.appendChild(b);});
D.querySelectorAll('form').forEach(function(f){var s=f.querySelector('.dy-form-status');if(!s){s=D.createElement('p');s.className='dy-form-status';s.setAttribute('role','status');f.appendChild(s);}f.addEventListener('invalid',function(e){s.textContent='Please check the highlighted field and try again.';s.setAttribute('data-state','error');},true);f.addEventListener('submit',function(){if(f.checkValidity()){s.textContent='Submitted. Please follow the next on-screen step.';s.setAttribute('data-state','success');}});});
D.querySelectorAll('img:not([alt]),img[alt=""]').forEach(function(img){var box=img.closest('a,article,figure'),label=box?(box.getAttribute('aria-label')||box.textContent||''):'';label=label.replace(/\s+/g,' ').trim().slice(0,160);img.alt=label||'Daily Yield editorial image';});
D.addEventListener('error',function(e){var img=e.target,fb=img&&img.getAttribute&&img.getAttribute('data-dy-fallback');if(!fb||img.getAttribute('data-dy-fallback-used'))return;img.setAttribute('data-dy-fallback-used','true');img.src=fb;img.removeAttribute('srcset')},true);
D.querySelectorAll('.post-body img,.page-body img').forEach(function(img,n){if(!img.hasAttribute('decoding'))img.setAttribute('decoding','async');if(n>0&&!img.hasAttribute('loading'))img.setAttribute('loading','lazy');if(n===0&&!img.hasAttribute('fetchpriority'))img.setAttribute('fetchpriority','high');});
/* If an external editorial host rate-limits a photograph, recover with another
   photograph already present in that same Post; no generated or unrelated image. */
(function(){var imgs=[].slice.call(D.querySelectorAll('.item-post .post-body img'));function src(im){return im.currentSrc||im.getAttribute('src')||''}imgs.forEach(function(img,n){var current=src(img),fallback='';for(var i=n+1;i<imgs.length;i++){var u=src(imgs[i]);if(u&&u!==current&&!/(?:thumb|upload)\.wikimedia\.org/i.test(u)){fallback=u;break}}if(!fallback)return;function recover(){if(img.getAttribute('data-dy-image-recovered'))return;img.setAttribute('data-dy-image-recovered','true');img.src=fallback;img.removeAttribute('srcset')}img.addEventListener('error',recover,{once:true});if(img.complete&&img.naturalWidth===0)recover()});})();
/* Archive documents remain reader initiated. Label pages progressively append
   feed JSON as the reader scrolls; no next-page HTML document is requested. */
/* Zero-request navigation policy: never prefetch, prerender, ping or otherwise
   request another Daily Yield document before a reader actually navigates to it.
   Blogger can count speculative document requests as traffic, so selected-hub
   warming is intentionally disabled to protect analytics integrity. */
(function(){H.setAttribute('data-dy-navigation-policy','reader-navigation-only');H.setAttribute('data-dy-synthetic-document-requests','0');})();
/* Safe accelerator: caches only Blogger feed JSON already required by visible
   shelves. It rejects Page, Post, archive and label documents by construction. */
(function(){H.setAttribute('data-dy-safe-accelerator','feed-and-assets-only');D.addEventListener('pointerover',function(e){var a=e.target.closest&&e.target.closest('a'),img=a&&a.querySelector&&a.querySelector('img');if(img&&typeof img.decode==='function')img.decode().catch(function(){});},{passive:true});D.addEventListener('focusin',function(e){var a=e.target.closest&&e.target.closest('a'),img=a&&a.querySelector&&a.querySelector('img');if(img&&typeof img.decode==='function')img.decode().catch(function(){});},{passive:true});})();
/* Label pages use the Blogger JSON feed, never background-loaded HTML documents.
   Cards append as the reader approaches the end; the native More Posts control is
   removed only after the first feed batch succeeds. */
(function(){if(!/^\/search\/label\//.test(location.pathname))return;var grid=D.querySelector('#Blog1 .blog-posts,.blog-posts'),pager=D.getElementById('blog-pager');if(!grid||!window.DYFeedCache)return;var label='';try{label=decodeURIComponent(location.pathname.split('/search/label/')[1]||'').replace(/\+/g,' ');}catch(e){}if(!label)return;var start=1,batch=12,total=0,loading=false,finished=false,started=false,imageIndex={},fallbackIndex={},indexPromise=window.DYFeedCache.asset().then(function(x){imageIndex=x.images||{};fallbackIndex=x.fallbacks||{};return imageIndex;}).catch(function(){return imageIndex;}),status=D.createElement('div');status.className='dy-label-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.textContent='Loading every '+label+' post';grid.parentNode.insertBefore(status,grid.nextSibling);function text(v){return String(v||'').replace(/\s+/g,' ').trim()}function esc(v){var x=D.createElement('span');x.textContent=v||'';return x.innerHTML}function href(e){var links=e.link||[];for(var i=0;i<links.length;i++)if(links[i].rel==='alternate')return links[i].href;return '#'}function content(e){return (e.summary&&e.summary.$t)||(e.content&&e.content.$t)||''}function entryId(e){return String(e.id&&e.id.$t||'').split('post-').pop()}function details(e){var raw=content(e),box=D.createElement('div');box.innerHTML=raw;var im=box.querySelector('img'),src=imageIndex[entryId(e)]||(im&&im.getAttribute('src'))||((e.media$thumbnail||{}).url||'');if(src)src=src.replace(/\/s\d+(?:-c)?\//,'/w900-h506-p-k-no-nu/');box.querySelectorAll('style,script,noscript').forEach(function(n){n.remove()});var sn=text(box.textContent);if(sn.indexOf('max-width:')>=0||sn.indexOf('font-family:')>=0||/^\.?dy[\w-]*\s*[({]/i.test(sn))sn='';return{image:src,fallback:fallbackIndex[entryId(e)]||'',snippet:sn.slice(0,190)}}function card(e){var url=href(e),title=text((e.title||{}).$t)||'Daily Yield post',info=details(e),date=new Date((e.published||{}).$t||''),dateText=isNaN(date.getTime())?'Daily Yield':date.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}),labels=(e.category||[]).map(function(x){return text(x.term)}).filter(Boolean);var post=D.createElement('article');post.className='post dy-label-card';var media=D.createElement('a');media.className='dy-label-image';media.href=url;media.setAttribute('aria-label','Read '+title);if(info.image){var img=D.createElement('img');img.src=info.image;if(info.fallback)img.setAttribute('data-dy-fallback',info.fallback);img.alt=title;img.loading='lazy';img.decoding='async';media.appendChild(img)}else{var fallback=D.createElement('span');fallback.textContent='DY';media.appendChild(fallback)}var titleBox=D.createElement('div');titleBox.className='post-title-container';titleBox.innerHTML='<h3 class="post-title entry-title"><a href="'+esc(url)+'">'+esc(title)+'</a></h3>';var header=D.createElement('div');header.className='post-header';var meta=D.createElement('div');meta.className='post-header-line-1';meta.innerHTML='<span class="byline post-timestamp">On <time class="published">'+esc(dateText)+'</time></span>';var labelBox=D.createElement('div');labelBox.className='labels-outer-container';var labelInner=D.createElement('div');labelInner.className='labels-container';var byline=D.createElement('span');byline.className='byline post-labels';labels.forEach(function(name){var a=D.createElement('a');a.href='/search/label/'+encodeURIComponent(name);a.rel='tag';a.textContent=name;byline.appendChild(a)});labelInner.appendChild(byline);labelBox.appendChild(labelInner);header.appendChild(meta);header.appendChild(labelBox);var body=D.createElement('div');body.className='post-body-container';var snippet=D.createElement('p');snippet.className='post-snippet';snippet.textContent=info.snippet||'Open this Daily Yield post for the full report and context.';var jump=D.createElement('a');jump.className='jump-link';jump.href=url;jump.innerHTML='Read more <span class="arr">→</span>';body.appendChild(snippet);body.appendChild(jump);post.appendChild(media);post.appendChild(titleBox);post.appendChild(header);post.appendChild(body);return post}function done(){finished=true;status.dataset.finished='true';status.textContent='Every '+label+' post is now displayed';if(observer)observer.disconnect()}function load(){if(loading||finished)return;loading=true;status.textContent='Loading more '+label+' posts';var url='/feeds/posts/summary/-/'+encodeURIComponent(label)+'?alt=json&orderby=published&max-results='+batch+'&start-index='+start;Promise.all([window.DYFeedCache.get(url,120000),indexPromise]).then(function(parts){var data=parts[0],feed=data.feed||{},entries=feed.entry||[];total=Number(((feed['openSearch$totalResults']||{}).$t)||0);if(!started){grid.innerHTML='';grid.classList.add('dy-label-feed');D.body.classList.add('dy-auto-feed');if(pager)pager.remove();started=true}var frag=D.createDocumentFragment();entries.forEach(function(e){frag.appendChild(card(e))});grid.appendChild(frag);start+=entries.length;loading=false;if(!entries.length||start>total){done();return}status.textContent=(start-1)+' of '+total+' '+label+' posts loaded';if(status.getBoundingClientRect().top<innerHeight+700)setTimeout(load,80);},function(){loading=false;if(!started){D.documentElement.classList.remove('dy-label-page');status.remove()}else{status.dataset.error='true';status.textContent='Loading paused. Scroll a little to retry.'}})}var observer=null;if('IntersectionObserver' in window){observer=new IntersectionObserver(function(es){if(es[0].isIntersecting)load()},{rootMargin:'700px 0px'});observer.observe(status)}else{var check=function(){if(!finished&&status.getBoundingClientRect().top<innerHeight+700)load()};addEventListener('scroll',check,{passive:true});load()}status.addEventListener('click',function(){if(!loading&&!finished)load()});load();H.setAttribute('data-dy-label-feed','feed-json-infinite');})();
var contentH1=D.querySelector('.item-post .post-body h1'),templateTitle=D.querySelector('.item-post .post-header .post-title-container');if(contentH1&&templateTitle)templateTitle.style.display='none';
function schemaModified(){var found='';D.querySelectorAll('script[type="application/ld+json"]').forEach(function(s){try{var data=JSON.parse(s.textContent),walk=function(x){if(!x||found)return;if(Array.isArray(x)){x.forEach(walk);return;}if(typeof x==='object'){if(x.dateModified)found=String(x.dateModified);Object.keys(x).forEach(function(k){walk(x[k]);});}};walk(data);}catch(e){}});return found;}
var modified=schemaModified(),titleBox=D.querySelector('.item-post .post-title-container,.page-body h1');if(modified&&titleBox){var dt=new Date(modified);if(!isNaN(dt.getTime())){var badge=D.createElement('p');badge.className='dy-updated';badge.textContent='Last reviewed '+dt.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});if(titleBox.parentNode)titleBox.parentNode.insertBefore(badge,titleBox.nextSibling);}}
/* Consent-gated real-user performance evidence. This sends one non-pageview GA4
   event only for readers who already allowed analytics; it creates no navigation. */
(function(){var cls=0,lcp=0,inp=0,sent=false;function observe(type,fn,opts){try{new PerformanceObserver(function(list){list.getEntries().forEach(fn);}).observe(opts||{type:type,buffered:true});}catch(e){}}observe('layout-shift',function(e){if(!e.hadRecentInput)cls+=e.value;});observe('largest-contentful-paint',function(e){lcp=Math.max(lcp,e.startTime||0);});observe('event',function(e){if(e.interactionId)inp=Math.max(inp,e.duration||0);},{type:'event',buffered:true,durationThreshold:40});function send(){if(sent)return;sent=true;var nav=performance.getEntriesByType&&performance.getEntriesByType('navigation')[0],ready=nav?nav.domContentLoadedEventEnd:0,load=nav?nav.loadEventEnd:0,metrics={lcp_ms:Math.round(lcp),cls_milli:Math.round(cls*1000),inp_ms:Math.round(inp),dom_ready_ms:Math.round(ready||0),load_ms:Math.round(load||0),non_interaction:true};H.setAttribute('data-dy-rum-lcp-ms',String(metrics.lcp_ms));H.setAttribute('data-dy-rum-cls-milli',String(metrics.cls_milli));H.setAttribute('data-dy-rum-inp-ms',String(metrics.inp_ms));if(safeGet('dy-consent')==='all'&&typeof window.gtag==='function')window.gtag('event','dy_web_vitals',metrics);}D.addEventListener('visibilitychange',function(){if(D.visibilityState==='hidden')send();});window.addEventListener('pagehide',send,{once:true});setTimeout(send,15000);H.setAttribute('data-dy-rum-policy','consent-only-non-pageview');})();
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
    text = text.replace("resizeImage(data:post.featuredImage, 800)", "resizeImage(data:post.featuredImage, 640)")
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
    # Remove the obsolete multi-line developer banner; the compact version marker
    # remains, while this saves transfer bytes for functional feed recovery code.
    text = re.sub(r'<!--\s*=+\s*DAILY YIELD.*?=+\s*-->', '', text, count=1, flags=re.S)
    text = text.replace(';animation:pageIn .8s ease}', '}').replace('@keyframes pageIn{from{opacity:0}to{opacity:1}}\n', '')
    # Read the lightweight summary inventory rather than only the newest 25 full
    # Posts. This gives the home rails enough non-News entries without downloading
    # every article body and lets media$thumbnail provide the card photograph.
    text = text.replace("fetch('/feeds/posts/default?alt=json&max-results=25')", "fetch('/feeds/posts/summary?alt=json&max-results=150&orderby=published')")
    text = text.replace("fetch('/feeds/posts/default/-/News?alt=json&max-results=15')", "fetch('/feeds/posts/summary/-/News?alt=json&max-results=150&orderby=published')")
    old_home_image = 'var img=\'\';var m=/<img[^>]+src="([^"]+)"/.exec(e.content&&e.content.$t||\'\');if(m)img=m[1];'
    new_home_image = 'var img=e.media$thumbnail&&e.media$thumbnail.url||\'\';var m=/<img[^>]+src="([^"]+)"/.exec((e.summary&&e.summary.$t)||(e.content&&e.content.$t)||\'\');if(!img&&m)img=m[1];'
    old_indexed_home_image = new_home_image+'var pid=(e.id&&e.id.$t||\'\').split(\'post-\').pop(),exact=(window.__dyImageIndex||{})[pid];if(exact)img=exact;'
    indexed_home_image = new_home_image+'var pid=(e.id&&e.id.$t||\'\').split(\'post-\').pop(),exact=(window.__dyImageIndex||{})[pid],fallback=(window.__dyImageFallbacks||{})[pid]||\'\';if(exact)img=exact;'
    if old_indexed_home_image in text:
        text = text.replace(old_indexed_home_image,indexed_home_image,1)
    elif old_home_image in text:
        text = text.replace(old_home_image, indexed_home_image, 1)
    elif new_home_image in text and 'exact=(window.__dyImageIndex||{})[pid]' not in text:
        text = text.replace(new_home_image,indexed_home_image,1)
    elif indexed_home_image not in text:
        raise RuntimeError('Homepage feed image parser not found')
    # News can occupy several complete feed pages. Read the total from the first
    # lightweight response, then retrieve every remaining summary page so the two
    # Article rails cannot become empty merely because Articles are older than News.
    text = text.replace("fetch('/feeds/posts/summary?alt=json&max-results=150&orderby=published').then(function(r){return r.json();})", "articleInventory()")
    inventory_anchor = "function go(){"
    inventory_helper = "function articleInventory(){return Promise.all([window.DYFeedCache.get('/feeds/posts/summary/-/Kushal%20K.%20Daga?alt=json&max-results=16&orderby=published',300000),window.DYFeedCache.asset()]).then(function(parts){window.__dyImageIndex=parts[1].images||{};window.__dyImageFallbacks=parts[1].fallbacks||{};return parts[0];});}\nfunction go(){"
    if 'function articleInventory()' in text:
        text = re.sub(r"function articleInventory\(\)\{.*?\}\nfunction go\(\)\{", lambda _m: inventory_helper, text, count=1, flags=re.S)
    else:
        text = text.replace(inventory_anchor, inventory_helper, 1)
    # The compact exact-image index supplies News photographs, so the Homepage
    # wire can use the lightweight summary feed instead of full article bodies.
    text = text.replace("fetch('/feeds/posts/summary/-/News?alt=json&max-results=150&orderby=published')", "fetch('/feeds/posts/summary/-/News?alt=json&max-results=15&orderby=published')")
    text = text.replace("/feeds/posts/default/-/News?alt=json&max-results=15&orderby=published", "/feeds/posts/summary/-/News?alt=json&max-results=15&orderby=published")
    text = text.replace("fetch('/feeds/posts/summary/-/News?alt=json&max-results=15&orderby=published').then(function(r){return r.json();})", "window.DYFeedCache.get('/feeds/posts/summary/-/News?alt=json&max-results=15&orderby=published',300000)")
    news_call="window.DYFeedCache.get('/feeds/posts/summary/-/News?alt=json&max-results=15&orderby=published',300000).then(function(j){"
    news_indexed="Promise.all([window.DYFeedCache.get('/feeds/posts/summary/-/News?alt=json&max-results=15&orderby=published',300000),window.DYFeedCache.asset()]).then(function(parts){var j=parts[0];window.__dyImageIndex=parts[1].images||{};window.__dyImageFallbacks=parts[1].fallbacks||{};"
    text=text.replace(news_call,news_indexed,1)
    text=text.replace("window.__dyImageIndex=parts[1].images||{};\n var items=parse(j,true)", "window.__dyImageIndex=parts[1].images||{};window.__dyImageFallbacks=parts[1].fallbacks||{};\n var items=parse(j,true)",1)
    text=text.replace("<img loading=\"lazy\" alt=\"'+esc(it.title)+'\" src=\"'+esc(it.img)+'\"/>", "<img loading=\"lazy\" alt=\"'+esc(it.title)+'\" data-dy-fallback=\"'+esc(it.fallback||'')+'\" src=\"'+esc(it.img)+'\"/>",1)
    # Keep the feed entry id and hydrate missing Article thumbnails from only the
    # 16 selected entry resources instead of downloading every full article body.
    card_anchor = "var a=D.createElement('a');a.className='kd-card';a.href=it.href;"
    card_entry = "if(it.id)a.setAttribute('data-kd-entry',it.id);"
    text = re.sub(re.escape(card_anchor)+r'(?:'+re.escape(card_entry)+r')*', card_anchor+card_entry, text, count=1)
    text = text.replace("im.src=it.img;im.alt=it.title||'Daily Yield article preview';", "im.src=it.img;if(it.fallback)im.setAttribute('data-dy-fallback',it.fallback);im.alt=it.title||'Daily Yield article preview';", 1)
    text = text.replace("out.push({title:e.title&&e.title.$t||'Untitled',href:href,img:img,", "out.push({id:(e.id&&e.id.$t||'').split('post-').pop(),title:e.title&&e.title.$t||'Untitled',href:href,img:img,fallback:fallback,")
    text = text.replace("href:href,img:img,letter:", "href:href,img:img,fallback:fallback,letter:")
    text = text.replace("href:href,img:img,\n meta:", "href:href,img:img,fallback:fallback,\n meta:")
    # The exact image index has already replaced stale summary thumbnails.
    text = text.replace("href:href,img:needNews?img:'',", "href:href,img:img,fallback:fallback,")
    hydrate_anchor = "function emptyBox(row,title,msg){"
    hydrate_helper = '''function hydrate(items){var q=items.filter(function(it){return !it.img&&it.id;}).slice(),active=0;function pump(){while(active<4&&q.length){(function(it){active++;window.DYFeedCache.get('/feeds/posts/default/'+encodeURIComponent(it.id)+'?alt=json',300000).then(function(j){var e=j.entry||{},m=/<img[^>]+src=["']([^"']+)["']/.exec(e.content&&e.content.$t||''),img=m&&m[1]||'';if(!img)return;D.querySelectorAll('[data-kd-entry="'+it.id+'"] .kd-th').forEach(function(th){th.textContent='';var im=D.createElement('img');im.src=img;im.alt=it.title||'Daily Yield article preview';im.loading='lazy';im.decoding='async';th.appendChild(im);});}).catch(function(){}).then(function(){active--;pump();});})(q.shift());}}pump();}
function emptyBox(row,title,msg){'''
    if 'function hydrate(items)' in text:
        text = re.sub(r"function hydrate\(items\).*?\nfunction emptyBox\(row,title,msg\)\{", lambda _m: hydrate_helper, text, count=1, flags=re.S)
    else:
        text = text.replace(hydrate_anchor, hydrate_helper, 1)
    text = text.replace("else autoRail(latest,31);", "else{autoRail(latest,31);hydrate(items);}")
    text = text.replace("if(fill(pop,earlier))autoRail(pop,24);", "if(fill(pop,earlier)){autoRail(pop,24);hydrate(earlier);}")
    # Both homepage article rails are chronological. PopularPosts is intentionally
    # not used here because its opaque ranking made the desk look unordered.
    text = text.replace("<p class='kd-rowlab'>Most popular</p>", "<p class='kd-rowlab'>Earlier articles</p>", 1)
    chronological = """var all=parse(j,false);
 var items=all.slice(0,8);
 if(!fill(latest,items))emptyBox(latest,'Waiting for your first post','This row fills with your latest general articles the moment you publish \\u2014 no placeholders, no invented headlines.');
 else autoRail(latest,31);
 var earlier=all.slice(8,16);
 if(fill(pop,earlier))autoRail(pop,24);
 else emptyBox(pop,'More dated articles will appear here','This second row continues the same newest-first article timeline.');"""
    if "var all=parse(j,false);" not in text:
        rail_pattern = re.compile(r"var items=parse\(j,false\)\.slice\(0,10\);.*?else emptyBox\(pop,'No popular picks yet'.*?\);", re.S)
        text, rail_count = rail_pattern.subn(lambda _m: chronological, text, count=1)
        if rail_count != 1:
            raise RuntimeError('homepage chronological rail source not found')
    # Embed the compact exact-image map directly in the Theme. Card rendering no
    # longer depends on GitHub availability and does not spend an extra request.
    image_index = json.loads(Path("LABEL_FEED_INDEX.json").read_text(encoding="utf-8"))
    head = HEAD.replace("__DY_EXACT_IMAGE_INDEX__", json.dumps(image_index, ensure_ascii=False, separators=(",", ":")))
    if "DY_SITE_ENHANCEMENTS_HEAD_START" in text:
        text = replace_marked(text, "<!-- DY_SITE_ENHANCEMENTS_HEAD_START -->", "<!-- DY_SITE_ENHANCEMENTS_HEAD_END -->", head)
    else:
        text = text.replace("</head>", head + "\n</head>", 1)
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
    if "DY_PRIVACY_CHOICES_START" in text:
        text = replace_marked(text, "<!-- DY_PRIVACY_CHOICES_START -->", "<!-- DY_PRIVACY_CHOICES_END -->", PRIVACY)
    else:
        text = text.replace("</body>", PRIVACY + "\n</body>", 1)
    if "DY_SITE_ENHANCEMENTS_JS_START" in text:
        text = replace_marked(text, "<!-- DY_SITE_ENHANCEMENTS_JS_START -->", "<!-- DY_SITE_ENHANCEMENTS_JS_END -->", JS)
    else:
        text = text.replace("</body>", JS + "\n</body>", 1)
    # Production JS does not need explanatory block comments. Removing only those
    # inside this owned marker preserves code while keeping the Theme under budget.
    a,b='<!-- DY_SITE_ENHANCEMENTS_JS_START -->','<!-- DY_SITE_ENHANCEMENTS_JS_END -->'
    before,rest=text.split(a,1);owned,after=rest.split(b,1)
    owned=re.sub(r'/\*.*?\*/','',owned,flags=re.S)
    text=before+a+owned+b+after
    return text


def main():
    for path in THEMES:
        original = path.read_text(encoding="utf-8")
        updated = inject(original)
        path.write_text(updated, encoding="utf-8")
        print(path, "updated" if updated != original else "already current")


if __name__ == "__main__":
    main()
