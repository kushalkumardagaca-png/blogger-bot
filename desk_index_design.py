#!/usr/bin/env python3
"""Daily Yield desk-index design system.

One renderer builds the tool index shown at the top of the Interactive pages
(Boardroom tools, Markets desk, Calculators). The same function produces the
preview file and the markup that is written back to Blogger, so what is reviewed
is exactly what is published.

Design rules
------------
* the group heading no longer competes with the tool cards: each group owns a
  full-width row with a numbered badge, its name and a count;
* every card carries the same anatomy, so the grid stays optically even:
  number, icon badge, name, plain-language note and a single call to action;
* the palette, serif display face and handwritten accent all come from the
  existing Daily Yield identity, so the block still belongs to the site;
* keyboard focus, reduced motion and small screens are handled explicitly.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

SCOPE = "dxi"
CSS = """<style id="dyDeskIndexStyle">
/* Daily Yield desk index — one designed board, three desks. */
.dxi{--dxi-ink:#241610;--dxi-muted:#7A6A57;--dxi-line:#E7D8C4;--dxi-soft:#F7E6D5;--dxi-accent:#BC5B33;--dxi-accent-dark:#9C4522;--dxi-paper:#FFFDF9;
  position:relative;margin:34px 0 0;padding:clamp(18px,3.4vw,30px);border:1px solid var(--dxi-line);border-radius:22px;
  background:linear-gradient(180deg,var(--dxi-paper) 0%,#FBF2E6 100%);box-shadow:0 26px 50px -34px rgba(36,22,16,.45);color:var(--dxi-ink);
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;box-sizing:border-box}
.dxi *,.dxi *::before,.dxi *::after{box-sizing:inherit}
.dxi::before{content:'';position:absolute;inset:0 auto 0 0;width:5px;border-radius:22px 0 0 22px;background:linear-gradient(180deg,var(--dxi-accent) 0%,#D98B5F 48%,#E8C49B 100%)}
.dxi-head{position:relative;padding:0 0 16px;margin:0 0 22px;border-bottom:1px solid var(--dxi-line)}
.dxi-eyebrow{margin:0;font:800 10px/1 Inter,sans-serif;letter-spacing:.26em;text-transform:uppercase;color:var(--dxi-accent-dark)}
.dxi-title{margin:10px 0 0;font:800 clamp(23px,3.5vw,34px)/1.12 Georgia,"Playfair Display",serif;letter-spacing:-.01em;color:var(--dxi-ink)}
.dxi-note{position:absolute;right:0;bottom:16px;margin:0;font:600 clamp(15px,1.7vw,19px)/1.2 Caveat,"Segoe Script",cursive;color:var(--dxi-accent);transform:rotate(-1.4deg);max-width:46%}
.dxi-meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 0 0}
.dxi-chip{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border:1px solid var(--dxi-line);border-radius:999px;background:#fff;
  font:700 10px/1 Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--dxi-muted)}
.dxi-chip b{color:var(--dxi-accent-dark);font-weight:800}
.dxi-chip--tip{border-style:dashed;color:var(--dxi-accent-dark);background:var(--dxi-soft)}
.dxi-group{margin:0 0 26px}
.dxi-group:last-child{margin-bottom:2px}
.dxi-ghead{display:flex;align-items:center;gap:12px;margin:0 0 13px}
.dxi-gnum{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9px;background:var(--dxi-ink);color:#FFF6EC;
  font:800 11.5px/1 Inter,sans-serif;font-variant-numeric:tabular-nums;letter-spacing:.02em;flex:0 0 30px}
.dxi-gname{margin:0;font:800 11.5px/1.1 Inter,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--dxi-ink);white-space:nowrap}
.dxi-gcount{font:700 10px/1 Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--dxi-accent-dark);background:var(--dxi-soft);
  border-radius:999px;padding:4px 9px;white-space:nowrap}
.dxi-gline{flex:1 1 40px;height:1px;min-width:18px;background:linear-gradient(90deg,var(--dxi-line),rgba(231,216,196,0))}
.dxi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(196px,1fr));gap:13px;list-style:none;margin:0;padding:0}
.dxi-card{position:relative;display:flex;flex-direction:column;gap:9px;min-height:142px;padding:14px 14px 12px;border:1px solid var(--dxi-line);border-radius:15px;
  background:#fff;color:var(--dxi-ink);text-decoration:none;overflow:hidden;transition:transform .22s cubic-bezier(.22,.8,.36,1),border-color .22s ease,box-shadow .22s ease}
.dxi-card::before{content:'';position:absolute;left:14px;right:14px;top:0;height:2px;border-radius:0 0 2px 2px;background:linear-gradient(90deg,var(--dxi-accent),#E3A97F);opacity:0;transition:opacity .22s ease}
.dxi-card:hover,.dxi-card:focus-visible{transform:translateY(-3px);border-color:var(--dxi-accent);box-shadow:0 20px 34px -26px rgba(156,69,34,.7),0 2px 0 rgba(188,91,51,.1);outline:none}
.dxi-card:hover::before,.dxi-card:focus-visible::before,.dxi-card[aria-current]{opacity:1}
.dxi-card:focus-visible{box-shadow:0 0 0 3px rgba(188,91,51,.28),0 20px 34px -26px rgba(156,69,34,.7)}
.dxi-card:active{transform:translateY(-1px)}
.dxi-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.dxi-num{font:800 12px/1 Inter,sans-serif;font-variant-numeric:tabular-nums;letter-spacing:.16em;color:var(--dxi-muted)}
.dxi-ico{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:11px;background:var(--dxi-soft);border:1px solid #EFD9C2;flex:0 0 36px}
.dxi-ico svg{width:21px;height:19px;overflow:visible}
.dxi-ico svg path,.dxi-ico svg circle,.dxi-ico svg ellipse,.dxi-ico svg rect,.dxi-ico svg polygon{fill:none;stroke:var(--dxi-accent-dark);stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.dxi-name{font:800 14.5px/1.28 Inter,sans-serif;letter-spacing:-.005em;color:var(--dxi-ink)}
.dxi-note2{margin:0;font:500 11.8px/1.45 Inter,sans-serif;color:var(--dxi-muted)}
.dxi-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:auto;padding-top:9px;border-top:1px dashed var(--dxi-line)}
.dxi-open{font:800 9.5px/1 Inter,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--dxi-accent-dark)}
.dxi-arrow{font:800 13px/1 Inter,sans-serif;color:var(--dxi-accent);transition:transform .22s cubic-bezier(.22,.8,.36,1)}
.dxi-card:hover .dxi-arrow,.dxi-card:focus-visible .dxi-arrow{transform:translateX(4px)}
.dxi-card[aria-current="true"]{border-color:var(--dxi-accent);background:linear-gradient(180deg,#FFF8F1,#FDF0E4)}
@media (max-width:900px){
  .dxi-note{position:static;display:block;margin:10px 0 0;max-width:none;transform:none}
  .dxi-grid{grid-template-columns:repeat(auto-fit,minmax(168px,1fr))}
}
@media (max-width:560px){
  .dxi{padding:16px 14px;border-radius:18px}
  .dxi::before{border-radius:18px 0 0 18px}
  .dxi-ghead{flex-wrap:wrap;gap:8px}
  .dxi-gname{white-space:normal}
  .dxi-gline{display:none}
  .dxi-grid{grid-template-columns:repeat(auto-fit,minmax(146px,1fr));gap:11px}
  .dxi-card{min-height:132px;padding:12px 12px 10px}
  .dxi-name{font-size:13.5px}
}
@media (prefers-reduced-motion:reduce){
  .dxi-card,.dxi-arrow{transition:none}
  .dxi-card:hover{transform:none}
}
</style>"""
SCRIPT = """<script data-dy-desk-index="1">(function(){var d=document,n=d.querySelector('.dxi');if(!n||n.dataset.dyIndexReady)return;n.dataset.dyIndexReady='1';
var reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches,cards=[].slice.call(n.querySelectorAll('.dxi-card'));
function target(a){var h=a.getAttribute('href')||'';return h.charAt(0)==='#'?d.getElementById(h.slice(1)):null}
cards.forEach(function(a){a.addEventListener('click',function(ev){var t=target(a);if(!t||ev.metaKey||ev.ctrlKey||ev.shiftKey)return;ev.preventDefault();
t.scrollIntoView({behavior:reduce?'auto':'smooth',block:'start'});if(history.replaceState)history.replaceState(null,'',a.getAttribute('href'));
cards.forEach(function(x){x.removeAttribute('aria-current')});a.setAttribute('aria-current','true')})});
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(!e.isIntersecting)return;
cards.forEach(function(x){if(target(x)===e.target)x.setAttribute('aria-current','true')})})},{rootMargin:'-45% 0px -50% 0px'});
cards.forEach(function(a){var t=target(a);if(t)io.observe(t)})}})();</script>"""


def card(item: dict, index_labels: dict) -> str:
    open_label = index_labels.get("open", "Open desk")
    return (
        '<a class="dxi-card" href="{href}">'
        '<span class="dxi-top"><span class="dxi-num">{num}</span><span class="dxi-ico">{icon}</span></span>'
        '<strong class="dxi-name">{title}</strong>'
        '<span class="dxi-note2">{desc}</span>'
        '<span class="dxi-foot"><span class="dxi-open">{open}</span><span class="dxi-arrow" aria-hidden="true">&#8594;</span></span>'
        '</a>'
    ).format(href=html.escape(item["href"], quote=True), num=html.escape(item.get("num") or ""),
             icon=item.get("icon") or "", title=html.escape(item.get("title") or ""),
             desc=html.escape(item.get("desc") or ""), open=html.escape(open_label))


def render(board: dict, labels: dict | None = None, css: bool = True) -> str:
    """Render one desk index board.

    ``board`` keeps the shape produced by the page survey:
    ``{"aria":..., "eyebrow":..., "title":..., "note":..., "chips":[...],
       "groups":[{"name":..., "items":[...]}], "labels":{...}}``
    """
    labels = {**(board.get("labels") or {}), **(labels or {})}
    total = sum(len(group["items"]) for group in board["groups"])
    chips = board.get("chips") or []
    chip_html = "".join(f'<span class="dxi-chip">{chip}</span>' for chip in chips)
    chip_html += f'<span class="dxi-chip dxi-chip--tip"><b>{total}</b> desks</span>'
    parts = [CSS if css else "", SCRIPT,
             f'<nav class="dxi" aria-label="{html.escape(board.get("aria") or "Desk index", quote=True)}">',
             '<header class="dxi-head">',
             f'<p class="dxi-eyebrow">{html.escape(board.get("eyebrow") or "Desk index")}</p>',
             f'<h2 class="dxi-title">{html.escape(board.get("title") or "Pick a desk")}</h2>',
             f'<p class="dxi-note">{html.escape(board.get("note") or "")}</p>',
             f'<div class="dxi-meta">{chip_html}</div>',
             '</header>', '<div class="dxi-body">']
    for number, group in enumerate(board["groups"], 1):
        count = len(group["items"])
        parts += [
            '<section class="dxi-group">',
            '<header class="dxi-ghead">',
            f'<span class="dxi-gnum">{number:02d}</span>',
            f'<h3 class="dxi-gname">{html.escape(group["name"])}</h3>',
            f'<span class="dxi-gcount">{count} {"desk" if count == 1 else "desks"}</span>',
            '<span class="dxi-gline" aria-hidden="true"></span>',
            '</header>',
            '<div class="dxi-grid">',
            "".join(card(item, labels) for item in group["items"]),
            '</div>', '</section>',
        ]
    parts += ['</div>', '</nav>']
    return "".join(parts)


def preview_boards(path: Path) -> str:
    """Build a single self-contained preview file for the three redesigned desks."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sections = []
    for key in ("corporate", "snapshot", "calculator"):
        sections.append(f'<h1 class="pv-title">{html.escape(data[key]["page"])}</h1>')
        sections.append(render(data[key]["board"], css=False))
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily Yield — desk index redesign preview</title>
<style>
body{margin:0;padding:28px clamp(14px,4vw,54px) 80px;background:#F8F1E6;color:#241610;
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.pv-wrap{max-width:1180px;margin:0 auto}
.pv-note{max-width:820px;margin:0 0 26px;font:500 14px/1.7 Inter,sans-serif;color:#6E5D4B}
.pv-title{margin:44px 0 0;font:800 clamp(15px,2vw,20px)/1.2 Inter,sans-serif;letter-spacing:.18em;text-transform:uppercase;color:#9C4522}
.pv-title:first-of-type{margin-top:18px}
</style>%s
</head><body><div class="pv-wrap">
<p class="pv-note">The same board, three desks: the group heading now owns a full row, every card follows one anatomy,
and the grid keeps an even rhythm at every screen width. Colours, serif display face and the handwritten note come
from the existing Daily Yield identity.</p>
%s
</div></body></html>""" % (CSS, "".join(sections))


if __name__ == "__main__":
    import sys
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "desk_index_data.json")
    target = Path(sys.argv[2] if len(sys.argv) > 2 else "preview.html")
    target.write_text(preview_boards(source), encoding="utf-8")
    print(target)
