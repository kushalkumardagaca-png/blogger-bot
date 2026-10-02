#!/usr/bin/env python3
from pathlib import Path
import base64, html
from social_creative import build_caption, creative_meta, render_social_card, tumblr_payload

OUT=Path("social_creative_preview"); OUT.mkdir(exist_ok=True)
stories=[
("How to negotiate your next salary without the awkward spiral",["Career"],"A practical script for discussing value, timing and the number you actually want."),
("What a bank rate change means for your next money move",["Banking"],"Borrowers and savers can experience the same rate decision very differently."),
("The real cost of adopting a dog—and why it can still be worth it",["Personal Finance"],"A realistic look at food, care, insurance and the joy that never fits a spreadsheet."),
("Rent or buy a home? Start with the life you actually want",["Housing"],"The strongest answer combines cash flow, flexibility, location and time horizon."),
("Build the travel fund before you build the itinerary",["Travel"],"A low-drama way to save for a trip without putting the return journey on a credit card."),
("Why the grocery shop still feels expensive",["Economy"],"Headline inflation and household costs can move differently. The useful context sits inside the basket."),
("The global market mood in one useful scroll",["Markets"],"A clear view of what moved across regions and which signals still need context."),
("The fintech app is cute. Read the permissions.",["Technology"],"Convenience matters, but so do fees, data access and the safety net behind the interface."),
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
page=f'''<!doctype html><html><head><meta charset="utf-8"><title>Daily Yield Photo-First Social System</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#101522;color:#f7f4ea;font:16px/1.5 Arial,sans-serif}}header{{max-width:1240px;margin:auto;padding:64px 24px 35px}}h1{{font-size:clamp(42px,8vw,92px);line-height:.88;margin:0;letter-spacing:-5px}}header p{{max-width:790px;color:#bdc7d9;font-size:19px}}.stamp{{display:inline-block;background:#d8ff49;color:#101522;padding:8px 12px;border-radius:99px;font-weight:800;margin-bottom:20px}}main{{max-width:1240px;margin:auto;padding:0 24px 70px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}}article{{background:#f8f2e7;color:#151515;border-radius:24px;overflow:hidden;box-shadow:0 18px 60px #0006}}img{{display:block;width:100%;aspect-ratio:1200/630;object-fit:cover}}.pad{{padding:24px}}.eyebrow{{color:#7b2cff;font-weight:800;font-size:12px;letter-spacing:1.5px}}h2{{font-size:25px;line-height:1.05;margin:10px 0 18px}}pre{{white-space:pre-wrap;font:14px/1.5 Arial,sans-serif;border-top:2px solid #111;padding-top:16px;margin:0;color:#303030}}@media(max-width:800px){{main{{grid-template-columns:1fr}}h1{{letter-spacing:-2px}}}}</style></head><body><header><span class="stamp">GLOBAL GEN-Z PHOTO SYSTEM 4.0</span><h1>Real life.<br>Money context.</h1><p>A bright global visual mix of young people, families, pets, homes, banks, work, technology, shopping, travel and cities. Photography stays dominant; the Daily Yield identity and headline remain compact, vivid and social-native.</p></header><main>{''.join(cards)}</main></body></html>'''
(OUT/"index.html").write_text(page)
for image in OUT.glob("*.jpg"): image.unlink()
print(OUT/"index.html")
