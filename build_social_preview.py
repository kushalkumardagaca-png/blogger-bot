#!/usr/bin/env python3
from pathlib import Path
import base64, html
from social_creative import build_caption, creative_meta, render_social_card, tumblr_payload

OUT=Path("social_creative_preview"); OUT.mkdir(exist_ok=True)
stories=[
("Markets are up. Your risk tolerance did not get the memo.",["Markets"],"A practical look at what changed, what did not, and the risk questions worth asking before the next trade."),
("Credit card APR: the tiny number with a very long shadow",["Debt"],"Minimum payments can hide the true timeline. Here is the repayment math and the trade-offs to compare."),
("Inflation cooled. Why does your grocery bill still feel loud?",["Economy"],"Headline inflation and household costs can move differently. The useful context sits inside the basket."),
("The no-drama emergency fund reset",["Personal Finance"],"A flexible framework for rebuilding a cash buffer without pretending every month looks the same."),
("Gold is moving. Here is what the chart cannot tell you.",["Markets"],"Price momentum is one signal, not a complete decision. Rates, currency moves and time horizon still matter."),
("Tax records future-you will be glad you kept",["Tax"],"A plain-English checklist for organizing records and asking better questions before filing."),
("A rate cut is not a personality trait",["Economy"],"What lower policy rates can—and cannot—change for borrowers, savers and market expectations."),
("The five-minute budget check that respects real life",["Personal Finance"],"A quick review built around priorities, recurring costs and the next realistic adjustment."),
]
platforms=["facebook","bluesky","tumblr","mastodon"]*2
cards=[]
for n,((title,labels,summary),platform) in enumerate(zip(stories,platforms),1):
 item={"id":str(n),"kind":"post","url":f"https://dailyyield.blogspot.com/2026/10/sample-story-{n}.html","title":title,"labels":labels,"content":f"<p>{summary}</p>"}
 path=OUT/f"{n:02d}-{platform}.jpg"; render_social_card(item,platform,path,summary,"JPEG")
 if platform=="tumblr":
  caption="\n".join(b.get("text",b.get("title","")) for b in tumblr_payload(item,summary)["content"] if b["type"] in ("text","link"))
 else: caption=build_caption(item,platform,summary)
 data=base64.b64encode(path.read_bytes()).decode(); meta=creative_meta(item,platform)
 cards.append(f'<article><img src="data:image/jpeg;base64,{data}" alt="{html.escape(title)}"><div class="pad"><div class="eyebrow">{platform.upper()} · PHOTO EDITION · layout {meta["layout"]+1}</div><h2>{html.escape(title)}</h2><pre>{html.escape(caption)}</pre></div></article>')
page=f'''<!doctype html><html><head><meta charset="utf-8"><title>Daily Yield Photo-First Social System</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#101522;color:#f7f4ea;font:16px/1.5 Arial,sans-serif}}header{{max-width:1240px;margin:auto;padding:64px 24px 35px}}h1{{font-size:clamp(42px,8vw,92px);line-height:.88;margin:0;letter-spacing:-5px}}header p{{max-width:790px;color:#bdc7d9;font-size:19px}}.stamp{{display:inline-block;background:#d8ff49;color:#101522;padding:8px 12px;border-radius:99px;font-weight:800;margin-bottom:20px}}main{{max-width:1240px;margin:auto;padding:0 24px 70px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}}article{{background:#f8f2e7;color:#151515;border-radius:24px;overflow:hidden;box-shadow:0 18px 60px #0006}}img{{display:block;width:100%;aspect-ratio:1200/630;object-fit:cover}}.pad{{padding:24px}}.eyebrow{{color:#7b2cff;font-weight:800;font-size:12px;letter-spacing:1.5px}}h2{{font-size:25px;line-height:1.05;margin:10px 0 18px}}pre{{white-space:pre-wrap;font:14px/1.5 Arial,sans-serif;border-top:2px solid #111;padding-top:16px;margin:0;color:#303030}}@media(max-width:800px){{main{{grid-template-columns:1fr}}h1{{letter-spacing:-2px}}}}</style></head><body><header><span class="stamp">PHOTO-FIRST CREATIVE SYSTEM 3.0</span><h1>Article photos.<br>Social energy.</h1><p>Every post now leads with full-bleed editorial photography—the authenticated article hero whenever available—with only a restrained magazine-style headline, masthead and credit overlay. No banners, panels, grids, stickers or PowerPoint-style cards.</p></header><main>{''.join(cards)}</main></body></html>'''
(OUT/"index.html").write_text(page)
for image in OUT.glob("*.jpg"): image.unlink()
print(OUT/"index.html")
