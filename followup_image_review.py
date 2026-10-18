#!/usr/bin/env python3
"""Like-for-like corrections within exactly the 44 reviewed existing figure slots."""
from __future__ import annotations
import html,json,re,datetime as dt
from bs4 import BeautifulSoup
from source_photography import source_alt

MARK='DY_IMAGE_SOURCE_REVIEW_20261018'


def caption(photo):
    creator=photo.get('creator')
    licence=photo.get('license') or photo.get('licence')
    licence_url=photo.get('license_url') or photo.get('licence_url')
    source=photo.get('source_page') or photo.get('original_url')
    if not (source and licence and licence_url):raise ValueError('reviewed primary reuse evidence missing')
    subject=photo.get('actual_subject') or 'Source image'
    credit=('Credit: '+str(creator)+'. ') if creator else 'Stock image from Unsplash; creator not identified in the retained asset metadata. '
    return ('Illustrative image: '+html.escape(subject)+'. '+html.escape(credit)+
            '<a href="'+html.escape(source,quote=True)+'" rel="noopener" target="_blank">'+html.escape('Source: '+str(photo.get('source_title') or photo.get('title') or photo.get('provider') or 'primary record'))+'</a> · '+
            '<a href="'+html.escape(licence_url,quote=True)+'" rel="license noopener" target="_blank">'+html.escape(licence)+'</a>. '+
            'Used as an illustration, not as evidence of the particular people, organisation or event discussed. Display may be cropped or resized.')


def image_data_references(document,mapping):
    # Exact image-data replacement, not a new script or a logic modification.
    for old,new in mapping.items():
        for a,b in ((old,new),(html.escape(old,quote=True),html.escape(new,quote=True)),(json.dumps(old)[1:-1],json.dumps(new)[1:-1])):
            document=document.replace(a,b)
    return document


def executable_scripts(document,mapping=None):
    values=[]
    for m in re.finditer(r'<script\b[^>]*>.*?</script>',document,re.I|re.S):
        if re.search(r'type=["\']application/ld\+json["\']',m.group(0),re.I):continue
        text=m.group(0)
        # Image URI data is allowed to change; executable logic is not.
        for url in sorted(set((mapping or {}).keys())|set((mapping or {}).values()),key=len,reverse=True):
            for variant in (url,html.escape(url,quote=True),json.dumps(url)[1:-1]):text=text.replace(variant,'__REVIEWED_IMAGE_URI__')
        values.append(text)
    return values


def update_existing_modified_date(document):
    def walk(value):
        if isinstance(value,list):
            for x in value:walk(x)
        elif isinstance(value,dict):
            types=value.get('@type',[]);types=[types] if isinstance(types,str) else types
            if set(types)&{'Article','NewsArticle'} and 'dateModified' in value:
                value['dateModified']=dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).isoformat()
            for key,x in value.items():
                if key not in ('author','publisher'):walk(x)
    def replace(m):
        data=json.loads(m.group(2));walk(data)
        return m.group(1)+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+m.group(3)
    return re.sub(r'(<script\b(?=[^>]*type=["\']application/ld\+json["\'])[^>]*>)(.*?)(</script>)',replace,document,flags=re.I|re.S)


def correct_figures(document,patches):
    out=document;found=[];mapping={p['oldSrc']:p['newPhoto']['url'] for p in patches}
    for patch in patches:
        photo=patch['newPhoto'];old=patch['oldSrc'];new=photo['url'];matches=[]
        for match in re.finditer(r'<figure\b[^>]*>.*?</figure>',out,re.I|re.S):
            soup=BeautifulSoup(match.group(0),'html.parser')
            if any(html.unescape(x.get('src',''))==old for x in soup.find_all('img',src=True)):matches.append(match)
        if not matches:
            # Idempotent retry recognises the already-corrected source and caption.
            if MARK in out and any(html.unescape(x.get('src',''))==new for x in BeautifulSoup(out,'html.parser').select('figure img[src]')):continue
            raise ValueError('exact reviewed figure not found; defer rather than editing another image')
        for match in reversed(matches):
            block=match.group(0)
            def img_replace(m):
                tag=m.group(0);src=re.search(r'\bsrc=["\']([^"\']+)',tag,re.I)
                if not src or html.unescape(src.group(1))!=old:return tag
                tag=tag[:src.start(1)]+html.escape(new,quote=True)+tag[src.end(1):]
                alt=html.escape(source_alt(photo),quote=True)
                if re.search(r'\balt=["\']',tag,re.I):tag=re.sub(r'\balt=(["\']).*?\1','alt="'+alt+'"',tag,count=1,flags=re.I|re.S)
                else:tag=tag.replace('<img','<img alt="'+alt+'"',1)
                # A stale srcset would override the corrected source on some screens.
                tag=re.sub(r'\s+srcset=(["\']).*?\1','',tag,flags=re.I|re.S)
                return tag
            block=re.sub(r'<img\b[^>]*>',img_replace,block,flags=re.I|re.S)
            credit=caption(photo)
            if re.search(r'<figcaption\b',block,re.I):block=re.sub(r'(<figcaption\b[^>]*>).*?(</figcaption>)',lambda m:m.group(1)+credit+m.group(2),block,count=1,flags=re.I|re.S)
            else:block=re.sub(r'</figure\s*>','<figcaption>'+credit+'</figcaption></figure>',block,count=1,flags=re.I)
            out=out[:match.start()]+block+out[match.end():]
        found.append({'oldSrc':old,'newSrc':new,'imageChanged':old!=new,'primarySource':photo.get('source_page'),'licence':photo.get('license') or photo.get('licence')})
    out=image_data_references(out,mapping)
    if found and MARK not in out:out+='\n<!-- '+MARK+' -->'
    if out!=document:out=update_existing_modified_date(out)
    if len(re.findall(r'<img\b',document,re.I))!=len(re.findall(r'<img\b',out,re.I)):raise ValueError('image count changed')
    for pattern in (r'<style\b.*?</style>',r'<h1\b.*?</h1>'):
        if re.findall(pattern,document,re.I|re.S)!=re.findall(pattern,out,re.I|re.S):raise ValueError('style/H1 changed')
    if executable_scripts(document,mapping)!=executable_scripts(out,mapping):raise ValueError('executable logic changed')
    # Financial prose is untouched; only figure blocks and exact image URI data vary.
    prose=lambda text:re.sub(r'<figure\b.*?</figure>|<script\b.*?</script>|<!--.*?-->',' ',text,flags=re.I|re.S)
    if image_data_references(prose(document),mapping).strip()!=prose(out).strip():raise ValueError('image correction changed financial prose')
    return out,found
