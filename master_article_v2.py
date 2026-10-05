#!/usr/bin/env python3
"""Strict compiler for the from-scratch Daily Yield master-article standard."""
from __future__ import annotations
import html, json, math, re
from urllib.parse import urlparse
from page_family import family_block
from social_identity import SOCIAL_PROFILES

BLOG="https://dailyyield.blogspot.com"
AUTHOR="Kushal K. Daga"
MASTER_V2_VERSION="2.0"
CORE_MIN,CORE_MAX=4000,4200
SUMMARY_MIN,SUMMARY_MAX=600,800


def words(value):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9’'\-]*",re.sub(r"<[^>]+>"," ",value or "")))

def slugify(value): return re.sub(r"[^a-z0-9]+","-",value.casefold()).strip("-")
def esc(value): return html.escape(str(value),quote=True)

def validate(package):
    errors=[];title=str(package.get("title","")).strip()
    if not 12<=len(title)<=46: errors.append("title must be short and 12–46 characters")
    if re.search(r"\b(?:19|20)\d{2}\b|\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",title,re.I): errors.append("master title contains a date")
    sections=package.get("sections") or []
    headings=[str(x.get("heading","")).strip().casefold() for x in sections]
    if not 7<=len(sections)<=14: errors.append("main article needs 7–14 topic-specific sections")
    if len(headings)!=len(set(headings)): errors.append("duplicate main headings")
    core=" ".join(" ".join(x.get("paragraphs") or []) for x in sections)
    count=words(core)
    if not CORE_MIN<=count<=CORE_MAX: errors.append(f"main article is {count} words; required {CORE_MIN}–{CORE_MAX}")
    summary=package.get("summary") or []
    summary_count=words(" ".join(summary))
    if not SUMMARY_MIN<=summary_count<=SUMMARY_MAX: errors.append(f"summary is {summary_count} words; required {SUMMARY_MIN}–{SUMMARY_MAX}")
    photos=package.get("photos") or []
    if len(photos)!=3: errors.append("exactly three distinct editorial photos are required")
    if len({x.get("url") for x in photos})!=3: errors.append("editorial photos are not distinct")
    for index,p in enumerate(photos,1):
        if not p.get("url") or not p.get("alt") or not p.get("caption"): errors.append(f"photo {index} metadata incomplete")
        if float(p.get("width",0) or 0)<=float(p.get("height",1) or 1): errors.append(f"photo {index} is not landscape")
    visuals=package.get("visuals") or []
    if len(visuals)<3: errors.append("at least three evidence-based data representations are required")
    for index,v in enumerate(visuals,1):
        rows=v.get("data") or []
        if rows and str(v.get("type","table")).casefold()=="table":
            if len(rows)<2 or not all(isinstance(row,dict) and len(row)>=2 for row in rows):errors.append(f"data visual {index} has malformed table rows")
        else:
            labels=v.get("labels") or []; values=v.get("values") or v.get("numeric_values") or []
            if not labels or len(labels)!=len(values): errors.append(f"data visual {index} has mismatched labels and values")
            else:
                try:[float(x) for x in values]
                except (TypeError,ValueError):errors.append(f"data visual {index} contains a non-numeric value")
        if not v.get("title") or not v.get("caption") or not (v.get("source") or v.get("source_number")):errors.append(f"data visual {index} attribution metadata incomplete")
    sources=package.get("sources") or []
    if len(sources)<6: errors.append("at least six topic-specific sources are required")
    for index,s in enumerate(sources,1):
        if not str(s.get("url","")).startswith("https://") or not s.get("name") or not s.get("title"): errors.append(f"source {index} incomplete")
    if len(package.get("faq") or [])<5: errors.append("at least five topic-specific FAQs are required")
    if len(package.get("glossary") or [])<8: errors.append("at least eight topic-specific glossary definitions are required")
    low=package.get("low_view_posts") or []
    if not 10<=len(low)<=15: errors.append("low-view shelf requires 10–15 genuinely measured Posts")
    if errors: raise ValueError("MASTER V2 REJECTED — "+"; ".join(errors))
    return {"core_words":count,"summary_words":summary_count}

def linked_text(text,sources,internals):
    refs={f"S{i+1}":x for i,x in enumerate(sources)}|{f"I{i+1}":x for i,x in enumerate(internals)}
    out=[];pos=0
    for m in re.finditer(r"\[\[([SI]\d+)\|([^\]]+)\]\]",text or ""):
        out.append(esc(text[pos:m.start()]));ref=refs.get(m.group(1));anchor=m.group(2)
        if ref: out.append(f'<a href="{esc(ref["url"])}" rel="noopener" target="_blank">{esc(anchor)}</a>' if m.group(1).startswith("S") else f'<a href="{esc(ref["url"])}">{esc(anchor)}</a>')
        else: out.append(esc(anchor))
        pos=m.end()
    out.append(esc((text or "")[pos:]));return "".join(out)

def photo(p,index):
    credit=esc(p['caption'])
    if p.get('source_page'): credit=f'<a href="{esc(p["source_page"])}" rel="noopener" target="_blank">{credit}</a>'
    if p.get('license_url'): credit+=f' · <a href="{esc(p["license_url"])}" rel="license noopener" target="_blank">Licence</a>'
    return f'''<figure class="dy2-photo"><img src="{esc(p['url'])}" alt="{esc(p['alt'])}" width="{int(p['width'])}" height="{int(p['height'])}" loading="{'eager' if index==1 else 'lazy'}" decoding="async"{' fetchpriority="high"' if index==1 else ''}><figcaption>{credit}</figcaption></figure>'''

def visual(v,sources,index):
    title=esc(v.get("title",f"Data view {index}"));caption=esc(v.get("caption",''));raw_source=v.get("source",v.get("source_number",1))
    try: source_id=int(raw_source or 1)
    except (TypeError,ValueError):
        key=str(raw_source).casefold();source_id=next((i for i,x in enumerate(sources,1) if key in (str(x.get('title',''))+' '+str(x.get('name',''))).casefold()),1)
    src=sources[min(max(source_id-1,0),len(sources)-1)]
    kind=str(v.get("type","table")).casefold();kind='bar' if kind in ('chart','metrics','graph') else kind;labels=[str(x) for x in v.get("labels",[])];values=[float(x) for x in (v.get("values") or v.get("numeric_values") or [])]
    data=v.get("data") or []
    if not data and (not labels or len(labels)!=len(values)):raise ValueError(f"data visual {index} has mismatched labels and values")
    palette=("#9c4522","#d69a5c","#7b5d92","#c66b78","#315b7d","#bc5b33","#7a6a58","#512618")
    if kind=="table" and data:
        columns=list(data[0]);head=''.join(f'<th scope="col">{esc(x)}</th>' for x in columns);rows=''.join('<tr>'+''.join(f'<td>{esc(row.get(x,""))}</td>' for x in columns)+'</tr>' for row in data);body=f'<table><caption>{title}</caption><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    elif kind=="table":
        rows="".join(f"<tr><th>{esc(a)}</th><td>{b:g}</td></tr>" for a,b in zip(labels,values));body=f'<table><caption>{title}</caption><tbody>{rows}</tbody></table>'
    elif kind=="pie":
        total=sum(max(0,x) for x in values) or 1;offset=0;circles=[];legend=[]
        for i,(label,value) in enumerate(zip(labels,values)):
            share=max(0,value)/total*100;color=palette[i%len(palette)]
            circles.append(f'<circle cx="180" cy="170" r="105" fill="none" stroke="{color}" stroke-width="70" pathLength="100" stroke-dasharray="{share:.3f} {100-share:.3f}" stroke-dashoffset="{-offset:.3f}"/>');offset+=share
            legend.append(f'<li><i style="background:{color}"></i>{esc(label)} — {value:g}</li>')
        body=f'<div class="dy2-pie"><svg viewBox="0 0 360 340" role="img" aria-label="{title}">{"".join(circles)}</svg><ul>{"".join(legend)}</ul></div>'
    elif kind=="line":
        lo=min(values);hi=max(values);span=hi-lo or 1;step=620/max(1,len(values)-1);points=[];dots=[]
        for i,(label,value) in enumerate(zip(labels,values)):
            x=40+i*step;y=300-(value-lo)/span*240;points.append(f'{x:.1f},{y:.1f}');dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5"><title>{esc(label)}: {value:g}</title></circle>')
        body=f'<svg class="dy2-line" viewBox="0 0 700 340" role="img" aria-label="{title}"><polyline points="{" ".join(points)}"/>{"".join(dots)}</svg>'
    else:
        maximum=max(values) if values else 1;maximum=maximum or 1
        bars="".join(f'<div class="dy2-bar"><span>{esc(a)}</span><i style="width:{max(2,b/maximum*100):.2f}%"></i><b>{b:g}</b></div>' for a,b in zip(labels,values));body=f'<div class="dy2-chart dy2-{esc(kind)}" role="img" aria-label="{title}">{bars}</div>'
    return f'<figure class="dy2-data dy2-data-{esc(kind)}"><h3>{title}</h3>{body}<figcaption>{caption} Source: <a href="{esc(src["url"])}" rel="noopener" target="_blank">{esc(src["name"])}</a>.</figcaption></figure>'

def low_view_shelf(posts):
    cards=[]
    for p in posts:
        image=f'<img src="{esc(p.get("image",""))}" alt="Article preview: {esc(p.get("title","Daily Yield article"))}" loading="lazy" decoding="async">' if p.get("image") else ''
        cards.append(f'<a class="dy2-low-card" href="{esc(p["url"])}"><span>{image}</span><small>{esc(p.get("label","Daily Yield"))}</small><strong>{esc(p["title"])}</strong><em>Read next →</em></a>')
    group="".join(cards)
    return f'''<section class="dy2-low" aria-labelledby="dy2LowTitle"><header><small>Worth discovering</small><h2 id="dy2LowTitle">More from Daily Yield</h2><span>Swipe, drag or keep watching</span></header><div class="dy-related-viewport"><div class="dy-related-track"><div class="dy-related-group">{group}</div><div class="dy-related-group" aria-hidden="true">{group}</div></div></div></section>'''

def follow_block():
    links="".join(f'<a href="{esc(url)}" target="_blank" rel="me noopener noreferrer"><strong>{esc(name)}</strong><span>{esc(handle)}</span></a>' for name,url,handle in SOCIAL_PROFILES)
    return f'''<section class="dy2-follow" aria-labelledby="dy2Follow"><small>Follow Daily Yield</small><h2 id="dy2Follow">Stay with the reporting</h2><div>{links}</div><a class="dy2-sub" href="#dy-subscribe">Choose your email and notification alerts →</a></section>'''

def render(package,topic,pub_date,pub_time,canonical_url=None,modified_date=None,modified_time=None):
    metrics=validate(package);sources=package["sources"];internals=package.get("internal_links") or []
    title=package["title"].strip();category=topic["Category"];slug=slugify(title);url=canonical_url or f"{BLOG}/{pub_date[:7].replace('-','/')}/{slug}.html"
    modified_date=modified_date or pub_date;modified_time=modified_time or pub_time
    meta=str(package.get("meta_description","")).strip()[:158]
    if not 110<=len(meta)<=158: raise ValueError("MASTER V2 REJECTED — unique meta description must be 110–158 characters")
    toc="".join(f'<li><a href="#dy2-{i}">{esc(s["heading"])}</a></li>' for i,s in enumerate(package["sections"],1))
    heading_positions={str(s.get('heading','')).casefold().strip():i for i,s in enumerate(package['sections'],1)};visuals=[]
    for n,item in enumerate(package['visuals'],1):
        item=dict(item);raw=item.get('after_section',min(len(package['sections']),n+2))
        try: position=int(raw)
        except (TypeError,ValueError): position=heading_positions.get(str(raw).casefold().strip(),min(len(package['sections']),n+2))
        item['_after_section']=max(1,min(len(package['sections']),position));visuals.append(item)
    visuals.sort(key=lambda x:x['_after_section']);section_html=[];cumulative=0;second=False;third=False
    for i,s in enumerate(package["sections"],1):
        paragraphs="".join(f'<p>{linked_text(p,sources,internals)}</p>' for p in s["paragraphs"])
        cumulative+=words(" ".join(s["paragraphs"]))
        extra=""
        while visuals and visuals[0]['_after_section']<=i: extra+=visual(visuals.pop(0),sources,len(package["visuals"])-len(visuals))
        if cumulative>=2000 and not second: extra+=photo(package["photos"][1],2);second=True
        if cumulative>=4000 and not third: extra+=photo(package["photos"][2],3);third=True
        section_html.append(f'<section id="dy2-{i}"><h2>{esc(s["heading"])}</h2>{paragraphs}{extra}</section>')
    summary="".join(f'<p>{linked_text(p,sources,internals)}</p>' for p in package["summary"])
    faq="".join(f'<details><summary><span>{esc(x["question"])}</span></summary><div><p>{linked_text(x["answer"],sources,internals)}</p></div></details>' for x in package["faq"])
    glossary="".join(f'<dt>{esc(x["term"])}</dt><dd>{esc(x["definition"])}</dd>' for x in package["glossary"])
    source_list="".join(f'<li id="source-{i}"><a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["name"])} — {esc(x["title"])}</a><span>{esc(x.get("date",""))} · {esc(x.get("use",""))}</span></li>' for i,x in enumerate(sources,1))
    source_index="".join(f'<li><a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["name"])} — {esc(x["title"])}</a><span>{esc(x.get("date",""))} · {esc(x.get("use",""))}</span></li>' for x in sources)
    internal_list="".join(f'<li><a href="{esc(x["url"])}">{esc(x["title"])}</a><span>{esc(x.get("relevance",""))}</span></li>' for x in internals)
    mh=package.get('module_headings') or {};topic_name=title.rstrip('.!?')
    headings={'contents':mh.get('contents') or f'Inside {topic_name}','summary':mh.get('summary') or f'What {topic_name} changes','faq':mh.get('faq') or f'Questions readers ask about {topic_name}','glossary':mh.get('glossary') or f'Terms behind {topic_name}','sources':mh.get('sources') or f'Evidence behind {topic_name}','internal_links':mh.get('internal_links') or 'Continue exploring on Daily Yield','external_sources':mh.get('external_sources') or 'Research trail and primary records'}
    schema={"@context":"https://schema.org","@type":"BlogPosting","@id":url+"#article","url":url,"mainEntityOfPage":{"@id":url},"headline":title,"description":meta,"articleSection":category,"inLanguage":"en","wordCount":metrics["core_words"],"datePublished":f"{pub_date}T{pub_time}:00+05:30","dateModified":f"{modified_date}T{modified_time}:00+05:30","author":{"@type":"Person","name":AUTHOR,"url":BLOG+"/p/about-us_02080501126.html"},"publisher":{"@type":"Organization","name":"Daily Yield","url":BLOG+"/"},"image":[p["url"] for p in package["photos"]],"citation":[s["url"] for s in sources],"about":[{"@type":"Thing","name":str(x)} for x in package.get("entities",[])],"spatialCoverage":[{"@type":"Place","name":str(x)} for x in package.get("geography",[])],"temporalCoverage":str(package.get("temporal_coverage",pub_date))}
    css='''.dy2{max-width:960px;margin:auto;color:#241610;font:17px/1.75 Georgia,serif}.dy2 h1,.dy2 h2,.dy2 h3{font-family:Arial,sans-serif;color:#512618}.dy2 h1{font-size:clamp(34px,6vw,58px);line-height:1.05}.dy2 h2{margin-top:48px;font-size:clamp(24px,4vw,34px)}.dy2 a{color:#9c4522;text-decoration-thickness:1px;text-underline-offset:3px}.dy2 a:hover{color:#bc5b33}.dy2-by{font:13px Arial,sans-serif;color:#7a6a58}.dy2-photo{overflow:hidden;border-radius:14px}.dy2-photo img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:14px;transition:transform .7s ease,filter .7s ease}.dy2-photo:hover img{transform:scale(1.018);filter:saturate(1.06)}.dy2 figcaption{margin-top:8px;color:#6e5d4b;font:12px/1.5 Arial,sans-serif}.dy2-toc{padding:20px 24px;border:1px solid #eadcc8;border-radius:14px;background:#fff8ee;box-shadow:0 10px 28px rgba(81,38,24,.07)}.dy2-toc li{transition:transform .22s ease}.dy2-toc li:hover{transform:translateX(5px)}.dy2-data{margin:32px 0;padding:18px;border:1px solid #eadcc8;border-radius:14px;background:#fffdf8;overflow:auto;box-shadow:0 8px 24px rgba(81,38,24,.06);transition:transform .25s ease,box-shadow .25s ease}.dy2-data:hover{transform:translateY(-3px);box-shadow:0 14px 32px rgba(81,38,24,.11)}.dy2 table{width:100%;border-collapse:collapse}.dy2 th,.dy2 td{padding:9px;border:1px solid #eadcc8;text-align:left}.dy2 tbody tr{transition:background .2s ease}.dy2 tbody tr:hover{background:#fff3e3}.dy2-bar{display:grid;grid-template-columns:minmax(100px,1fr) 3fr auto;gap:8px;align-items:center;margin:8px 0}.dy2-bar i{display:block;height:18px;background:#bc5b33;border-radius:3px;transform-origin:left;animation:dy2-grow .8s ease both}.dy2-pie{display:grid;grid-template-columns:minmax(220px,360px) 1fr;align-items:center;gap:18px}.dy2-pie svg{width:100%;height:auto;transform:rotate(-90deg)}.dy2-pie ul{list-style:none;padding:0}.dy2-pie li{margin:8px 0}.dy2-pie li i{display:inline-block;width:12px;height:12px;margin-right:8px;border-radius:50%}.dy2-line{width:100%;height:auto}.dy2-line polyline{fill:none;stroke:#9c4522;stroke-width:5;stroke-linejoin:round}.dy2-line circle{fill:#d69a5c}.dy2-summary,.dy2-faq,.dy2-glossary,.dy2-links{margin-top:46px;padding-top:24px;border-top:1px solid #eadcc8}.dy2-faq{counter-reset:dy2faq}.dy2-faq details{counter-increment:dy2faq;margin:14px 0;border:1px solid #eadcc8;border-radius:14px;background:linear-gradient(135deg,#fffdf8,#fff8ee);box-shadow:0 7px 20px rgba(81,38,24,.06);overflow:hidden;transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease}.dy2-faq details:hover{transform:translateY(-2px);border-color:#d69a5c;box-shadow:0 12px 28px rgba(81,38,24,.11)}.dy2-faq details[open]{border-left:5px solid #9c4522}.dy2-faq summary{display:flex;align-items:center;gap:13px;padding:18px 54px 18px 18px;cursor:pointer;list-style:none;position:relative;color:#512618;font:700 17px/1.4 Arial,sans-serif}.dy2-faq summary::-webkit-details-marker{display:none}.dy2-faq summary:before{content:counter(dy2faq,decimal-leading-zero);display:grid;place-items:center;flex:0 0 34px;height:34px;border-radius:50%;background:#f6e3d3;color:#9c4522;font-size:12px}.dy2-faq summary:after{content:'+';position:absolute;right:19px;top:16px;color:#9c4522;font:300 30px/1 Arial,sans-serif;transition:transform .35s ease}.dy2-faq details[open] summary:after{transform:rotate(45deg)}.dy2-faq details>div{display:grid;grid-template-rows:0fr;transition:grid-template-rows .42s ease}.dy2-faq details>div>p{overflow:hidden;margin:0;padding:0 22px;color:#59483e}.dy2-faq details[open]>div{grid-template-rows:1fr}.dy2-faq details[open]>div>p{padding:0 22px 20px;animation:dy2-answer .45s ease both}.dy2-glossary dt{font-weight:bold;color:#512618}.dy2-glossary dd{margin:0 0 14px}.dy2-links li{margin:10px 0}.dy2-links span{display:block;color:#7a6a58;font-size:13px}.dy2-low,.dy2-follow{max-width:1120px;margin:52px auto;padding:22px;border:1px solid #eadcc8;border-radius:16px}.dy2-low header{display:flex;flex-wrap:wrap;align-items:end;gap:8px 18px}.dy2-low header h2{margin:0}.dy2-low header span{margin-left:auto}.dy2-low-card{display:flex;flex:0 0 270px!important;width:270px!important;flex-direction:column;padding:10px;border:1px solid #eadcc8;border-radius:12px;background:#fffdf8;text-decoration:none;transition:transform .25s ease,box-shadow .25s ease}.dy2-low-card:hover{transform:translateY(-4px);box-shadow:0 12px 26px rgba(81,38,24,.12)}.dy2-low-card>span{height:110px;overflow:hidden}.dy2-low-card img{width:100%;height:100%;object-fit:cover}.dy2-low-card small{margin-top:8px}.dy2-low-card strong{margin:6px 0}.dy2-low-card em{margin-top:auto}.dy2-follow>div{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.dy2-follow>div a{padding:12px;border:1px solid #eadcc8;border-radius:10px;text-decoration:none;transition:transform .2s ease,background .2s ease}.dy2-follow>div a:hover{transform:translateY(-2px);background:#fff8ee}.dy2-follow span{display:block}.dy2-sub{display:block;margin-top:14px}.dy2>section,.dy2>figure,.dy2>nav{animation:dy2-reveal linear both;animation-timeline:view();animation-range:entry 3% cover 22%}@keyframes dy2-reveal{from{opacity:.25;transform:translateY(22px)}to{opacity:1;transform:none}}@keyframes dy2-grow{from{transform:scaleX(.05)}to{transform:scaleX(1)}}@keyframes dy2-answer{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}@media(max-width:640px){.dy2{font-size:16px}.dy2-follow>div{grid-template-columns:1fr 1fr}.dy2-bar{grid-template-columns:1fr}.dy2-bar i{min-width:2px}.dy2-pie{grid-template-columns:1fr}.dy2-faq summary{padding-left:14px}}@media(prefers-reduced-motion:reduce){.dy2 *{animation:none!important;transition:none!important;scroll-behavior:auto!important}}'''
    body=f'''<!-- DY_MASTER_V2 --><article class="dy2"><style>{css}</style><header><h1>{esc(title)}</h1><p class="dy2-by">{esc(category)} · By <strong>{AUTHOR}</strong> · Published {esc(pub_date)}</p></header>{photo(package['photos'][0],1)}<nav class="dy2-toc" aria-label="Table of contents"><h2>{esc(headings['contents'])}</h2><ol>{toc}</ol></nav>{''.join(section_html)}<section class="dy2-summary"><h2>{esc(headings['summary'])}</h2>{summary}</section><section class="dy2-faq"><h2>{esc(headings['faq'])}</h2>{faq}</section><section class="dy2-glossary"><h2>{esc(headings['glossary'])}</h2><dl>{glossary}</dl></section><section class="dy2-links"><h2>{esc(headings['sources'])}</h2><ol>{source_list}</ol><h2>{esc(headings['internal_links'])}</h2><ul>{internal_list}</ul><h2>{esc(headings['external_sources'])}</h2><ol>{source_index}</ol></section><p><strong>Important:</strong> Educational information only; not personalised financial, tax, investment, credit or legal advice.</p></article>{low_view_shelf(package['low_view_posts'])}{follow_block()}{family_block('',include_follow=False)}<script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script>'''
    return title,slug,meta,[category,AUTHOR],body
