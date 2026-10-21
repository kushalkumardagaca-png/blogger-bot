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
import re
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
/* one track count per group, so no row of the index ends in a hole */
.dxi-grid{display:grid;grid-template-columns:repeat(var(--dxi-cols,4),minmax(min(196px,100%),318px));justify-content:center;gap:13px;list-style:none;margin:0;padding:0}
.dxi-card{position:relative;display:flex;flex-direction:column;gap:9px;min-height:150px;padding:15px 15px 12px;border:1px solid var(--dxi-line);border-radius:15px;
  background:#fff;color:var(--dxi-ink);text-decoration:none;overflow:hidden;transition:transform .22s cubic-bezier(.22,.8,.36,1),border-color .22s ease,box-shadow .22s ease}
.dxi-card::before{content:'';position:absolute;left:14px;right:14px;top:0;height:2px;border-radius:0 0 2px 2px;background:linear-gradient(90deg,var(--dxi-accent),#E3A97F);opacity:0;transition:opacity .22s ease}
.dxi-card:hover,.dxi-card:focus-visible{transform:translateY(-3px);border-color:var(--dxi-accent);box-shadow:0 20px 34px -26px rgba(156,69,34,.7),0 2px 0 rgba(188,91,51,.1);outline:none}
.dxi-card:hover::before,.dxi-card:focus-visible::before,.dxi-card[aria-current]{opacity:1}
.dxi-card:focus-visible{box-shadow:0 0 0 3px rgba(188,91,51,.28),0 20px 34px -26px rgba(156,69,34,.7)}
.dxi-card:active{transform:translateY(-1px)}
.dxi-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.dxi-num{font:800 12px/1 Inter,sans-serif;font-variant-numeric:tabular-nums;letter-spacing:.16em;color:var(--dxi-muted)}
.dxi-ico{display:inline-flex;align-items:center;justify-content:center;width:clamp(44px,4.6vw,52px);height:clamp(44px,4.6vw,52px);
  border-radius:15px;background:var(--dxi-soft);border:1px solid #EFD9C2;flex:0 0 auto}
/* square, centred, never clipped: the glyph fills two thirds of the badge and its own geometry
   decides the box, so an icon drawn wide is not squeezed and one drawn small is not flung off-centre */
.dxi-ico svg{display:block;width:clamp(26px,2.9vw,32px);height:clamp(26px,2.9vw,32px);flex:0 0 auto}
.dxi-ico svg *{fill:none;stroke:var(--dxi-accent-dark);stroke-width:var(--dxi-sw,1.9);stroke-linecap:round;stroke-linejoin:round}
.dxi-name{font:800 14.5px/1.28 Inter,sans-serif;letter-spacing:-.005em;color:var(--dxi-ink)}
.dxi-note2{margin:0;font:500 11.8px/1.45 Inter,sans-serif;color:var(--dxi-muted)}
.dxi-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:auto;padding-top:9px;border-top:1px dashed var(--dxi-line)}
.dxi-open{font:800 9.5px/1 Inter,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--dxi-accent-dark)}
.dxi-arrow{font:800 13px/1 Inter,sans-serif;color:var(--dxi-accent);transition:transform .22s cubic-bezier(.22,.8,.36,1)}
.dxi-card:hover .dxi-arrow,.dxi-card:focus-visible .dxi-arrow{transform:translateX(4px)}
.dxi-card[aria-current="true"]{border-color:var(--dxi-accent);background:linear-gradient(180deg,#FFF8F1,#FDF0E4)}
@media (max-width:900px){
  .dxi-note{position:static;display:block;margin:10px 0 0;max-width:none;transform:none}
  .dxi-grid{grid-template-columns:repeat(var(--dxi-cols-mid,3),minmax(min(168px,100%),300px))}
}
@media (max-width:560px){
  .dxi{padding:16px 14px;border-radius:18px}
  .dxi::before{border-radius:18px 0 0 18px}
  .dxi-ghead{flex-wrap:wrap;gap:8px}
  .dxi-gname{white-space:normal}
  .dxi-gline{display:none}
  .dxi-grid{grid-template-columns:repeat(auto-fit,minmax(146px,1fr));gap:11px}
  .dxi-grid[data-odd="1"] .dxi-card:last-child{grid-column:1/-1}
  .dxi-card{min-height:140px;padding:12px 12px 10px}
  .dxi-ico{width:44px;height:44px}
  .dxi-ico svg{width:27px;height:27px}
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


# ---------------------------------------------------------------- icons and layout
# The index once lived under a stylesheet that positioned `.kc-iic` absolutely in the top-right
# corner of its card. Blogger keeps that stylesheet on the page, and the icons were copied across
# with their old class still on them, so every glyph on the new board was being placed by the dead
# rule: out of its badge, at 31x28, with the theme's own stroke. `fit_icon()` rebuilds the tag from
# the drawing alone, so nothing outside this board can move it, and squares the box around the art so
# every icon sits centred at the same visual size.
_ICON_STRIP = re.compile(r"^<svg\b[^>]*>|</svg>\s*$", re.I)
_PAIR = re.compile(r"(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")
_NUM = r"-?\d*\.?\d+(?:[eE][-+]?\d+)?"


def _attrs(chunk: str) -> dict:
    return {k.lower(): v for k, v in re.findall(r'([\w:-]+)\s*=\s*"([^"]*)"', chunk)}


def _path_points(d: str) -> list[tuple[float, float]]:
    """Anchor points of an SVG path: where the pen lands, not its control arms.

    Control points of a curve are pulled outside the drawn line on purpose, so using them to size a
    box would shrink the visible glyph. A lowercase command is an offset from the point the pen has
    already reached - `c3 3.4 3 11.6 0 15` ends fifteen units below where it started, not at 15 -
    which is why this walks the path instead of reading its numbers as coordinates.
    """
    points: list[tuple[float, float]] = []
    x = y = 0.0
    start = (0.0, 0.0)
    steps = {"M": 2, "L": 2, "T": 2, "Q": 4, "S": 4, "C": 6, "A": 7, "H": 1, "V": 1}
    for command, argument in re.findall(rf"([MmLlHhVvCcSsQqTtAaZz])((?:{_NUM}[\s,]*)*)", d):
        numbers = [float(n) for n in _PAIR.findall(argument)]
        relative = command.islower()
        key = command.upper()
        if key == "Z":
            x, y = start
            points.append((x, y))
            continue
        step, i = steps[key], 0
        while i + step <= len(numbers):
            window = numbers[i:i + step]
            if key == "H":
                x = x + window[0] if relative else window[0]
            elif key == "V":
                y = y + window[0] if relative else window[0]
            else:
                tail = (window[5], window[6]) if key == "A" else (window[-2], window[-1])
                dx, dy = tail
                x, y = (x + dx, y + dy) if relative else (dx, dy)
            if key == "M" and i == 0:
                start = (x, y)
            points.append((x, y))
            i += step
    return points


def icon_points(markup: str) -> list[tuple[float, float]]:
    """Every point the glyph actually draws, whatever shape it is built from."""
    points: list[tuple[float, float]] = []
    for tag in ("circle", "ellipse"):
        for chunk in re.findall(rf"<{tag}\b[^>]*>", markup, re.I):
            a = _attrs(chunk)
            cx, cy = float(a.get("cx", 0)), float(a.get("cy", 0))
            rx = float(a.get("r") or a.get("rx") or 0)
            ry = float(a.get("r") or a.get("ry") or rx)
            points += [(cx - rx, cy - ry), (cx + rx, cy + ry)]
    for chunk in re.findall(r"<rect\b[^>]*>", markup, re.I):
        a = _attrs(chunk)
        x, y = float(a.get("x", 0)), float(a.get("y", 0))
        points += [(x, y), (x + float(a.get("width", 0)), y + float(a.get("height", 0)))]
    for chunk in re.findall(r"<line\b[^>]*>", markup, re.I):
        a = _attrs(chunk)
        points += [(float(a.get("x1", 0)), float(a.get("y1", 0))), (float(a.get("x2", 0)), float(a.get("y2", 0)))]
    for chunk in re.findall(r"<poly(?:line|gon)\b[^>]*>", markup, re.I):
        numbers = [float(n) for n in _PAIR.findall(_attrs(chunk).get("points", ""))]
        points += list(zip(numbers[0::2], numbers[1::2]))
    for chunk in re.findall(r"<path\b[^>]*>", markup, re.I):
        points += _path_points(_attrs(chunk).get("d", ""))
    return points


def drawing(svg: str) -> str:
    """The part of an icon that must survive: its drawing data, whitespace aside.

    `fit_icon()` rebuilds the tag around a glyph, so comparing whole tags would report a loss on every
    icon that was merely improved. This compares the artwork itself, which is what the reader sees.
    """
    return re.sub(r"\s+", " ", _ICON_STRIP.sub("", svg or "")).strip()


def fit_icon(svg: str) -> str:
    """Rebuild one icon tag so it renders square, centred, and immune to the page's old rules.

    The drawing data is kept byte for byte; only the wrapper is rebuilt. A glyph whose art escapes a
    sane frame, or one with nothing to measure, keeps the view box it arrived with, squared, rather
    than being cropped by a guess.
    """
    if not svg:
        return ""
    inner = _ICON_STRIP.sub("", svg).strip()
    if not inner:
        return ""
    points = icon_points(inner)
    stroke = 1.9
    box = None
    original = re.search(rf'viewBox\s*=\s*"\s*({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})', svg, re.I)
    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        pad = stroke / 2 + 0.8
        side = max(max(xs) - min(xs), max(ys) - min(ys)) + 2 * pad
        if 6 <= side <= 46:
            box = ((min(xs) + max(xs)) / 2 - side / 2, (min(ys) + max(ys)) / 2 - side / 2, side)
            stroke = round(1.9 * side / 24, 2)  # same apparent weight whatever the box measures
    if box is None and original:
        x, y, w, h = (float(value) for value in original.groups())
        side = max(w, h)
        box = (x + w / 2 - side / 2, y + h / 2 - side / 2, side)
    if box is None:
        box = (0, 0, 24)
    left, top, side = box
    return (f'<svg viewBox="{left:.3g} {top:.3g} {side:.3g} {side:.3g}" preserveAspectRatio="xMidYMid meet"'
            f' aria-hidden="true" focusable="false" style="--dxi-sw:{stroke:g}">{inner}</svg>')


def grid_open(count: int) -> str:
    """The opening tag of one group's grid, carrying the column counts it asked for."""
    wide, mid = layout_for(count)
    odd = ' data-odd="1"' if count % 2 else ""
    return f'<div class="dxi-grid"{odd} style="--dxi-cols:{wide};--dxi-cols-mid:{mid}">'


def layout_for(count: int) -> tuple[int, int]:
    """How many columns a group of `count` cards should use, wide and mid width.

    `auto-fit` fills as many tracks as the container allows and leaves the last row short: five cards
    at four columns is a row of four and a row of one, and three cards at five columns is a row with a
    hole in it. That ragged bottom edge is what made the index look unfinished. Each group is now given
    its own column count, chosen to use as few rows as possible, then to leave as few empty places as
    possible, and only then to be as wide as it can be - so five sit in one row of five, six in two
    rows of three, and a lone card is centred instead of stranded at the left.
    """
    def best(candidates: tuple[int, ...]) -> int:
        scored = []
        for columns in candidates:
            if columns > max(1, count):
                continue
            rows = -(-count // columns)
            holes = (columns - count % columns) % columns
            scored.append(((rows, holes, -columns), columns))
        return min(scored)[1] if scored else 1

    # four tracks is the widest counted here: five of them would need more room than the
    # narrowest desktop column offers, and a grid that overflows its own page is worse than a
    # row with one place left over.
    return best((4, 3, 2, 1)), best((3, 2, 1))


WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
         "nineteen", "twenty", "twenty-one", "twenty-two", "twenty-three", "twenty-four",
         "twenty-five", "twenty-six", "twenty-seven", "twenty-eight", "twenty-nine", "thirty")


def count_word(total: int) -> str:
    """The number a sentence may claim, in the same voice as the rest of it."""
    return WORDS[total] if 0 <= total < len(WORDS) else str(total)


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
             icon=fit_icon(item.get("icon") or ""), title=html.escape(item.get("title") or ""),
             desc=html.escape(item.get("desc") or ""), open=html.escape(open_label))


def render(board: dict, labels: dict | None = None, css: bool = True) -> str:
    """Render one desk index board.

    ``board`` keeps the shape produced by the page survey:
    ``{"aria":..., "eyebrow":..., "title":..., "note":..., "chips":[...],
       "groups":[{"name":..., "items":[...]}], "labels":{...}}``
    """
    labels = {**(board.get("labels") or {}), **(labels or {})}
    total = sum(len(group["items"]) for group in board["groups"])
    note = board.get("note") or ""
    if "{total}" in note:
        # the handwritten line used to assert a number the file had memorised: eleven tools, seven
        # desks, fourteen calculators. Cards are added to these pages, so the claim went stale on all
        # three at once and contradicted the count beside it. The sentence is still written by hand;
        # only its number is now read from the board it describes.
        note = note.replace("{total}", count_word(total))
    chips = board.get("chips") or []
    chip_html = "".join(f'<span class="dxi-chip">{chip}</span>' for chip in chips)
    chip_html += f'<span class="dxi-chip dxi-chip--tip"><b>{total}</b> desks</span>'
    parts = [CSS if css else "", SCRIPT,
             f'<nav class="dxi" aria-label="{html.escape(board.get("aria") or "Desk index", quote=True)}">',
             '<header class="dxi-head">',
             f'<p class="dxi-eyebrow">{html.escape(board.get("eyebrow") or "Desk index")}</p>',
             f'<h2 class="dxi-title">{html.escape(board.get("title") or "Pick a desk")}</h2>',
             f'<p class="dxi-note">{html.escape(note)}</p>',
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
            grid_open(len(group["items"])),
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
