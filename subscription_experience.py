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
/* Site-wide Signal Desk: follows Daily Yield's established ivory/copper palette. */
.dy-sub-zone{position:relative;isolation:isolate;width:100%;padding:clamp(54px,8vw,104px) clamp(16px,4.5vw,48px);overflow:hidden;background:linear-gradient(180deg,var(--paper),#f2e5d2)}
.dy-sub-zone .sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
.dy-sub-zone::before,.dy-sub-zone::after{content:"";position:absolute;z-index:-2;border-radius:50%;filter:blur(1px);pointer-events:none}
.dy-sub-zone::before{width:clamp(320px,48vw,720px);height:clamp(320px,48vw,720px);right:-16%;top:-42%;background:radial-gradient(circle,rgba(188,91,51,.20),rgba(188,91,51,0) 68%);animation:dySubDrift 11s ease-in-out infinite alternate}
.dy-sub-zone::after{width:430px;height:430px;left:-190px;bottom:-230px;background:radial-gradient(circle,rgba(217,160,91,.19),rgba(217,160,91,0) 70%);animation:dySubDrift 14s ease-in-out -5s infinite alternate-reverse}
.dy-sub-shell{position:relative;width:min(1180px,100%);margin:auto;border:1px solid rgba(115,73,43,.20);border-radius:clamp(24px,4vw,42px);background:linear-gradient(145deg,rgba(255,253,248,.98),rgba(255,247,235,.96));box-shadow:0 34px 100px -52px rgba(36,22,16,.58),inset 0 1px rgba(255,255,255,.9);overflow:hidden}
.dy-sub-shell::before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(105deg,transparent 20%,rgba(255,255,255,.7) 46%,transparent 70%);transform:translateX(-130%);animation:dySubSheen 8s ease-in-out 1.2s infinite}
.dy-sub-grid{display:grid;grid-template-columns:minmax(0,1.17fr) minmax(340px,.83fr);min-height:630px}
.dy-sub-story{position:relative;padding:clamp(34px,6vw,78px);overflow:hidden;color:#fff8ee;background:radial-gradient(500px 330px at 85% 8%,rgba(217,160,91,.20),transparent 68%),linear-gradient(145deg,#241610,#351c10 58%,#512618)}
.dy-sub-story::after{content:"DY";position:absolute;right:-.04em;bottom:-.26em;font:700 clamp(180px,27vw,370px)/1 var(--font-display);letter-spacing:-.12em;color:rgba(255,248,238,.035);pointer-events:none}
.dy-sub-orbit{position:absolute;width:270px;height:270px;right:-94px;top:-86px;border:1px solid rgba(241,179,131,.24);border-radius:50%;animation:dySubSpin 24s linear infinite}
.dy-sub-orbit::before,.dy-sub-orbit::after{content:"";position:absolute;border-radius:50%}.dy-sub-orbit::before{width:13px;height:13px;left:29px;top:47px;background:#f1b383;box-shadow:0 0 0 8px rgba(241,179,131,.09),0 0 34px rgba(241,179,131,.7)}.dy-sub-orbit::after{inset:45px;border:1px dashed rgba(241,179,131,.20)}
.dy-sub-kicker{position:relative;display:inline-flex;align-items:center;gap:10px;margin:0 0 24px;color:#f1b383;font:800 10px/1 var(--font-body);letter-spacing:.2em;text-transform:uppercase}
.dy-sub-live{width:8px;height:8px;border-radius:50%;background:#f1b383;box-shadow:0 0 0 0 rgba(241,179,131,.58);animation:dySubPulse 2.2s infinite}
.dy-sub-story h2{position:relative;max-width:730px;margin:0;color:#fffaf1;font:600 clamp(40px,6.1vw,76px)/.98 var(--font-display);letter-spacing:-.052em}
.dy-sub-story h2 em{display:block;color:#f1b383;font-weight:500}
.dy-sub-lede{position:relative;max-width:650px;margin:25px 0 31px;color:#dfcfbe;font-size:clamp(15px,1.8vw,18px);line-height:1.75}
.dy-sub-benefits{position:relative;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;max-width:690px;margin:0;padding:0;list-style:none}
.dy-sub-benefits li{min-height:118px;padding:17px;border:1px solid rgba(241,179,131,.18);border-radius:18px;background:rgba(255,255,255,.045);backdrop-filter:blur(4px);transition:transform .35s var(--ease),border-color .35s,background .35s}
.dy-sub-benefits li:hover{transform:translateY(-4px);border-color:rgba(241,179,131,.55);background:rgba(255,255,255,.075)}
.dy-sub-benefits svg{width:23px;height:23px;margin-bottom:13px;stroke:#f1b383;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.dy-sub-benefits b{display:block;color:#fff8ee;font:700 12px/1.25 var(--font-body);letter-spacing:.02em}.dy-sub-benefits span{display:block;margin-top:6px;color:#bdac9b;font-size:11px;line-height:1.45}
.dy-sub-formside{position:relative;padding:clamp(32px,5vw,64px);display:flex;flex-direction:column;justify-content:center;background:rgba(255,253,248,.78)}
.dy-sub-eyebrow{margin:0 0 10px;color:var(--accent-dark);font:800 10px/1 var(--font-body);letter-spacing:.18em;text-transform:uppercase}.dy-sub-formside h3{font-size:clamp(29px,3.2vw,42px);line-height:1.08;letter-spacing:-.03em}.dy-sub-formside>p{margin:13px 0 21px;color:var(--muted);font-size:13px;line-height:1.68}
.dy-sub-steps{display:flex;align-items:center;margin:0 0 23px}.dy-sub-step{display:flex;align-items:center;gap:7px;color:var(--muted);font:700 9px/1.2 var(--font-body);letter-spacing:.08em;text-transform:uppercase}.dy-sub-step i{width:25px;height:25px;border:1px solid var(--line);border-radius:50%;display:grid;place-items:center;color:var(--accent-dark);font-style:normal;background:#fff}.dy-sub-line{height:1px;flex:1;min-width:12px;margin:0 8px;background:linear-gradient(90deg,var(--accent),var(--line));transform-origin:left;animation:dySubLine 3.2s ease-in-out infinite}
.dy-sub-form{margin:0}.dy-sub-field{position:relative}.dy-sub-field svg{position:absolute;left:17px;top:50%;width:19px;height:19px;transform:translateY(-50%);stroke:var(--accent-dark);fill:none;stroke-width:1.7}.dy-sub-field input{width:100%;height:58px;padding:0 17px 0 48px;border:1px solid var(--line);border-radius:15px;background:#fff;color:var(--ink);font:500 15px var(--font-body);outline:none;box-shadow:0 9px 30px -25px rgba(36,22,16,.6);transition:border-color .3s,box-shadow .3s,transform .3s}.dy-sub-field input:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-soft),0 13px 35px -25px rgba(36,22,16,.6);transform:translateY(-1px)}.dy-sub-field input::placeholder{color:#9b8974}
.dy-sub-submit{position:relative;width:100%;min-height:58px;margin-top:10px;padding:14px 49px 14px 20px;border-radius:15px;background:linear-gradient(120deg,var(--accent-dark),var(--accent),#d67c50);background-size:180% 100%;color:#fff8ee;box-shadow:0 15px 34px -17px rgba(156,69,34,.8);font:800 12px/1.35 var(--font-body);letter-spacing:.08em;text-transform:uppercase;overflow:hidden;transition:transform .3s var(--ease),box-shadow .3s,background-position .5s}.dy-sub-submit:hover{transform:translateY(-3px);box-shadow:0 19px 38px -16px rgba(156,69,34,.9);background-position:100% 0}.dy-sub-submit:active{transform:translateY(-1px)}.dy-sub-submit svg{position:absolute;right:20px;top:50%;width:20px;height:20px;transform:translateY(-50%);stroke:currentColor;fill:none;stroke-width:1.8;transition:transform .3s}.dy-sub-submit:hover svg{transform:translate(4px,-50%)}
.dy-sub-consent{margin:10px 2px 0!important;color:#877562!important;font-size:10px!important;line-height:1.5!important}.dy-sub-consent a{color:var(--accent-dark);text-decoration:underline;text-underline-offset:2px}
.dy-sub-choices{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:18px}.dy-sub-choice{min-height:70px;padding:13px;border:1px solid var(--line);border-radius:14px;background:#fff;display:flex;align-items:center;gap:11px;color:var(--ink);transition:transform .3s var(--ease),border-color .3s,box-shadow .3s}.dy-sub-choice:hover{transform:translateY(-3px);border-color:#c99770;box-shadow:0 12px 28px -24px rgba(36,22,16,.65)}.dy-sub-choice svg{width:24px;height:24px;flex:none;stroke:var(--accent-dark);fill:none;stroke-width:1.65;stroke-linecap:round;stroke-linejoin:round}.dy-sub-choice b{display:block;font-size:11px;line-height:1.25}.dy-sub-choice small{display:block;margin-top:4px;color:var(--muted);font-size:9px;line-height:1.35}.dy-sub-choice-wide{grid-column:1/-1}
.dy-sub-trust{display:flex;flex-wrap:wrap;gap:7px 13px;margin-top:17px;color:#796957;font:700 9px/1.3 var(--font-body);letter-spacing:.04em}.dy-sub-trust span::before{content:"\2713";margin-right:5px;color:var(--accent-dark)}
.dy-sub-beacon{position:fixed;left:clamp(12px,2.2vw,28px);bottom:clamp(12px,2.2vw,28px);z-index:72;max-width:270px;padding:9px 13px 9px 9px;border:1px solid rgba(217,160,91,.35);border-radius:999px;background:rgba(36,22,16,.94);color:#fff8ee;display:flex;align-items:center;gap:10px;box-shadow:0 16px 45px -18px rgba(36,22,16,.72);backdrop-filter:blur(12px);transform:translateY(22px);opacity:0;visibility:hidden;transition:opacity .45s,transform .55s var(--ease),visibility 0s linear .55s}.dy-sub-beacon.dy-show{opacity:1;visibility:visible;transform:none;transition:opacity .45s,transform .55s var(--ease)}.dy-sub-beacon:hover{transform:translateY(-3px)}.dy-sub-beacon-icon{position:relative;width:37px;height:37px;flex:none;border-radius:50%;display:grid;place-items:center;background:linear-gradient(145deg,#d88155,#9c4522)}.dy-sub-beacon-icon::after{content:"";position:absolute;inset:-4px;border:1px solid rgba(241,179,131,.35);border-radius:50%;animation:dySubPulseRing 2.4s infinite}.dy-sub-beacon-icon svg{width:19px;height:19px;stroke:#fff;fill:none;stroke-width:1.8}.dy-sub-beacon-copy{text-align:left}.dy-sub-beacon-copy b{display:block;font:700 11px/1.2 var(--font-body);letter-spacing:.02em}.dy-sub-beacon-copy span{display:block;margin-top:3px;color:#d8c2ad;font-size:9px}.dy-sub-beacon-x{width:23px;height:23px;margin-left:2px;border-radius:50%;color:#cdb6a0;display:grid;place-items:center;font-size:16px}.dy-sub-beacon-x:hover{background:rgba(255,255,255,.09);color:#fff}
@keyframes dySubDrift{to{transform:translate3d(-25px,22px,0) scale(1.07)}}@keyframes dySubSheen{0%,68%{transform:translateX(-130%)}85%,100%{transform:translateX(130%)}}@keyframes dySubSpin{to{transform:rotate(360deg)}}@keyframes dySubPulse{0%{box-shadow:0 0 0 0 rgba(241,179,131,.55)}70%,100%{box-shadow:0 0 0 12px rgba(241,179,131,0)}}@keyframes dySubPulseRing{0%{transform:scale(.86);opacity:.8}70%,100%{transform:scale(1.25);opacity:0}}@keyframes dySubLine{0%,100%{transform:scaleX(.35);opacity:.45}50%{transform:scaleX(1);opacity:1}}
@media(max-width:900px){.dy-sub-grid{grid-template-columns:1fr}.dy-sub-story{padding:44px clamp(22px,6vw,52px)}.dy-sub-formside{padding:42px clamp(22px,6vw,52px)}.dy-sub-benefits{max-width:none}}
@media(max-width:580px){.dy-sub-zone{padding:42px 11px}.dy-sub-shell{border-radius:23px}.dy-sub-story h2{font-size:clamp(39px,12vw,58px)}.dy-sub-benefits{grid-template-columns:1fr}.dy-sub-benefits li{min-height:0;display:grid;grid-template-columns:30px 1fr;column-gap:8px}.dy-sub-benefits svg{grid-row:1/3;margin:1px 0 0}.dy-sub-benefits span{grid-column:2}.dy-sub-steps{align-items:flex-start}.dy-sub-step{max-width:62px;flex-direction:column;text-align:center}.dy-sub-line{margin-top:12px}.dy-sub-choices{grid-template-columns:1fr}.dy-sub-choice-wide{grid-column:auto}.dy-sub-beacon{max-width:230px}.dy-sub-beacon-copy span{display:none}}
/* Theme-wide visual corrections: brand hierarchy, contact desk and moving article rails. */
.topbar-inner{height:clamp(92px,10vw,112px)!important}
.topbar-title{gap:2px!important;padding:5px 0 13px!important;max-width:calc(100vw - 120px)}
.topbar-title .tb-a{font:800 clamp(32px,4.7vw,50px)/.94 var(--font-display)!important;letter-spacing:.095em!important;white-space:nowrap}
.topbar-title .tb-line{min-height:15px!important}
.topbar-title .tb-b{font:500 clamp(10px,1.25vw,13px)/1.1 var(--font-body)!important;letter-spacing:.08em!important;color:var(--accent-dark)!important}
.topbar-title .tb-caret{height:11px!important}.topbar-title .tb-squig{bottom:-8px!important;width:58px!important}
.kd-sec{width:100%;min-width:0;overflow:hidden}
#kd-articles .kd-row{cursor:grab;scroll-snap-type:none;overscroll-behavior-inline:contain}
#kd-articles .kd-row.kd-grabbing{cursor:grabbing;user-select:none}
#kd-articles .kd-row[data-kd-auto='1']{scrollbar-width:none}
#kd-articles .kd-row[data-kd-auto='1']::-webkit-scrollbar{display:none}
.kd-engage{position:relative;overflow:hidden!important;padding:clamp(30px,5vw,54px)!important;background:radial-gradient(480px 230px at 0 0,rgba(188,91,51,.12),transparent 65%),linear-gradient(145deg,#fffaf0,#f4e1c4)!important}
.kd-engage::before{content:"?";position:absolute;right:-.04em;bottom:-.36em;color:rgba(156,69,34,.055);font:700 clamp(170px,27vw,330px)/1 var(--font-display);pointer-events:none}
.kd-engage h2{font-size:clamp(32px,4.8vw,54px)!important;letter-spacing:-.035em}.kd-engage>p{max-width:760px!important;font-size:clamp(13px,1.5vw,16px)!important}
.kd-eg-row{position:relative;display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px!important;max-width:760px;margin:25px auto 12px!important}
.kd-eg{min-height:96px;padding:18px!important;border-radius:18px!important;display:flex!important;align-items:center;gap:15px;text-align:left;background:rgba(255,253,248,.92)!important;box-shadow:0 13px 32px -28px rgba(36,22,16,.75);font:inherit!important}
.kd-eg-icon{width:52px;height:52px;flex:none;border-radius:15px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-dark)}.kd-eg-icon svg{width:26px;height:26px;stroke:currentColor;fill:none;stroke-width:1.65;stroke-linecap:round;stroke-linejoin:round}
.kd-eg-copy{min-width:0}.kd-eg-copy strong{display:block;color:var(--ink);font:700 17px/1.2 var(--font-display)}.kd-eg-copy small{display:block;margin-top:6px;color:var(--muted);font:500 10px/1.45 var(--font-body);overflow-wrap:anywhere}.kd-eg-arrow{margin-left:auto;color:var(--accent-dark);font-size:22px;transition:transform .25s}.kd-eg:hover .kd-eg-arrow{transform:translateX(4px)}
@media(max-width:560px){.topbar-inner{height:88px!important}.topbar-title{max-width:calc(100vw - 104px)}.topbar-title .tb-a{font-size:27px!important;letter-spacing:.075em!important}.topbar-title .tb-b{font-size:10px!important}.kd-eg-row{grid-template-columns:1fr}.kd-eg{min-height:84px;padding:15px!important}.kd-eg-icon{width:46px;height:46px}.kd-engage{padding:30px 16px!important}}
/* Also honour phone hardware when a mobile browser requests a desktop-width viewport. */
@media(max-device-width:760px){.dy-sub-grid{grid-template-columns:1fr!important}.dy-sub-story,.dy-sub-formside{padding:38px 22px!important}.dy-sub-benefits{grid-template-columns:1fr!important}.topbar-inner{height:88px!important}.topbar-title .tb-a{font-size:27px!important}.topbar-title .tb-b{font-size:10px!important}.kd-eg-row{grid-template-columns:1fr!important}}
@media(prefers-reduced-motion:reduce){.dy-sub-zone::before,.dy-sub-zone::after,.dy-sub-shell::before,.dy-sub-orbit,.dy-sub-live,.dy-sub-line,.dy-sub-beacon-icon::after{animation:none!important}.dy-sub-benefits li,.dy-sub-choice,.dy-sub-submit,.dy-sub-beacon{transition:none!important}}
/* DY_SUBSCRIPTION_CSS_END */'''

HTML = r'''<!-- DY_SUBSCRIPTION_PANEL_START -->
<section aria-labelledby='dySubscribeTitle' class='dy-sub-zone' id='dy-subscribe'>
 <div class='dy-sub-shell'>
  <div class='dy-sub-grid'>
   <div class='dy-sub-story'>
    <span aria-hidden='true' class='dy-sub-orbit'></span>
    <p class='dy-sub-kicker'><span class='dy-sub-live'></span> The Signal Desk &#183; Free to join</p>
    <h2 id='dySubscribeTitle'>The market won&#8217;t wait. <em>Neither should your understanding.</em></h2>
    <p class='dy-sub-lede'>Turn Daily Yield&#8217;s reporting into the rhythm you choose: one calm daily digest, selected priority alerts, or the complete live feed. Get the context before the noise becomes a decision.</p>
    <ul class='dy-sub-benefits'>
     <li><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M4 5.5h16v13H4z'/><path d='m5 7 7 5 7-5'/></svg><b>Inbox clarity</b><span>Confirm once, then choose daily, weekly or individual delivery.</span></li>
     <li><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9'/><path d='M10 20h4'/></svg><b>Priority alerts</b><span>Opt in to browser notifications for the stories you do not want to miss.</span></li>
     <li><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M5 4.5h14v15H5z'/><path d='M8 8h8M8 11.5h8M8 15h5'/></svg><b>You set the pace</b><span>Avoid 25 interruptions: the daily digest is our recommended starting point.</span></li>
    </ul>
   </div>
   <div class='dy-sub-formside'>
    <p class='dy-sub-eyebrow'>Your 60-second setup</p>
    <h3>Make the next important story find you.</h3>
    <p>Enter your email, confirm it, and select how often Daily Yield should arrive. No password is requested here.</p>
    <div aria-label='Subscription steps' class='dy-sub-steps'>
     <span class='dy-sub-step'><i>1</i>Enter</span><span aria-hidden='true' class='dy-sub-line'></span><span class='dy-sub-step'><i>2</i>Confirm</span><span aria-hidden='true' class='dy-sub-line'></span><span class='dy-sub-step'><i>3</i>Choose pace</span>
    </div>
    <form accept-charset='UTF-8' action='https://api.follow.it/subscribe' class='dy-sub-form' method='post' target='_blank'>
     <label class='sr-only' for='dySubscribeEmail'>Email address</label>
     <div class='dy-sub-field'><svg aria-hidden='true' viewBox='0 0 24 24'><rect height='14' rx='2' width='18' x='3' y='5'/><path d='m4.5 7 7.5 5.5L19.5 7'/></svg><input autocomplete='email' id='dySubscribeEmail' inputmode='email' name='email' placeholder='Your best email address' required='required' type='email'/></div>
     <button class='dy-sub-submit' type='submit'>Put Daily Yield in my inbox <svg aria-hidden='true' viewBox='0 0 24 24'><path d='M5 12h14M13 6l6 6-6 6'/></svg></button>
     <p class='dy-sub-consent'>By continuing, you ask <a href='https://follow.it' rel='noopener' target='_blank'>follow.it</a> to process your address and send a confirmation so you can choose delivery. See our <a href='https://dailyyield.blogspot.com/p/privacy-policy.html'>Privacy Policy</a>. You can unsubscribe at any time.</p>
    </form>
    <div class='dy-sub-choices'>
     <a class='dy-sub-choice dy-sub-choice-wide' href='https://follow.it/now' rel='noopener' target='_blank'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9'/><path d='M10 20h4'/></svg><span><b>Choose email, browser alerts or another channel</b><small>Opens the secure delivery-choice flow on follow.it</small></span></a>
     <a class='dy-sub-choice' href='https://www.blogger.com/followers/follow/8911514070006792465' rel='noopener' target='_blank'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M7 4h6a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3v4a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8a4 4 0 0 1 3-4Z'/><path d='M8 9h5M8 15h8'/></svg><span><b>Follow with Google</b><small>Add to Blogger Reading List</small></span></a>
     <a class='dy-sub-choice' href='https://dailyyield.blogspot.com/feeds/posts/default?alt=rss' rel='noopener' target='_blank'><svg aria-hidden='true' viewBox='0 0 24 24'><circle cx='6' cy='18' r='1'/><path d='M5 11a8 8 0 0 1 8 8M5 5a14 14 0 0 1 14 14'/></svg><span><b>Use RSS</b><small>Every Post in your feed reader</small></span></a>
    </div>
    <div class='dy-sub-trust'><span>Free</span><span>Explicit opt-in</span><span>Unsubscribe anytime</span><span>Frequency control</span></div>
   </div>
  </div>
 </div>
</section>
<button aria-controls='dy-subscribe' aria-label='Go to Daily Yield subscription choices' class='dy-sub-beacon' id='dySubscribeBeacon' type='button'><span class='dy-sub-beacon-icon'><svg aria-hidden='true' viewBox='0 0 24 24'><path d='M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9'/><path d='M10 20h4'/></svg></span><span class='dy-sub-beacon-copy'><b>Don&#8217;t miss the signal</b><span>Choose your free delivery rhythm</span></span><span aria-label='Dismiss subscription reminder' class='dy-sub-beacon-x' role='button' tabindex='0'>&#215;</span></button>
<!-- DY_SUBSCRIPTION_PANEL_END -->'''

JS = r'''<!-- DY_SUBSCRIPTION_JS_START -->
<script>//<![CDATA[
(function(){
  'use strict';
  var beacon=document.getElementById('dySubscribeBeacon');
  var panel=document.getElementById('dy-subscribe');
  if(!beacon||!panel){return;}
  var dismiss=beacon.querySelector('.dy-sub-beacon-x');
  var key='dy-sub-reminder-dismissed';
  var hidden=false;
  try{hidden=(Date.now()-Number(localStorage.getItem(key)||0))<1209600000;}catch(e){}
  function show(){if(!hidden&&window.scrollY>Math.min(760,document.documentElement.scrollHeight*.18)){beacon.classList.add('dy-show');}}
  function close(ev){if(ev){ev.preventDefault();ev.stopPropagation();}hidden=true;beacon.classList.remove('dy-show');try{localStorage.setItem(key,String(Date.now()));}catch(e){}}
  beacon.addEventListener('click',function(ev){if(ev.target===dismiss){return;}panel.scrollIntoView({behavior:'smooth',block:'center'});window.setTimeout(function(){var input=document.getElementById('dySubscribeEmail');if(input){input.focus({preventScroll:true});}},850);});
  dismiss.addEventListener('click',close);
  dismiss.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){close(ev);}});
  window.addEventListener('scroll',show,{passive:true});
  window.setTimeout(show,9000);
  if('IntersectionObserver' in window){new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.isIntersecting){beacon.classList.remove('dy-show');}});},{threshold:.18}).observe(panel);}
})();
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
    return re.sub(pattern, replacement, text, flags=re.S)


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
        "legacy_twitter_shares": text.count("twitter.com/intent/tweet"),
        "legacy_linkedin_shares": text.count("linkedin.com/sharing/share-offsite"),
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
        "follow_it_forms": 1,
        "blogger_follow_links": 1,
        "legacy_twitter_shares": 0,
        "legacy_linkedin_shares": 0,
        "all_linkedin_links": 0,
        "popular_featured_images": 1,
        "moving_article_rails": 1,
        "contact_email_cards": 1,
        "contact_page_cards": 1,
        "css_checkmark_escape": 1,
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
