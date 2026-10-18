#!/usr/bin/env python3
"""Nine individually reviewed legacy briefings. No new stories or invented facts."""
from __future__ import annotations
import datetime as dt,html,json,re
from decimal import Decimal
from pathlib import Path
from bs4 import BeautifulSoup
from news_pipeline import WHY
from html.parser import HTMLParser
from content_policy_guard import audit_text

REVIEW={
 '7509329855154139182':{'drop':{3:'Non-financial military/landmine story misread as trade.',4:'Weather-only source excerpt has no supported finance angle.',6:'Headline is a 2024 forecast, not current October 2026 reporting.'},'summaries':{10:'Linked source: The Economic Times, on U.S. Treasury yields and French/German bond markets. The historical headline is retained; this archive does not reproduce a separate verified numerical summary.'}},
 '1134526280711723914':{'drop':{2:'Earlier LEAD version of the retained second-lead Seoul-market dispatch.',3:'Initial version of the same Seoul-market wire story.',7:'Initial version of the retained LEAD oil-recovery-project story.',8:'Ordinary sporting medals, not commodity gold or finance.'},'summaries':{1:"Yonhap's retained second-lead headline reports Seoul shares closing higher and the Korean won rising on October 2. Earlier versions of that same wire dispatch are consolidated, not counted as additional events.",6:"The retained Yonhap LEAD headline reports Trump's description of an US$8.4 billion oil-recovery project. Its earlier initial dispatch is not treated as a separate project or event."}},
 '4156483657490223145':{'drop':{4:'Ordinary Asian Games medal results, not financial reporting.',5:'Ordinary fencing medal results, not financial reporting.',7:'Earlier LEAD version of retained second-lead market dispatch.',8:'Initial version of retained second-lead market dispatch.'},'summaries':{6:"Yonhap's retained second-lead headline reports Seoul stocks falling more than 2.5 percent on chip losses. The earlier initial and LEAD versions are consolidated into that one source event."}},
 '3566483254293904115':{'drop':{i:'Ordinary sports/medal coverage, including repeated wire updates; not finance.' for i in range(2,9)},'summaries':{}},
 '4559693310963899298':{'drop':{3:'War/security statement without a supported personal-finance angle.',10:'Ordinary equestrian medal report, not finance.',11:'Earlier version of the same non-financial medal result.',12:'Urgent version of the same non-financial medal result.',13:'Animal-loan/diplomacy story, not a financial loan report in the retained excerpt.'},'summaries':{}},
 '9051696550888128467':{'drop':{},'summaries':{11:"Linked source: Yahoo Finance, discussing U.S. debt and Treasury-yield risks. This is the publisher's historical risk framing, not a prediction or a statement about today's market."}},
 '2983561509636256187':{'drop':{i:'Ordinary sports or medal coverage; not finance. Original duplicate medal wires are not separate financial events.' for i in range(1,10)},'summaries':{},'no_current_financial_items':True},
 '9115764774433521189':{'drop':{i:'Ordinary sports/medal reporting, including multiple wire versions; not finance.' for i in range(1,9)},'summaries':{}},
 '8605540625196160085':{'drop':{3:'Earlier second-lead version of retained third-lead cooperation story.',4:'Ordinary kayak medal result, not financial reporting.',5:'Earlier update of the non-financial kayak result.',6:'Initial update of the non-financial kayak result.',7:'Urgent update of the non-financial kayak result.',8:'Ordinary gymnastics medal preview, not finance.'},'summaries':{2:"Yonhap's retained third-lead headline describes a South Korea-Mexico cooperation plan covering defence, crude oil and AI. The earlier second-lead dispatch is consolidated rather than counted as another agreement."}}
}
MARK='DY_ARCHIVE_SOURCE_REVIEW_20261018'


def all_item_spans(document):
    starts=[0]
    for match in re.finditer('\n',document):starts.append(match.end())
    class Parser(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=False);self.divs=[];self.items=[]
        def absolute(self):
            line,column=self.getpos();return starts[line-1]+column
        def handle_starttag(self,tag,attrs):
            if tag=='div':
                classes=dict(attrs).get('class','') or ''
                self.divs.append((self.absolute(),'fbk-item' in classes.split()))
        def handle_endtag(self,tag):
            if tag=='div' and self.divs:
                start,is_item=self.divs.pop()
                if is_item:
                    end=self.absolute();close=re.match(r'</div\s*>',document[end:],re.I)
                    if not close:raise ValueError('unrecognised item close')
                    self.items.append({'start':start,'end':end+close.end()})
    parser=Parser();parser.feed(document);parser.close()
    spans=sorted(parser.items,key=lambda x:x['start'])
    if len(spans)!=len(BeautifulSoup(document,'html.parser').select('.fbk-item')):raise ValueError('item parser did not cover every background/reference entry')
    return spans


def executable_scripts(document):
    return [m.group(0) for m in re.finditer(r'<script\b[^>]*>.*?</script>',document,re.I|re.S)
            if not re.search(r'type=["\']application/ld\+json["\']',m.group(0),re.I)]


def match_archive_metadata(document,headline,description,edition):
    def walk(value):
        if isinstance(value,list):
            for item in value:walk(item)
        elif isinstance(value,dict):
            types=value.get('@type',[]);types=[types] if isinstance(types,str) else types
            if set(types)&{'Article','NewsArticle'}:
                value['headline']=headline;value['description']=description
                if 'dateModified' in value:value['dateModified']=dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).isoformat()
                if 'keywords' in value:value['keywords']='Daily Yield, Kushal Daga, CA Kushal Daga, Kushal Daga website, corrected historical finance archive, '+edition
            for key,item in value.items():
                if key not in ('author','publisher'):walk(item)
    def replace(match):
        data=json.loads(match.group(2));walk(data)
        return match.group(1)+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+match.group(3)
    return re.sub(r'(<script\b(?=[^>]*type=["\']application/ld\+json["\'])[^>]*>)(.*?)(</script>)',replace,document,flags=re.I|re.S)


def strip_stock(document):
    literals=[s for values in WHY.values() for s in values]
    parts=re.split(r'(<script\b.*?</script>|<style\b.*?</style>)',document,flags=re.I|re.S)
    for i in range(0,len(parts),2):
        for line in literals:
            for literal in (line,html.escape(line),html.escape(line,quote=False)):
                parts[i]=parts[i].replace('<em>'+literal+'</em>','').replace(literal,'')
    return ''.join(parts)


def reference_date(edition,rates):
    # These editions were published before the next European reference fixing.
    before=dt.date.fromisoformat(edition)-dt.timedelta(days=1)
    eligible=[date for date in rates if date<=before.isoformat()]
    if not eligible:raise ValueError('no historical ECB fixing available')
    return max(eligible)


def verify_reference(item,date,rates):
    title=BeautifulSoup(item,'html.parser').find(['h2','h3','h4'])
    values=dict(re.findall(r'EUR/([A-Z]{3})\s+([0-9]+\.[0-9]+)',title.get_text(' ',strip=True) if title else ''))
    if set(values)!={'USD','GBP','JPY','CNY','INR','BRL'}:raise ValueError('reference heading was not recognised')
    for currency,printed in values.items():
        actual=Decimal(rates[date][currency]);precision=len(printed.split('.')[1]);tolerance=Decimal(1).scaleb(-precision)/2
        if abs(Decimal(printed)-actual)>tolerance:raise ValueError('historical ECB figure differs: '+currency)
    return values


def review_content(post_id,content,rates):
    spec=REVIEW[post_id]
    if MARK in content:return content,{'status':'ALREADY_REVIEWED','removed':[]}
    spans=all_item_spans(content);soup=BeautifulSoup(content,'html.parser')
    h=soup.find('h1');heading=h.get_text(' ',strip=True) if h else ''
    date_match=re.search(r'(\d{1,2}) (September|October) (2026)',heading)
    if not date_match:raise ValueError('original edition date not found')
    day,month,year=date_match.groups();edition=dt.date(int(year),9 if month=='September' else 10,int(day)).isoformat()
    date=reference_date(edition,rates);removed=[];retained=[];replacements={};fx_values=None
    for number,span in enumerate(spans,1):
        raw=content[span['start']:span['end']];node=BeautifulSoup(raw,'html.parser');title=node.find(['h2','h3','h4']);title=title.get_text(' ',strip=True) if title else ''
        link=node.select_one('a.fbk-src[href]');url=link.get('href') if link else ''
        if number in spec['drop']:
            removed.append({'position':number,'title':title,'source':url,'reason':spec['drop'][number]});replacements[number]='';continue
        new=raw
        if number in spec['summaries']:
            paragraphs=list(re.finditer(r'<p\b[^>]*>.*?</p>',new,re.S|re.I))
            if not paragraphs:raise ValueError('target source paragraph missing')
            first=paragraphs[0];new=new[:first.start()]+'<p>'+html.escape(spec['summaries'][number])+'</p>'+new[first.end():]
        new=strip_stock(new)
        if title.startswith('EUR/USD'):
            fx_values=verify_reference(raw,date,rates)
            replacement=(f'Historical ECB reference, dated {date}: these retained figures match the primary ECB history within their displayed rounding. They are not current prices, retail conversion offers or executable trading quotes. Use the linked ECB source for current reference data.')
            new=re.sub(r'<p\b[^>]*>.*?</p>','<p>'+replacement+'</p>',new,count=1,flags=re.I|re.S)
        retained.append({'position':number,'title':title,'source':url});replacements[number]=new
    if not fx_values:raise ValueError('historical reference was not verified')
    out=content
    for number,span in reversed(list(enumerate(spans,1))):out=out[:span['start']]+replacements[number]+out[span['end']:]
    lead=(f'Archived briefing: {len(retained)-1} retained source-linked news/context entries, plus one historical ECB reference box. A source-selection correction on 18 October 2026 removed non-financial material and consolidated overlapping wire updates. The original publication and coverage dates are retained; this is not a live market update or a claim of exhaustive coverage.')
    if spec.get('no_current_financial_items'):
        lead=('Archive correction: no current-window financial items remain from the original source batch. It was dominated by sporting medal results, which have been removed rather than passed off as commodity or economic news. One previously labelled trade-background entry and the historical ECB reference are retained for transparency. No replacement financial news has been invented or backdated.')
    out,n=re.subn(r'(<p\b[^>]*class=["\'][^"\']*\bfbk-lede\b[^"\']*["\'][^>]*>).*?(</p>)',lambda m:m.group(1)+html.escape(lead)+m.group(2),out,count=1,flags=re.I|re.S)
    if n!=1:raise ValueError('archive introduction not recognised')
    note=('Source-review correction, 18 October 2026: repeated wire versions are not separate events. Source headlines and commentary remain attributed to their publishers. Earlier non-financial selections and unsupported completeness/freshness wording were removed. This archive is historical information, not personal financial advice.')
    out,n=re.subn(r'(<p\b[^>]*class=["\'][^"\']*\bfbk-note\b[^"\']*["\'][^>]*>).*?(</p>)',lambda m:m.group(1)+html.escape(note)+m.group(2),out,count=1,flags=re.I|re.S)
    if n!=1:raise ValueError('recency note not recognised')
    if spec.get('no_current_financial_items'):
        # Put an explicit correction in the original empty Tape area, not an
        # invented replacement story or an abandoned under-construction widget.
        match=re.search(r'(<p class="fbk-sub">.*?</p>)',out,re.S)
        if match:out=out[:match.end()]+'<p>Correction: the original in-window items in this section were non-financial sports reports. They were removed; no verified current-window financial report is claimed for this section.</p>'+out[match.end():]
    out=match_archive_metadata(out,heading,'Corrected historical finance archive. Source selection reviewed on 18 October 2026; original publication date retained. Not live market data.',edition)
    out+='\n<!-- '+MARK+' -->'
    # Hard bounds: no full HTML reserialization, title/URL changes or hidden code changes.
    if executable_scripts(content)!=executable_scripts(out):raise ValueError('executable script changed')
    for pattern in (r'<style\b.*?</style>',r'<img\b[^>]*>',r'<h1\b.*?</h1>'):
        if re.findall(pattern,content,re.I|re.S)!=re.findall(pattern,out,re.I|re.S):raise ValueError('protected script/style/image/H1 changed')
    before_links=[x['source'] for x in retained]
    after_soup=BeautifulSoup(out,'html.parser')
    after_links=[a.get('href') for a in after_soup.select('.fbk-item a.fbk-src[href]')]
    if before_links!=after_links:raise ValueError('retained source links changed')
    outside=lambda soup:[a.get('href') for a in soup.select('a[href]') if not a.find_parent('div',class_='fbk-item')]
    if outside(soup)!=outside(after_soup):raise ValueError('outside-source navigation links changed')
    issues=audit_text(heading,out,'archive-review',require_disclosure=True)
    # Policy audit of full chrome may legitimately flag library code; report it,
    # never remove a check or a genuine quotation merely to force a green result.
    return out,{'status':'REVIEWED','edition':edition,'retained':retained,'removed':removed,
                'retainedCount':len(retained),'referenceDate':date,'referenceValues':fx_values,
                'noCurrentFinancialItems':bool(spec.get('no_current_financial_items')),'postReviewFlags':issues,
                'imagesAndExecutableCodeUnchanged':True,'existingArticleMetadataMatchedToCorrection':True,'newFinancialClaimsInvented':False}
