#!/usr/bin/env python3
"""Corpus-level originality checks for automated editorial packages."""
from __future__ import annotations
import json,re
from pathlib import Path
from content_policy_guard import normalize_sentence,sentences

def package_text(package:dict)->str:
 return ' '.join(' '.join(x.get('paragraphs') or []) for x in package.get('sections') or [])

def shingles(text:str,size:int=5)->set[tuple[str,...]]:
 words=re.findall(r"[a-z0-9]+",text.casefold());return {tuple(words[i:i+size]) for i in range(max(0,len(words)-size+1))}

def assert_cross_corpus_original(package:dict,target:Path,root:Path|None=None)->bool:
 root=root or Path(__file__).parent
 current=package_text(package);current_sentences={normalize_sentence(x) for x in sentences(current) if len(normalize_sentence(x).split())>=14}
 current_shingles=shingles(current);issues=[]
 for path in sorted((root/'master_packages'/'dynamic').glob('*.json'))[-120:]:
  try:
   if path.resolve()==target.resolve():continue
   prior=json.loads(path.read_text());prior_text=package_text(prior)
  except Exception:continue
  prior_sentences={normalize_sentence(x) for x in sentences(prior_text) if len(normalize_sentence(x).split())>=14}
  overlap=current_sentences&prior_sentences
  if overlap:
   issues.append(f'exact substantive sentence reused from {path.name}')
   break
  prior_shingles=shingles(prior_text)
  union=len(current_shingles|prior_shingles);similarity=len(current_shingles&prior_shingles)/union if union else 0
  if similarity>0.42:
   issues.append(f'article language too similar to {path.name} ({similarity:.1%})')
   break
 if issues:raise RuntimeError('CORPUS ORIGINALITY GATE FAILED — '+'; '.join(issues))
 return True
