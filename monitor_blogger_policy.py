#!/usr/bin/env python3
"""Detect official Blogger Content Policy wording changes for supervised review."""
from __future__ import annotations
import datetime as dt,hashlib,json,re
from pathlib import Path
import requests
URL='https://www.blogger.com/content-policy';OUT=Path('BLOGGER_POLICY_MONITOR_STATUS.json')
def main():
 r=requests.get(URL,headers={'User-Agent':'DailyYieldPolicyMonitor/1.0'},timeout=45);r.raise_for_status()
 text=re.sub(r'\s+',' ',re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|<[^>]+>',' ',r.text,flags=re.I|re.S)).strip()
 digest=hashlib.sha256(text.encode()).hexdigest();prior={}
 try:prior=json.loads(OUT.read_text())
 except Exception:pass
 changed=bool(prior.get('official_text_sha256') and prior['official_text_sha256']!=digest)
 status={'status':'REVIEW_REQUIRED' if changed else 'PASS','checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'url':URL,'official_text_sha256':digest,'previous_sha256':prior.get('official_text_sha256',''),'wording_changed':changed,'note':'A hash change requires line-by-line human/policy review; it never auto-relaxes safeguards.'}
 OUT.write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status))
if __name__=='__main__':main()
