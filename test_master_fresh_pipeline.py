from unittest.mock import patch
from master_fresh_pipeline import short_title,unsupported_numbers,generate_section,interleaved_extract
from master_article_v2 import words


def evidence():
    return [{'name':f'Source {i}','title':f'Finance record {i}','url':f'https://example.com/{i}','text':'The financial market evidence reports 25 percent for the documented sample. Scope and uncertainty are explicitly described.'} for i in range(1,10)]


def test_fresh_title_is_renderer_safe():
    title=short_title('A Very Long Financial Headline About Household Credit Decisions | Publisher Name')
    assert 12<=len(title)<=46
    assert 'Publisher' not in title


def test_numeric_gate_accepts_only_cited_evidence_numbers():
    rows=evidence()
    assert unsupported_numbers('The source reports 25 percent. [[S1|record]]',rows,{1})==[]
    assert unsupported_numbers('The source reports 99 percent. [[S1|record]]',rows,{1})==['99']


def test_bounded_section_generation_uses_small_independent_contract():
    paragraph=('Market evidence describes household credit mechanisms, affected groups, jurisdiction, trade-offs and uncertainty without extending beyond the documented source. '*7)+'[[S1|documented market evidence]]'
    payload={'paragraphs':[paragraph]*5}
    with patch('master_fresh_pipeline.model_json',return_value=payload):
        section=generate_section('Household Credit Choices','Credit choices: evidence baseline',0,evidence())
    assert 400<=words(' '.join(section['paragraphs']))<=490
    assert section['heading']=='Credit choices: evidence baseline'


def test_summary_is_extracted_from_verified_sections_not_generated():
    sections=[]
    for i in range(9):
        paragraphs=[]
        for j in range(6):
            paragraphs.append((f'Section {i} paragraph {j} explains documented financial mechanisms and uncertainty for affected readers in the cited jurisdiction. '*8)+f' [[S1|source {i}]]')
        sections.append({'heading':f'Heading {i}','paragraphs':paragraphs})
    summary=interleaved_extract(sections)
    assert 600<=words(' '.join(summary))<=800
