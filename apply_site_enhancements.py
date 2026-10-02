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
/* Full-screen selected Option 1: a dense, dependency-free finance sticker wall
   with one lightweight centre-ring animation and one composited field drift. */
.dy-load-screen{position:fixed;inset:0;z-index:2147483000;display:grid;place-items:center;overflow:hidden;isolation:isolate;contain:strict;background:radial-gradient(circle at 50% 42%,#fffaf1 0,#f8ecda 58%,#efd8bd 100%);color:#241610;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .24s ease-out,visibility 0s linear .24s;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.dy-load-screen[data-active='true']{opacity:1;visibility:visible;pointer-events:auto;transition:opacity .22s ease-out,visibility 0s;animation:dyLoaderFadeIn .24s ease-out both}.dy-symbol-field{position:absolute;z-index:0;inset:-6%;display:grid;grid-template-columns:repeat(12,minmax(58px,1fr));grid-template-rows:repeat(9,minmax(58px,1fr));align-items:center;justify-items:center;gap:5px;transform:rotate(-3deg) scale(1.07);animation:dyFieldDrift 5s ease-in-out infinite;will-change:transform}.dy-symbol-field span{display:grid;place-items:center;min-width:42px;min-height:42px;padding:5px;color:#9c4522;font:800 clamp(20px,3vw,42px)/1 Georgia,"Times New Roman",serif;opacity:.18}.dy-symbol-field span:nth-child(3n){color:#315d4b;transform:rotate(8deg)}.dy-symbol-field span:nth-child(4n){color:#bc7d22;transform:rotate(-9deg)}.dy-symbol-field span:nth-child(5n){border:1px solid currentColor;border-radius:12px;background:rgba(255,253,248,.42);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;font-size:clamp(10px,1.5vw,17px);letter-spacing:.04em}.dy-symbol-field span:nth-child(7n){border-radius:50%;outline:1px solid currentColor;outline-offset:5px}
.dy-sticker-field{position:absolute;z-index:2;inset:0;pointer-events:none}.dy-sticker{--s:1;position:absolute;display:flex;align-items:center;justify-content:center;gap:7px;padding:9px 13px;border:2px solid currentColor;border-radius:15px;background:#fffdf8;color:#9c4522;box-shadow:4px 6px 0 rgba(36,22,16,.13);font:800 clamp(10px,1.25vw,15px)/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.03em;white-space:nowrap;transform:rotate(var(--r,0deg)) scale(var(--s));transform-origin:center}.dy-sticker:nth-child(3n){color:#315d4b;background:#f3f5e9}.dy-sticker:nth-child(4n){color:#80571d;background:#fff1c9}.dy-sticker:nth-child(5n){border-radius:999px}.dy-load-card{position:relative;z-index:5;width:min(78vw,310px);aspect-ratio:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border:2px solid #eadcc8;border-radius:50%;background:rgba(255,253,248,.97);box-shadow:0 28px 90px -40px rgba(36,22,16,.65)}.dy-load-kicker{display:block;margin-bottom:14px;color:#241610;font:800 10px/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.32em;text-transform:uppercase}.dy-load-ring{position:relative;width:86px;height:86px;border-radius:50%}.dy-load-ring::before,.dy-load-ring::after{content:"";position:absolute;border-radius:50%}.dy-load-ring::before{inset:0;border:6px solid rgba(188,91,51,.16);border-top-color:#bc5b33;border-right-color:#f0b180;animation:dyRing 1s linear infinite}.dy-load-ring::after{inset:19px;background:#bc5b33;box-shadow:inset 0 0 0 6px #fff8ee}.dy-load-ring b{position:absolute;inset:0;z-index:2;display:grid;place-items:center;color:#fff8ee;font:700 18px/1 Georgia,"Times New Roman",serif}.dy-load-title{margin:17px 20px 8px;color:#241610;font:700 clamp(27px,7vw,38px)/1.05 Georgia,"Times New Roman",serif;letter-spacing:-.035em}.dy-load-copy{min-height:1.5em;margin:0 18px;color:#7a6a58;font:700 11px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;letter-spacing:.07em}
@keyframes dyLoaderFadeIn{from{opacity:0}to{opacity:1}}@keyframes dyRing{to{transform:rotate(360deg)}}@keyframes dyFieldDrift{0%,100%{transform:rotate(-3deg) scale(1.07) translateY(0)}50%{transform:rotate(-2deg) scale(1.07) translateY(-8px)}}
@media(max-width:640px){.dy-symbol-field{inset:-3%;grid-template-columns:repeat(7,1fr);grid-template-rows:repeat(16,1fr);gap:0;transform:rotate(-2deg) scale(1.03);animation-name:dyFieldDriftMobile}.dy-symbol-field span{min-width:28px;min-height:28px;font-size:24px;opacity:.21}.dy-sticker{--s:.62;padding:8px 10px}.dy-load-card{width:235px}.dy-load-title{font-size:28px;margin-top:13px}.dy-load-ring{width:70px;height:70px}.dy-load-ring::after{inset:15px}}
@keyframes dyFieldDriftMobile{0%,100%{transform:rotate(-2deg) scale(1.03) translateY(0)}50%{transform:rotate(-1deg) scale(1.03) translateY(-6px)}}
/* Compact high-density layout: more dated content remains visible per screen. */
html,body{max-width:100%;overflow-x:clip}.fk-home main,.fk-home #enhancedHome,.kd-sec,.kd-row,.kd-mqwrap{max-width:100%;min-width:0}.kd-row,.kd-mqwrap{overflow-x:auto;overscroll-behavior-inline:contain}
.fk-rest .blog-posts{grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.fk-rest .blog-posts .post{padding:16px}.fk-rest .blog-posts h3.post-title{font-size:18px}.fk-rest .blog-posts .post-snippet{font-size:12px;line-height:1.55;-webkit-line-clamp:2}.blog-posts .snippet-thumbnail-container{aspect-ratio:16/9}.dy-auto-feed #blog-pager{display:none!important}.dy-feed-sentinel{grid-column:1/-1;min-height:56px;display:grid;place-items:center;color:var(--muted);font:700 10px/1.4 var(--font-body);letter-spacing:.1em;text-transform:uppercase}.dy-feed-sentinel[data-finished='true']{min-height:28px;opacity:.72}
/* Keep the subscription desk useful without letting it dominate the page. */
.dy-sub-zone{padding:24px 16px!important}.dy-sub-shell{width:min(1040px,100%)!important;border-radius:22px!important}.dy-sub-grid{grid-template-columns:1.05fr .95fr!important;min-height:0!important}.dy-sub-story,.dy-sub-formside{padding:26px!important}.dy-sub-story h2{font-size:clamp(32px,4vw,46px)!important;line-height:1!important}.dy-sub-lede{margin:14px 0 18px!important;font-size:13px!important;line-height:1.55!important}.dy-sub-benefits{gap:7px!important}.dy-sub-benefits li{min-height:78px!important;padding:11px!important;border-radius:12px!important}.dy-sub-benefits svg{width:18px!important;height:18px!important;margin-bottom:6px!important}.dy-sub-benefits span{margin-top:3px!important;font-size:9px!important}.dy-sub-formside h3{font-size:27px!important}.dy-sub-formside>p{margin:8px 0 12px!important}.dy-sub-steps{margin-bottom:12px!important}.dy-sub-field input,.dy-sub-submit{height:46px!important;min-height:46px!important}.dy-sub-choices{margin-top:10px!important}.dy-sub-choice{min-height:52px!important;padding:9px!important}.dy-sub-trust{margin-top:10px!important}
/* Five tool benches share one compact row as one navigational unit. */
#kd-tools{padding-top:34px!important;padding-bottom:34px!important}#kd-tools .kd-head{margin-bottom:16px!important}#kd-tools .kd-digest{grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:8px!important}#kd-tools .kd-dg{min-width:0;padding:12px 10px!important;border-radius:11px!important}#kd-tools .kd-dg b{font-size:14px!important}#kd-tools .kd-dg span{font-size:10px!important;line-height:1.4!important}#kd-tools .kd-dg i{font-size:8px!important}
@media(max-width:760px){.fk-rest .blog-posts,.fk-home .blog-posts{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:9px!important;padding:0 9px!important}.blog-posts .post{padding:11px!important}.blog-posts h3.post-title{font-size:15px!important}.blog-posts .post-header-line-1{font-size:8px!important}.blog-posts .post-labels a{padding:4px 7px!important;font-size:7px!important}.blog-posts .post-snippet{display:none!important}.dy-sub-zone{padding:16px 9px!important}.dy-sub-grid{grid-template-columns:1fr!important}.dy-sub-story,.dy-sub-formside{padding:18px!important}.dy-sub-story h2{font-size:30px!important}.dy-sub-lede{font-size:11px!important;margin-bottom:0!important}.dy-sub-benefits,.dy-sub-orbit,.dy-sub-steps,.dy-sub-trust{display:none!important}.dy-sub-formside h3{font-size:23px!important}.dy-sub-formside>p{font-size:11px!important}.dy-sub-choices{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:5px!important}.dy-sub-choice,.dy-sub-choice-wide{grid-column:auto!important;min-height:46px!important;padding:7px!important}.dy-sub-choice svg{display:none}.dy-sub-choice small{display:none}.dy-sub-choice b{font-size:8px!important}.dy-sub-consent{font-size:8px!important}#kd-tools{padding:24px 8px!important}#kd-tools .kd-digest{grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:4px!important}#kd-tools .kd-dg{padding:8px 4px!important;text-align:center}#kd-tools .kd-dg b{font-size:9px!important;line-height:1.15!important;overflow-wrap:anywhere}#kd-tools .kd-dg span,#kd-tools .kd-dg i{display:none!important}}
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
<section aria-labelledby='dyPrivacyTitle' aria-live='polite' class='dy-privacy' id='dyPrivacyPanel' role='dialog'><span class='dy-privacy-kicker'>Reader measurement choice</span><h2 id='dyPrivacyTitle'>Help Daily Yield understand what readers value</h2><p>Essential storage keeps your preferences. If you allow optional analytics, Google Analytics records visits and engagement so Daily Yield can improve its articles, News desks and tools. The complete site works either way, and you can change this choice in the footer.</p><div class='dy-privacy-actions'><button class='dy-primary' data-dy-consent='analytics' type='button'>Allow optional analytics</button><button data-dy-consent='essential' type='button'>Continue with essential only</button><a href='https://dailyyield.blogspot.com/p/privacy-policy.html'>Read Privacy Policy</a></div></section>
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
var panel=D.getElementById('dyPrivacyPanel'),manage=D.getElementById('dyPrivacyManage');
function consentLabel(mode){return mode==='analytics'?'Privacy choices · Analytics allowed':mode==='essential'?'Privacy choices · Essential only':'Privacy choices';}function setConsentLabel(mode){if(manage){manage.textContent=consentLabel(mode);manage.setAttribute('data-consent',mode||'unset');}}function consent(mode){safeSet('dy-consent',mode);if(panel)panel.classList.remove('dy-open');if(manage)manage.setAttribute('aria-expanded','false');setConsentLabel(mode);window.dataLayer=window.dataLayer||[];window.dataLayer.push({event:'dy_consent_update',analytics_storage:mode==='analytics'?'granted':'denied'});if(typeof window.gtag==='function')window.gtag('consent','update',{analytics_storage:mode==='analytics'?'granted':'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});}
if(panel&&manage){var hero=D.querySelector('.fk-home .kv-hero');if(hero)hero.insertAdjacentElement('afterend',panel);var savedConsent=safeGet('dy-consent');setConsentLabel(savedConsent);if(savedConsent==='analytics'||savedConsent==='essential')consent(savedConsent);else panel.classList.add('dy-open');manage.addEventListener('click',function(){var open=!panel.classList.contains('dy-open');panel.classList.toggle('dy-open',open);manage.setAttribute('aria-expanded',open?'true':'false');if(open){if(hero)panel.scrollIntoView({behavior:'smooth',block:'center'});setTimeout(function(){panel.querySelector('button').focus();},hero?500:0);}});panel.querySelectorAll('[data-dy-consent]').forEach(function(b){b.addEventListener('click',function(){consent(b.getAttribute('data-dy-consent'));});});}
try{var q=new URLSearchParams(location.search),a={};['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(function(k){var v=q.get(k);if(v)a[k]=v.slice(0,160);});if(Object.keys(a).length){sessionStorage.setItem('dy-attribution',JSON.stringify(a));H.setAttribute('data-dy-attributed','true');}}catch(e){}
D.querySelectorAll('input[type="password"]').forEach(function(i){if(i.parentNode.classList.contains('dy-password-wrap'))return;var w=D.createElement('span');w.className='dy-password-wrap';i.parentNode.insertBefore(w,i);w.appendChild(i);var b=D.createElement('button');b.type='button';b.className='dy-password-toggle';b.textContent='Show';b.setAttribute('aria-label','Show password');b.addEventListener('click',function(){var show=i.type==='password';i.type=show?'text':'password';b.textContent=show?'Hide':'Show';b.setAttribute('aria-label',(show?'Hide':'Show')+' password');});w.appendChild(b);});
D.querySelectorAll('form').forEach(function(f){var s=f.querySelector('.dy-form-status');if(!s){s=D.createElement('p');s.className='dy-form-status';s.setAttribute('role','status');f.appendChild(s);}f.addEventListener('invalid',function(e){s.textContent='Please check the highlighted field and try again.';s.setAttribute('data-state','error');},true);f.addEventListener('submit',function(){if(f.checkValidity()){s.textContent=f.classList.contains('dy-sub-form')?'Opening the secure confirmation step in a new tab.':'Submitted. Please follow the next on-screen step.';s.setAttribute('data-state','success');}});});
D.querySelectorAll('img:not([alt]),img[alt=""]').forEach(function(img){var box=img.closest('a,article,figure'),label=box?(box.getAttribute('aria-label')||box.textContent||''):'';label=label.replace(/\s+/g,' ').trim().slice(0,160);img.alt=label||'Daily Yield editorial image';});
D.querySelectorAll('.post-body img,.page-body img').forEach(function(img,n){if(!img.hasAttribute('decoding'))img.setAttribute('decoding','async');if(n>0&&!img.hasAttribute('loading'))img.setAttribute('loading','lazy');if(n===0&&!img.hasAttribute('fetchpriority'))img.setAttribute('fetchpriority','high');});
/* Gapless chronological feed: preload the next Blogger page before the reader
   reaches the end, append it in server order, and continue until exhausted. */
(function(){var grid=D.querySelector('.blog-posts.hfeed'),pager=D.getElementById('blog-pager');if(!grid||!pager)return;var next=pager.querySelector('.blog-pager-older-link'),busy=false,seen={};grid.querySelectorAll('h3.post-title a').forEach(function(a){seen[a.href]=1;});function sortGrid(){var cards=[].slice.call(grid.querySelectorAll(':scope > .post-outer-container'));cards.sort(function(a,b){var ad=a.querySelector('time.published'),bd=b.querySelector('time.published');return (Date.parse(bd&&bd.getAttribute('datetime')||0)||0)-(Date.parse(ad&&ad.getAttribute('datetime')||0)||0);});cards.forEach(function(card){grid.insertBefore(card,sent||null);});}sortGrid();if(!next)return;H.classList.add('dy-auto-feed');var sent=D.createElement('div');sent.className='dy-feed-sentinel';sent.setAttribute('role','status');sent.textContent='Loading more articles';grid.appendChild(sent);function load(){if(busy||!next)return;busy=true;var href=next.href;fetch(href,{credentials:'same-origin'}).then(function(r){if(!r.ok)throw Error('feed');return r.text();}).then(function(markup){var doc=new DOMParser().parseFromString(markup,'text/html'),fresh=doc.querySelectorAll('.blog-posts.hfeed .post-outer-container'),frag=D.createDocumentFragment(),added=0;fresh.forEach(function(article){var a=article.querySelector('h3.post-title a'),key=a&&a.href;if(key&&seen[key])return;if(key)seen[key]=1;article.classList.add('in');article.classList.remove('will-reveal');article.querySelectorAll('img').forEach(function(img){img.loading='lazy';img.decoding='async';});frag.appendChild(D.importNode(article,true));added++;});grid.insertBefore(frag,sent);sortGrid();next=doc.querySelector('#blog-pager .blog-pager-older-link');busy=false;if(!next){sent.textContent='All articles loaded';sent.setAttribute('data-finished','true');if(io)io.disconnect();}else{sent.textContent=added?'Loading more articles':'Continuing the archive';setTimeout(load,0);}}).catch(function(){busy=false;sent.textContent='More articles will load when the connection recovers';});}var io;if('IntersectionObserver' in window){io=new IntersectionObserver(function(es){if(es.some(function(e){return e.isIntersecting;}))load();},{rootMargin:'1400px 0px'});io.observe(sent);load();}else load();})();
/* Selected-destination navigation warmer: every Daily Yield Page or Post can
   trigger it, including a direct social-media deep link. Only Home, Daily
   Article, Daily News and canonical label archives are warmed. Destinations are
   fetched as low-priority documents without execution or synthetic pageviews. */
(function(){H.setAttribute('data-dy-prefetch-scope','every-entry-selected-destinations');var mobile=matchMedia('(max-width:760px)').matches,limit=52,used=0,seen={},queue=[],running=false,core=['/','/p/article.html','/p/daily-news.html'],labels='Contrarian Hooks|Age and Wealth Milestones|Passive Income Reality|Middle Class Survival|Money Audits and Case Studies|Housing Cars and Big Buys|Automation and Money Systems|Credit Debt and Optimization|AI Fintech and Future Money|Money Psychology and Mindset|Investing Strategies|Retirement Pensions and FIRE|Taxes and Account Optimization|Career Salary and Raises|Side Hustles That Work|Insurance and Protection|Couples Family and Kids|Starters Students and First Jobs|Spending Lifestyle and Frugality|Rich Habits vs Broke Habits|Recessions Crashes and Defense|Cash Savings and Emergency Funds|Real Estate Investing|Myths Scams and Bad Advice|2026 Money Moves|US|China|Germany|India|Japan|UK|France|Italy|Russia|Canada|Brazil|Spain|Mexico|Australia|South Korea|Market and Trading|Economy and Macro Policy|Corporate Finance and Industry|Personal Finance|Global News'.split('|');function eligible(a){if(!a||used>=limit)return'';var u;try{u=new URL(a.href,location.href);}catch(e){return'';}if(u.origin!==location.origin||u.href===location.href||u.protocol!=='https:'||u.hash&&u.pathname===location.pathname&&u.search===location.search)return'';if(/\/feeds(?:\/|\?|$)/.test(u.pathname)||/^(?:mailto:|tel:|javascript:)/i.test(a.getAttribute('href')||''))return'';u.hash='';return u.href;}function warm(href){if(!href||seen[href]||used>=limit||D.hidden)return;seen[href]=1;used++;var link=D.createElement('link');link.rel='prefetch';link.as='document';link.href=href;link.setAttribute('fetchpriority','low');D.head.appendChild(link);H.setAttribute('data-dy-prefetched',String(used));}function drain(deadline){running=false;if(D.hidden)return;while(queue.length&&used<limit&&(!deadline||deadline.timeRemaining()>4||deadline.didTimeout)){warm(queue.shift());if(mobile)break;}if(queue.length&&used<limit)schedule();}function schedule(){if(running)return;running=true;if('requestIdleCallback' in window)requestIdleCallback(drain,{timeout:1800});else setTimeout(function(){drain(null);},700);}function collect(){var ranked=[];core.forEach(function(path){var a=D.createElement('a');a.href=path;ranked.push(a);});labels.forEach(function(label){var a=D.createElement('a');a.href='/search/label/'+encodeURIComponent(label)+'?max-results=50';ranked.push(a);});ranked.forEach(function(a){var h=eligible(a);if(h&&!seen[h]&&queue.indexOf(h)<0)queue.push(h);});schedule();}function intent(e){var a=e.target.closest&&e.target.closest('a[href]'),h=eligible(a);if(h){queue=queue.filter(function(x){return x!==h;});warm(h);}}D.addEventListener('pointerover',intent,{passive:true});D.addEventListener('focusin',intent,{passive:true});D.addEventListener('touchstart',intent,{passive:true});if(D.readyState==='loading')D.addEventListener('DOMContentLoaded',function(){setTimeout(collect,0);},{once:true});else setTimeout(collect,0);window.addEventListener('pageshow',collect);})();
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
    if old_home_image in text:
        text = text.replace(old_home_image, new_home_image, 1)
    elif new_home_image not in text:
        raise RuntimeError('Homepage feed image parser not found')
    # The newest 150 mixed entries can still be almost entirely News. Merge a
    # second lightweight summary page so both Article rows have genuine posts.
    text = text.replace("fetch('/feeds/posts/summary?alt=json&max-results=150&orderby=published').then(function(r){return r.json();})", "articleInventory()")
    inventory_anchor = "function go(){"
    inventory_helper = "function articleInventory(){return Promise.all([1,151].map(function(start){return fetch('/feeds/posts/summary?alt=json&max-results=150&orderby=published&start-index='+start).then(function(r){if(!r.ok)throw Error('feed');return r.json();});})).then(function(parts){var entries=[];parts.forEach(function(j){entries=entries.concat(j.feed&&j.feed.entry||[]);});return {feed:{entry:entries}};});}\nfunction go(){"
    if 'function articleInventory()' not in text:
        text = text.replace(inventory_anchor, inventory_helper, 1)
    # News needs only a small newest batch; retain full content there so cards can
    # recover photographs even when Blogger omits media$thumbnail.
    text = text.replace("fetch('/feeds/posts/summary/-/News?alt=json&max-results=150&orderby=published')", "fetch('/feeds/posts/default/-/News?alt=json&max-results=15&orderby=published')")
    # Keep the feed entry id and hydrate missing Article thumbnails from only the
    # 16 selected entry resources instead of downloading every full article body.
    text = text.replace("var a=D.createElement('a');a.className='kd-card';a.href=it.href;", "var a=D.createElement('a');a.className='kd-card';a.href=it.href;if(it.id)a.setAttribute('data-kd-entry',it.id);")
    text = text.replace("out.push({title:e.title&&e.title.$t||'Untitled',href:href,img:img,", "out.push({id:(e.id&&e.id.$t||'').split('post-').pop(),title:e.title&&e.title.$t||'Untitled',href:href,img:img,")
    hydrate_anchor = "function emptyBox(row,title,msg){"
    hydrate_helper = '''function hydrate(items){var q=items.filter(function(it){return !it.img&&it.id;}).slice(),active=0;function pump(){while(active<4&&q.length){(function(it){active++;fetch('/feeds/posts/default/'+encodeURIComponent(it.id)+'?alt=json').then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(j){var e=j.entry||{},img=e.media$thumbnail&&e.media$thumbnail.url||'',m=/<img[^>]+src="([^"]+)"/.exec(e.content&&e.content.$t||'');if(!img&&m)img=m[1];if(!img)return;D.querySelectorAll('[data-kd-entry="'+it.id+'"] .kd-th').forEach(function(th){th.textContent='';var im=D.createElement('img');im.src=img;im.alt=it.title||'Daily Yield article preview';im.loading='lazy';th.appendChild(im);});}).catch(function(){}).then(function(){active--;pump();});})(q.shift());}}pump();}
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
