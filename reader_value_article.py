#!/usr/bin/env python3
"""Load and compile a researched Master Article V2 package.

The rejected fixed cross-topic template has been removed. Packages are prepared
by prepare_master_article.py and must pass strict word, evidence, visual, image,
summary, FAQ, glossary, link and low-exposure-shelf validation before use.
"""
import json,re
from pathlib import Path
from master_article_v2 import render
from brand_identity import ensure_brand_identity
from seo_meta import ensure_seo_meta
from social_identity import ensure_social_identity


def build(topic,pub_date,pub_time,hero=None):
    path=Path(__file__).with_name('master_packages')/f"topic_{topic['#']}.json"
    if not path.exists():
        raise RuntimeError(f'compliant researched package is missing: {path}; run prepare_master_article.py first')
    package=json.loads(path.read_text(encoding='utf-8'))
    title,slug,meta,labels,body=render(package,topic,pub_date,pub_time)
    first=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I)
    body=ensure_seo_meta(body,title,meta,first.group(1) if first else '')
    body=ensure_social_identity(ensure_brand_identity(body))
    return title,slug,meta,labels,body
