#!/usr/bin/env python3
"""Truthful image descriptions and conservative real-photograph selection."""
from __future__ import annotations
import html,re
from urllib.parse import urlparse,unquote

NON_PHOTO=re.compile(r'\.(?:pdf|webm|ogv|ogg|svg|gif)(?:$|[?#])|fileicon|\b(?:diagram|infographic|cartoon|engraving|lithograph|painting|coat of arms|clipart)\b',re.I)


def actual_subject(record):
    text=record.get('source_title') or record.get('title') or ''
    if not text and '/wiki/File:' in str(record.get('source_page','')):
        text=unquote(unquote(record['source_page'].split('/wiki/File:',1)[1]))
    text=html.unescape(re.sub(r'<[^>]+>',' ',str(text))).replace('_',' ')
    text=re.sub(r'^File:','',text,flags=re.I)
    text=re.sub(r'\.(?:jpe?g|png|webp|tiff?|pdf|webm|ogv|ogg|svg)$','',text,flags=re.I)
    return re.sub(r'\s+',' ',text).strip()[:200]


def source_alt(record):
    if record.get('actual_subject_verified') and record.get('actual_subject'):
        return 'Illustrative image: '+str(record['actual_subject'])[:195]
    subject=actual_subject(record)
    source=record.get('source_page','')+' '+record.get('original_url','')
    label='Illustrative source image' if NON_PHOTO.search(source) else 'Illustrative photograph'
    return (label+' titled: '+subject)[:220] if subject else 'Illustrative image; see the credited source and licence. No particular event or person is implied.'


def photographic_candidate(record):
    original=record.get('original_url') or record.get('source_page') or ''
    identity=' '.join(str(record.get(k,'') or '') for k in ('title','source_title','source_page','original_url'))
    description=str(record.get('description','') or '')
    if re.search(r'\.(?:pdf|webm|ogv|ogg|svg|gif)(?:$|[?#\s])|fileicon',identity,re.I):return False
    # Do not mistake "painting a vision" or factory workers painting aircraft
    # for the medium of an image. Require an actual non-photographic medium.
    if re.search(r'wood engraving|oil painting|lithograph|digital artwork|schematic diagram|hand.drawn illustration|clipart|coat of arms',identity+' '+description,re.I):return False
    path=unquote(urlparse(original).path)
    return bool(re.search(r'\.(?:jpe?g|png|webp|tiff?)$',path,re.I))
