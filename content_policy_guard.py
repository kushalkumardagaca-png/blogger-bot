#!/usr/bin/env python3
"""Blogger December 2026 content-policy guardrails.

The guard does not try to disguise automation. It requires useful, distinct,
honestly attributed output and fails closed on deceptive, dangerous, private,
repetitive or commercially manipulative material.
"""
from __future__ import annotations
import html,os,re
from urllib.parse import urlparse,parse_qs
from collections import Counter

POLICY_VERSION="BLOGGER_CONTENT_POLICY_2026_12_GREEN_V2"
DISCLOSURE_MARKER="DY_AUTOMATION_DISCLOSURE_GREEN_V2"
# The one sentence every current piece of content carries, so a reader or a
# reviewer always has both monitored addresses in front of them.
FOOTER_CONTACT=("Report a correction or ask a question at dailyyield.official@gmail.com or "
 "kushalkumardaga.ca@gmail.com; both inboxes are monitored and replies take usually "
 "within 2–3 working days. ")
# The byline is an abbreviation of the publisher's legal name, not a second person.
FOOTER_NAME_NOTE=("Daily Yield is written and published by Kushal Daga, the short form of the "
 "publisher's legal name, Kushal Kumar Daga, which is the name used on ownership, payment "
 "and platform records. ")

# These phrases are acceptable only when expressly negated or quoted as a risk.
DECEPTIVE_PATTERNS=(
 r"\bguaranteed\s+(?:return|profit|income|approval|win)s?\b",
 r"\brisk[- ]free\s+(?:investment|profit|return|income)\b",
 r"\b(?:double|triple)\s+your\s+money\b",
 r"\bget\s+rich\s+quick\b",
 r"\bzero\s+risk\b",
 r"\bsecret\s+(?:loophole|system)\s+(?:banks|governments|experts)\s+do(?:n['’]t| not)\s+want\s+you\s+to\s+know\b",
)
FAKE_EXPERIENCE_PATTERNS=(
 r"\bI\s+(?:personally\s+)?(?:tested|used|bought|invested in|earned from|made money from)\b",
 r"\bwe\s+(?:personally\s+)?(?:tested|used|bought|invested in|earned from|made money from)\b",
)
REGULATED_PROMOTION_PATTERNS=(
 r"\b(?:buy|order|shop|sign up for)\b.{0,35}\b(?:tobacco|vape|weapon|firearm|illegal drug|unapproved supplement)\b",
 r"\b(?:best|recommended|join|deposit at)\b.{0,25}\b(?:casino|sportsbook|betting site)\b",
)
DANGEROUS_PATTERNS=(
 r"\bhow to\s+(?:phish|steal credentials|evade sanctions|launder money|make a bomb)\b",
 r"\bdownload\s+(?:this\s+)?(?:malware|ransomware|credential stealer)\b",
)
# Strict formats reduce false positives in ordinary financial reporting.
PRIVATE_DATA_PATTERNS=(
 ("US Social Security number",r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
 # Aadhaar-like formatting is evaluated with nearby identity context below;
 # financial examples commonly contain unrelated 4-4-4 grouped figures.
 ("private key",r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
REPETITIVE_FALLBACK_PHRASES=(
 "This passage is used only for its documented scope, while unsupported predictions and recommendations remain outside this section.",
 "The cited record is one bounded part of the evidence and cannot support broader certainty.",
 "The record establishes context, not a universal forecast, causal conclusion or personal recommendation.",
)
NEGATION_WORDS=("not ","no ","never ","avoid ","warning","scam","fraud","false","misleading","does not")


def plain(value:str)->str:
 value=re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>"," ",value or "",flags=re.I|re.S)
 return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",value))).strip()

def sentences(value:str)->list[str]:
 text=plain(value)
 return [x.strip() for x in re.split(r"(?<=[.!?])\s+",text) if len(re.findall(r"[A-Za-z][A-Za-z'’\-]*",x))>=10]

def normalize_sentence(value:str)->str:
 value=re.sub(r"https?://\S+"," ",value.casefold())
 value=re.sub(r"\[\[s\d+\|[^]]+\]\]"," ",value)
 return re.sub(r"[^a-z0-9]+"," ",value).strip()

def _affirmative_match(text:str,pattern:str)->bool:
 for match in re.finditer(pattern,text,flags=re.I|re.S):
  lead=text[max(0,match.start()-70):match.start()].casefold()
  if not any(word in lead for word in NEGATION_WORDS):return True
 return False

def _luhn_valid(value:str)->bool:
 """Return true only for a structurally plausible payment-card number.

 Financial articles commonly place many unrelated figures next to one another. A
 bare digit-count regex therefore creates false privacy alarms; Luhn validation
 preserves the fail-closed gate for actual card-like identifiers.
 """
 digits=re.sub(r"\D","",value)
 if not 13<=len(digits)<=19 or len(set(digits))==1:return False
 total=0
 for index,char in enumerate(reversed(digits)):
  number=int(char)
  if index%2:number=number*2-9 if number>4 else number*2
  total+=number
 return total%10==0

def audit_text(title:str,content:str,channel:str="blog",require_disclosure:bool=False)->list[str]:
 text=plain(content);issues=[]
 for pattern in DECEPTIVE_PATTERNS:
  if _affirmative_match(text,pattern):issues.append("deceptive financial or commercial promise")
 for pattern in FAKE_EXPERIENCE_PATTERNS:
  if re.search(pattern,text,re.I):issues.append("unsupported first-person product or investment experience")
 for pattern in REGULATED_PROMOTION_PATTERNS:
  if re.search(pattern,text,re.I|re.S):issues.append("promotion of a regulated or prohibited product")
 for pattern in DANGEROUS_PATTERNS:
  if re.search(pattern,text,re.I):issues.append("dangerous or illegal facilitation language")
 for name,pattern in PRIVATE_DATA_PATTERNS:
  if re.search(pattern,text,re.I):issues.append("possible exposed "+name)
 for match in re.finditer(r"(?<!\d)[2-9]\d{3}[ -]\d{4}[ -]\d{4}(?!\d)",text):
  context=text[max(0,match.start()-80):match.end()+80]
  if re.search(r"\b(?:aadhaar|identity|identification|id number)\b",context,re.I):issues.append("possible exposed Indian Aadhaar-like number")
 card_candidates=re.findall(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)",text)
 if any(_luhn_valid(candidate) for candidate in card_candidates):
  issues.append("possible exposed payment-card-like number")
 for phrase in REPETITIVE_FALLBACK_PHRASES:
  if phrase.casefold() in text.casefold():issues.append("repetitive deterministic fallback sentence")
 qualification=r"(?:Certified Accountant|Chartered Accountant|CPA|CFA|licensed financial adviser|registered investment adviser)"
 if re.search(r"(?:Kushal(?: K\. Daga)?|the author|the publisher|\bI am\b|\bwe are\b).{0,55}\b"+qualification+r"\b",text,re.I) and os.environ.get("DY_VERIFIED_PROFESSIONAL_QUALIFICATION","").casefold()!="true":
  issues.append("unverified professional qualification")
 # Rankings and testimonials are unusually risky in finance. A superlative
 # product/company title must include a visible methodology and commercial-
 # relationship statement; otherwise it can resemble a fake review.
 if re.search(r"\bbest\b.{0,45}\b(?:compan(?:y|ies)|bank|broker|insurer|insurance|card|loan|app|platform|fund)s?\b",title or '',re.I):
  if not re.search(r"\b(?:selection|comparison|ranking) methodology\b",text,re.I) or not re.search(r"\b(?:no paid placement|not a paid ranking|commercial relationship|affiliate compensation)\b",text,re.I):issues.append("unsupported financial ranking or fake-review risk")
 # Encoded Google News IDs can coincidentally contain "affid". Only actual
 # parsed affiliate query parameters establish this mechanical signal.
 affiliate_links=[]
 for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)',content or '',flags=re.I):
  query=parse_qs(urlparse(html.unescape(href)).query)
  if any(k.casefold() in ('aff_id','affid','affiliate','affiliate_id','referral') for k in query) or any(v.casefold()=='affiliate' for k,values in query.items() if k.casefold()=='utm_medium' for v in values):affiliate_links.append(href)
 if affiliate_links and not re.search(r"\b(?:affiliate|commercial relationship|paid placement|commission)\b",text,re.I):issues.append("undisclosed affiliate or commercial link")
 # Seamless carousels may contain an accessibility-hidden clone of visible cards.
 # Scan the full text for harmful material, but do not count that non-reader clone
 # as repeated editorial prose.
 # A licence credit is not editorial prose either: the same photographer, licence and source sentence
 # belong on every figure of a series by design, and the first article scrubbed to satisfy this
 # measurement shipped with two empty captions (22 October 2026). That blank credit failed the
 # whole-site image-rights audit, and the green operating gate then held every desk and every Master
 # slot on 23 October. Harmful-language patterns are still read across the whole page - only the
 # repetition count stops treating an attribution as duplicated reporting.
 repetition_content=content or ''
 for pattern in (r'<figcaption\b[^>]*>.*?</figcaption\s*>',r'<div\b[^>]*aria-hidden=["\']true["\'][^>]*>.*?</div>',r'<div\b[^>]*class=["\'][^"\']*\bdy2-data\b[^"\']*["\'][^>]*>.*?</div>',r'<section\b[^>]*class=["\'][^"\']*\bdy2-links\b[^"\']*["\'][^>]*>.*?</section>',r'<a\b[^>]*class=["\'][^"\']*\b(?:fbk-src|dy-context|dy-related)\b[^"\']*["\'][^>]*>.*?</a>'):
  repetition_content=re.sub(pattern,' ',repetition_content,flags=re.I|re.S)
 seq=[normalize_sentence(x) for x in sentences(repetition_content)];seq=[x for x in seq if len(x.split())>=10]
 # This is an explicit background/date label, not substantive reporting. It
 # remains visible on each older item and is not removed to fake originality.
 # Likewise the exact image-rights disclaimer is repeated per photo on purpose;
 # it is a functional attribution notice, not duplicated financial analysis.
 date_labels={normalize_sentence(x) for x in ('It is separated from the current-period items so its date and role are clear.','This item is included only to provide context for the current desk.','Used as an illustration, not as evidence of the particular people, organisation or event discussed.')}
 substantive_seq=[s for s in seq if s not in date_labels]
 counts=Counter(substantive_seq);duplicates=[s for s,n in counts.items() if n>1 and len(s.split())>=12]
 if duplicates:issues.append("repeated substantive sentence within the content")
 if len(substantive_seq)>=12 and len(counts)/len(substantive_seq)<0.94:issues.append("insufficient sentence-level originality")
 for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)',content or '',flags=re.I):
  if re.match(r'\s*(?:javascript|vbscript|data):',html.unescape(href),re.I):issues.append('unsafe active link scheme')
 for src in re.findall(r'<script\b[^>]*src=["\']([^"\']+)',content or '',flags=re.I):
  if not re.match(r'https://(?:[^/]+\.)?(?:google\.com|gstatic\.com|blogger\.com|blogspot\.com)/',html.unescape(src),re.I):issues.append('unapproved external script host')
 if require_disclosure and DISCLOSURE_MARKER not in content:issues.append("transparent automation disclosure missing")
 # A byline is allowed, but automated output must never falsely claim personal review.
 if re.search(r"(?:personally|manually)\s+(?:reviewed|approved)\s+by\s+Kushal",text,re.I):issues.append("unsupported personal-review claim")
 return sorted(set(issues))

def assert_policy_compliant(title:str,content:str,channel:str="blog",require_disclosure:bool=False)->bool:
 issues=audit_text(title,content,channel,require_disclosure)
 if issues:raise RuntimeError("BLOGGER CONTENT POLICY GATE FAILED — "+"; ".join(issues))
 return True

def automation_disclosure(kind:str="article")->str:
 return f'''<!-- {DISCLOSURE_MARKER} --><aside class="dy-policy-disclosure" aria-label="Editorial process disclosure"><strong>How this {html.escape(kind)} was produced</strong><p>Daily Yield uses automated tools to assist source collection, drafting, validation, formatting, scheduling and distribution. The byline identifies the publisher responsible for the publication; it does not state that every automated draft was personally reviewed. {FOOTER_NAME_NOTE} Material claims must remain attributable to the linked sources. No paid placement or affiliate compensation is represented unless a specific disclosure says otherwise. {FOOTER_CONTACT[:-1]} Report abuse through Blogger’s Report Abuse link.</p></aside>'''

def assert_social_compliant(text:str)->bool:
 issues=audit_text("social post",text,"social",False)
 if len(re.findall(r"#[A-Za-z0-9_]+",text))>4:issues.append("excessive hashtagging")
 if re.search(r"\b(?:act now|limited time|don['’]t miss out|must buy)\b",text,re.I):issues.append("manufactured urgency")
 if issues:raise RuntimeError("SOCIAL CONTENT POLICY GATE FAILED — "+"; ".join(sorted(set(issues))))
 return True
