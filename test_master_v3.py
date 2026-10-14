from unittest.mock import patch
from master_article_v2 import words
from master_article_v2 import validate
from master_v3_generator import build,extracted_summary,support,validate_section,visuals,write_section

def paragraphs():
    base=('Markets connect household choices with documented policy boundaries and uncertainty through evidence. '*50).split()[:440]
    return [' '.join(base[i:i+110])+' [[S1|documented source]]' for i in range(0,440,110)]
def prose():return '\n\n'.join(paragraphs())
def sections():return [{'heading':f'Distinct evidence heading {i}','paragraphs':paragraphs()} for i in range(9)]

def test_v3_section_contract_is_narrow_enough_for_article_total():
    p=paragraphs();ok,error=validate_section(p,{1:' '.join(p)})
    assert ok,error
    assert 400<=words(' '.join(p))<=490
    assert 10*400==4000

def test_v3_summary_support_and_visuals_are_deterministic():
    rows=sections();summary=extracted_summary(rows);faq,glossary=support(rows)
    sources=[{'name':f'Source {i}','title':f'Topic evidence {i}','url':f'https://example.com/{i}','text':prose()} for i in range(1,9)]
    charts=visuals(sources,rows)
    assert 600<=words(' '.join(summary))<=800
    assert len(faq)>=5 and len(glossary)>=8 and len(charts)==3
    assert all(x['type']=='table' and len(x['data'])>=2 for x in charts)

def test_v3_plain_text_section_does_not_require_json():
    source={'name':'Official source','title':'Market policy evidence','url':'https://example.com','text':prose()}
    with patch('master_v3_generator.text_call',return_value=prose()):
        out=write_section('Market Policy Evidence','Documented market scope',1,[(1,source)])
    assert out and 400<=words(' '.join(out))<=490

def test_v3_accumulates_safe_short_attempts():
    source={'name':'Official source','title':'Market policy evidence','url':'https://example.com','text':prose()}
    first='\n\n'.join(paragraphs()[:2]);attempts=[first.replace('Markets',word) for word in ('Markets','Households','Consumers','Investors','Workers','Families')]
    with patch('master_v3_generator.text_call',side_effect=attempts):
        out=write_section('Market Policy Evidence','Documented market scope',1,[(1,source)])
    assert len(out)>=4 and 400<=words(' '.join(out))<=490

def test_v3_full_package_satisfies_existing_strict_compiler(tmp_path):
    sources=[{'name':f'Official Source {i}','title':f'Distinct Market Evidence {i}','url':f'https://example.com/{i}','text':prose(),'overlap':5} for i in range(1,11)]
    photos=[{'url':f'https://example.com/photo-{i}.jpg','alt':'Relevant financial editorial photograph','caption':'Photo: Creator / CC BY 4.0','width':1600,'height':900} for i in range(1,4)]
    low=[{'title':f'Article {i}','url':f'https://dailyyield.blogspot.com/{i}','image':'','label':'Daily Yield'} for i in range(15)]
    item={'id':'v3-test','title':'Household Market Evidence','category':'Money Decisions','sources':[]}
    with patch('master_v3_generator.discover_sources',return_value=sources),patch('master_v3_generator.write_section',return_value=paragraphs()),patch('master_v3_generator.photo_set',return_value=photos),patch('master_v3_generator.low_exposure_posts',return_value=low):
        package=build(item,'evergreen',tmp_path/'package.json')
    result=validate(package)
    assert 4000<=result['core_words']<=4200 and 600<=result['summary_words']<=800
