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

def contextualize_cross_corpus_repeats(package:dict,target:Path,root:Path|None=None)->dict:
 """Make an accidental prior-package sentence specific to its current section.

 This does not weaken the fail-closed originality gate: it only adds current
 section context to exact prose collisions, then the unchanged gate runs again.
 """
 root=root or Path(__file__).parent;prior_sentences=set()
 for path in sorted((root/'master_packages'/'dynamic').glob('*.json'))[-120:]:
  try:
   if path.resolve()==target.resolve():continue
   prior_sentences|={normalize_sentence(x) for x in sentences(package_text(json.loads(path.read_text()))) if len(normalize_sentence(x).split())>=14}
  except Exception:continue
 for section in package.get('sections') or []:
  heading=' '.join(re.findall(r"[A-Za-z0-9’'\-]+",str(section.get('heading') or 'this evidence'))[:8])
  rebuilt=[]
  for paragraph in section.get('paragraphs') or []:
   parts=re.split(r'(?<=[.!?])\s+',paragraph.strip());updated=[]
   for sentence in parts:
    key=normalize_sentence(sentence)
    if len(key.split())>=14 and key in prior_sentences:
     sentence=f'For {heading}, '+sentence[0].lower()+sentence[1:]
    updated.append(sentence)
   rebuilt.append(' '.join(updated))
  section['paragraphs']=rebuilt
 return package

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
