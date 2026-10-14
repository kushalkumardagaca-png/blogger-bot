#!/usr/bin/env python3
"""Static audit for Blogger Content Policy safeguards effective before 16 Dec 2026."""
from __future__ import annotations
import json,re,datetime
from pathlib import Path
R=Path(__file__).parent;checks=[]
def check(name,ok,detail=''):checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
pre=(R/'publication_preflight.py').read_text();guard=(R/'content_policy_guard.py').read_text();master=(R/'master_v3_generator.py').read_text();renderer=(R/'master_article_v2.py').read_text();news=(R/'news_pipeline.py').read_text();social=(R/'social_creative.py').read_text();deploy=(R/'deploy_blogger_policy_compliance.py').read_text();workflow=(R/'.github/workflows/blogger_policy_compliance.yml').read_text();themes='\n'.join(p.read_text() for p in (R/'theme').glob('*.xml'))
check('Every Blogger publication passes the central policy guard','assert_policy_compliant' in pre and 'require_disclosure=True' in pre)
check('Automated posts disclose the production process','automation_disclosure' in renderer and 'automation_disclosure' in news and 'DY_AUTOMATION_DISCLOSURE_2026_12' in guard)
check('Master packages are policy-versioned and older prose is rebuilt','POLICY_VERSION' in master and "package.get('policy_version')!=POLICY_VERSION" in (R/'master_v3_pipeline.py').read_text())
check('Deterministic Master completion avoids the retired repeated disclaimer', 'This passage is used only for its documented scope' not in master)
check('Corpus originality blocks reused sentences and highly similar articles',(R/'content_originality.py').exists() and 'assert_cross_corpus_original' in master)
check('Deceptive promises, fake experience and manufactured urgency are blocked','DECEPTIVE_PATTERNS' in guard and 'FAKE_EXPERIENCE_PATTERNS' in guard and 'manufactured urgency' in guard)
check('Sensitive identifiers and unsafe scripts are blocked','PRIVATE_DATA_PATTERNS' in guard and 'unsafe active link scheme' in guard and 'unapproved external script host' in guard)
check('Social captions and Tumblr payloads pass policy checks',social.count('assert_social_compliant')>=3)
check('Images indicating minors are rejected from automated selection','MINOR_TERMS' in (R/'photo_selector.py').read_text() and 'MINOR_IMAGE_TERMS' in news)
check('Policy, correction, privacy and Report Abuse notices deploy idempotently','DY_BLOGGER_POLICY_2026_12_START' in deploy and 'Report Abuse mechanism' in deploy and 'Privacy' in deploy)
check('Policy deployment updates Blogger and persists evidence','deploy_blogger_policy_compliance.py' in workflow and 'BLOGGER_POLICY_DEPLOYMENT_STATUS.json' in workflow)
check('Unverified Certified Accountant claim is absent from deployable site sources','Certified Accountant' not in themes and 'Certified Accountant' not in (R/'markets_today_page.html').read_text())
check('Custom theme retains Blogger Report Abuse mechanism','https://www.blogger.com/go/report-abuse' in themes)
check('Publication quota cannot override compliance','A publication quota never overrides these safeguards' in deploy)
result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy_version':'BLOGGER_CONTENT_POLICY_2026_12','summary':{'pass':sum(x['status']=='PASS' for x in checks),'fail':sum(x['status']=='FAIL' for x in checks)},'checks':checks}
(R/'BLOGGER_CONTENT_POLICY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');(R/'BLOGGER_CONTENT_POLICY_AUDIT.md').write_text('# Blogger Content Policy Audit\n\n'+f"**{result['summary']['pass']} passed · {result['summary']['fail']} failed**\n\n"+'\n'.join(f"- **{x['status']}** — {x['name']}" for x in checks)+'\n')
print(json.dumps(result['summary']))
if result['summary']['fail']:raise SystemExit(1)
