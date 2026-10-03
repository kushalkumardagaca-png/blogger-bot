#!/usr/bin/env python3
"""Reader-first, source-led master article builder.

No fake personal experience, invented quotation, universal claim or hidden
'AI detector' trick. Variation comes from the subject, decision lens, evidence,
worked assumptions and structure—not cosmetic synonym swapping.
"""
from __future__ import annotations
import hashlib, html, json, math, re
from seo_hygiene import compact_title, repair_image_alts
from seo_meta import ensure_seo_meta

BLOG='https://dailyyield.blogspot.com'
AUTHOR='Kushal K. Daga'

LENSES={
 'debt':{
  'match':('Credit Debt','Middle Class','Cash Savings'),
  'question':'Which obligation or cash-flow gap is costing the household the most each month?',
  'measure':'interest cost, minimum-payment drag and months of essential expenses covered',
  'risk':'A plan can look efficient on a spreadsheet and still fail when income is interrupted or a variable rate resets.',
  'actions':['List every balance, rate, minimum and due date in one place.','Protect a starter cash buffer before making an irreversible lump-sum payment.','Direct extra cash to the highest effective rate unless a small-balance win is needed to sustain the plan.','Review the plan after any rate, income or household change.'],
  'sources':[('Consumer Financial Protection Bureau','https://www.consumerfinance.gov/consumer-tools/debt-collection/'),('Federal Trade Commission','https://consumer.ftc.gov/articles/how-get-out-debt'),('Reserve Bank of India financial education','https://www.rbi.org.in/FinancialEducation/Home.aspx')]
 },
 'investing':{
  'match':('Investing','Passive Income','Rich Habits','2026 Money','Real Estate'),
  'question':'What return is actually required, and what risk must the reader accept to pursue it?',
  'measure':'fees, diversification, time horizon, liquidity and the size of a tolerable loss',
  'risk':'A historical average is not a promise. Sequence risk, taxes, fees and a forced early sale can dominate the headline return.',
  'actions':['Write down the goal, date and amount before selecting a product.','Separate emergency cash from long-horizon capital.','Compare total fees and diversification rather than recent performance alone.','Choose a review rule in advance instead of reacting to headlines.'],
  'sources':[('Investor.gov diversification guide','https://www.investor.gov/introduction-investing/investing-basics/glossary/diversification'),('FINRA Fund Analyzer','https://tools.finra.org/fund_analyzer/'),('OECD financial education','https://www.oecd.org/financial/education/')]
 },
 'retirement':{
  'match':('Retirement','Age and Wealth'),
  'question':'How much future spending must today’s savings support, and for how long?',
  'measure':'savings rate, retirement horizon, inflation, fees and withdrawal flexibility',
  'risk':'One optimistic return assumption can hide a large funding gap. Retirement planning needs ranges, not a single magic number.',
  'actions':['Estimate essential and optional retirement spending separately.','Run low, middle and high return assumptions after fees.','Check beneficiary, nomination and account-consolidation details.','Revisit the plan annually and after major life changes.'],
  'sources':[('OECD pensions resources','https://www.oecd.org/pensions/'),('Investor.gov compound interest calculator','https://www.investor.gov/financial-tools-calculators/calculators/compound-interest-calculator'),('International Labour Organization social protection','https://www.ilo.org/topics-and-sectors/social-protection')]
 },
 'work':{
  'match':('Career Salary','Side Hustles','Starters Students'),
  'question':'Does the opportunity improve durable take-home income after time, tax, volatility and out-of-pocket cost?',
  'measure':'net hourly value, income stability, skill portability and downside if the opportunity ends',
  'risk':'Gross income can be a poor measure when unpaid time, equipment, travel, tax and inconsistent demand are ignored.',
  'actions':['Calculate net income after direct costs and a reasonable tax reserve.','Track the real hours spent, including administration and travel.','Prefer skills and customer relationships that remain useful if one platform disappears.','Set a stop rule before investing more money.'],
  'sources':[('International Labour Organization wages','https://www.ilo.org/topics-and-sectors/wages'),('OECD employment data','https://www.oecd.org/employment/'),('Consumer Financial Protection Bureau budgeting','https://www.consumerfinance.gov/consumer-tools/budgeting/')]
 },
 'household':{
  'match':('Housing Cars','Spending Lifestyle','Couples Family','Insurance','Money Psychology'),
  'question':'What recurring commitment does this decision create, and what flexibility does the household lose?',
  'measure':'total ownership cost, recurring cash flow, insurance exposure and the cost of reversing the decision',
  'risk':'The purchase price is often the smallest visible number; financing, maintenance, tax, insurance and lost flexibility continue afterward.',
  'actions':['Convert every recurring cost to an annual figure.','Include maintenance, tax, insurance and transaction costs.','Test the budget against a temporary income reduction.','Agree in advance on the condition that would trigger a change.'],
  'sources':[('CFPB home buying resources','https://www.consumerfinance.gov/owning-a-home/'),('NAIC consumer insurance information','https://content.naic.org/consumer'),('OECD consumer policy','https://www.oecd.org/consumer/')]
 },
 'tax':{
  'match':('Taxes and Account','Automation and Money'),
  'question':'Which part of the process can be simplified without assuming that one country’s tax rule applies everywhere?',
  'measure':'after-tax outcome, documentation, deadlines, fees and the cost of an incorrect assumption',
  'risk':'Tax rules are local and change over time. A useful framework must separate arithmetic from jurisdiction-specific eligibility.',
  'actions':['Identify the country and tax year before applying a rule.','Use official guidance for limits, dates and eligibility.','Keep records supporting each deduction, contribution or election.','Use a qualified adviser when the decision is material or cross-border.'],
  'sources':[('OECD tax resources','https://www.oecd.org/tax/'),('Income Tax Department India','https://www.incometax.gov.in/iec/foportal/'),('HM Revenue & Customs','https://www.gov.uk/government/organisations/hm-revenue-customs')]
 },
 'safety':{
  'match':('Myths Scams','AI Fintech','Recessions Crashes'),
  'question':'What evidence would have to be true before a reader should trust the claim or transfer money?',
  'measure':'source identity, regulatory status, fees, withdrawal rights and the maximum loss',
  'risk':'Urgency, certainty and secrecy are warning signs. A polished interface does not prove that a product, adviser or return is legitimate.',
  'actions':['Pause before paying and verify the entity through an official register.','Search the exact claim and contact details independently.','Never share an OTP, remote-access code or wallet recovery phrase.','Use a separate channel to confirm any urgent payment request.'],
  'sources':[('Federal Trade Commission scam guidance','https://consumer.ftc.gov/scams'),('Investor.gov fraud resources','https://www.investor.gov/protect-your-investments/fraud'),('Reserve Bank of India safe digital banking','https://www.rbi.org.in/commonperson/English/Scripts/SMSLimitedliability.aspx')]
 },
 'audit':{
  'match':('Money Audits','Contrarian Hooks'),
  'question':'Which claim can be reconstructed from records, and what evidence would reverse the conclusion?',
  'measure':'documented cash flow, comparison period, omitted costs and sensitivity to changed assumptions',
  'risk':'A striking conclusion may disappear when the comparison period, fees or missing household obligations are restored.',
  'actions':['Define the claim in a form that can be tested.','Collect statements and receipts for the same comparison period.','Separate observed figures from estimates.','Run the calculation again with the strongest reasonable counter-assumption.'],
  'sources':[('Consumer Financial Protection Bureau budgeting','https://www.consumerfinance.gov/consumer-tools/budgeting/'),('OECD financial education','https://www.oecd.org/financial/education/'),('Investor.gov research resources','https://www.investor.gov/introduction-investing/getting-started/research-investments')]
 },
 'general':{
  'match':(),
  'question':'What decision is the reader trying to make, and which number would change that decision?',
  'measure':'cash-flow effect, opportunity cost, uncertainty and reversibility',
  'risk':'A universal rule can be misleading when income stability, country, household obligations and time horizon differ.',
  'actions':['State the decision in one sentence.','Separate known numbers from assumptions.','Compare at least two realistic alternatives.','Set a date to review the result.'],
  'sources':[('Consumer Financial Protection Bureau','https://www.consumerfinance.gov/consumer-tools/'),('OECD financial education','https://www.oecd.org/financial/education/'),('Investor.gov','https://www.investor.gov/')]
 }
}

def lens_for(category):
 normalized=re.sub(r'[^a-z0-9]+',' ',category.casefold().replace('&',' and ')).strip()
 for key,lens in LENSES.items():
  if key!='general' and any(re.sub(r'[^a-z0-9]+',' ',x.casefold().replace('&',' and ')).strip() in normalized for x in lens['match']):return key,lens
 return 'general',LENSES['general']

def esc(x):return html.escape(str(x),quote=True)
def slugify(title):return re.sub(r'[^a-z0-9]+','-',title.casefold()).strip('-')

def worked_example(key,seed):
 if key in ('investing','retirement'):
  monthly=(100,150,200,250,300,400,500)[seed%7];years=(3,5,7,10,12,15)[(seed//7)%6];rate=(.04,.05,.06,.07)[(seed//13)%4];months=years*12
  future=monthly*((1+rate/12)**months-1)/(rate/12);contrib=monthly*months
  text=(f'This is an illustration, not a forecast. Assume {monthly} currency units are contributed monthly for {years} years and test a {rate*100:.0f}% annual return before tax and fees. Contributions total {contrib:,.0f}; the formula FV = payment × (((1 + monthly rate)^months − 1) ÷ monthly rate) gives about {future:,.0f}. At 0%, the result is {contrib:,.0f}.')
  rows=[('Monthly contribution',monthly),('Period',f'{years} years'),('Test return',f'{rate*100:.0f}% before tax and fees'),('Contributions',f'{contrib:,.0f}'),('Modeled value',f'{future:,.0f}')]
 elif key=='debt':
  balance=(2400,3600,5000,7200)[seed%4];apr=(.12,.18,.24)[(seed//5)%3];payment=(150,200,300)[(seed//11)%3];monthly_interest=balance*apr/12;principal=max(0,payment-monthly_interest)
  text=(f'Assume a balance of {balance:,.0f} currency units at {apr*100:.0f}% APR and a {payment} monthly payment. The first month’s approximate interest is balance × APR ÷ 12 = {monthly_interest:,.0f}; about {principal:,.0f} of that payment reduces principal before fees. This is a one-month illustration, not a payoff quote; daily interest, fees and new spending can change it.')
  rows=[('Starting balance',f'{balance:,.0f}'),('APR',f'{apr*100:.0f}%'),('Monthly payment',payment),('Approx. first-month interest',f'{monthly_interest:,.0f}'),('Approx. principal reduction',f'{principal:,.0f}')]
 elif key=='work':
  gross=(500,800,1200)[seed%3];costs=(80,160,240)[(seed//3)%3];hours=(20,35,50)[(seed//7)%3];reserve=.20;net=gross-costs-gross*reserve;hourly=net/hours
  text=(f'Assume a project pays {gross} currency units, needs {hours} total hours, costs {costs}, and sets aside {reserve*100:.0f}% of gross pay for possible tax. The planning remainder is gross − costs − reserve = {net:,.0f}, or {hourly:,.2f} per hour. Actual tax depends on jurisdiction and personal circumstances.')
  rows=[('Gross pay',gross),('Direct costs',costs),('Tax reserve',f'{gross*reserve:,.0f}'),('Total hours',hours),('Planning net per hour',f'{hourly:,.2f}')]
 elif key=='household':
  price=(12000,18000,25000)[seed%3];years=(3,5,7)[(seed//3)%3];annual=(1200,1800,2400)[(seed//7)%3];total=price+years*annual
  text=(f'Assume a purchase price of {price:,.0f} currency units and recurring insurance, maintenance and fees of {annual:,.0f} a year for {years} years. A simple ownership baseline is price + annual costs × years = {total:,.0f}, before financing, resale value and opportunity cost. The purpose is to expose recurring costs, not estimate a particular asset.')
  rows=[('Purchase price',f'{price:,.0f}'),('Recurring annual costs',f'{annual:,.0f}'),('Holding period',f'{years} years'),('Simple cash-cost baseline',f'{total:,.0f}'),('Excluded','financing, resale value, opportunity cost')]
 elif key=='tax':
  income=(30000,50000,80000)[seed%3];rate=(.10,.20,.30)[(seed//5)%3];eligible=(1000,2000,3000)[(seed//11)%3];saving=eligible*rate
  text=(f'For arithmetic only, assume taxable income of {income:,.0f}, a {rate*100:.0f}% marginal rate and a genuinely eligible deduction of {eligible:,.0f}. The rough tax effect is deduction × marginal rate = {saving:,.0f}, not the full deduction. Eligibility, caps and treatment must be checked for the reader’s country and tax year.')
  rows=[('Illustrative taxable income',f'{income:,.0f}'),('Illustrative marginal rate',f'{rate*100:.0f}%'),('Assumed eligible deduction',f'{eligible:,.0f}'),('Rough tax effect',f'{saving:,.0f}'),('Must verify','country, year, eligibility and caps')]
 elif key=='safety':
  requested=(500,1000,2500)[seed%3];recoverable=0
  text=(f'Assume an unverified sender requests {requested:,.0f} currency units and promises urgency or an unusually certain return. The safe planning assumption is that the full {requested:,.0f} could be lost and recovery could be zero. No return calculation is appropriate until identity, authorization, fees and withdrawal rights are independently verified.')
  rows=[('Amount requested',f'{requested:,.0f}'),('Amount at risk',f'up to {requested:,.0f}'),('Assumed recoverable amount',recoverable),('Promised return','not used before verification'),('Decision threshold','independent verification first')]
 else:
  monthly=(100,200,300)[seed%3];months=(6,9,12)[(seed//5)%3];total=monthly*months
  text=(f'Assume a decision changes monthly cash flow by {monthly} currency units for {months} months. The direct cash commitment is monthly change × months = {total:,.0f}, before tax, fees or secondary effects. This simple baseline helps readers identify which missing assumption deserves research.')
  rows=[('Monthly cash-flow change',monthly),('Duration',f'{months} months'),('Direct commitment',f'{total:,.0f}'),('Tax and fees','not yet included'),('Next step','replace assumptions with records')]
 return text,''.join(f'<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>' for a,b in rows)

def build(topic,pub_date,pub_time,hero):
 category=topic['Category'];title=compact_title(topic['Punchy Title']);desc=re.sub(r'\s+',' ',topic.get('Video Description','')).strip();idea=re.sub(r'\s+',' ',topic.get('Video Idea','')).strip()
 slug=slugify(title);key,lens=lens_for(category);seed=int(hashlib.sha256((title+category).encode()).hexdigest()[:8],16)
 example_context,example_rows=worked_example(key,seed)
 headings=[('Start with the decision, not the slogan','Put the numbers on one page','What the example proves—and what it cannot','A practical decision framework','Where this advice can fail','A seven-day checklist'),('The question underneath the headline','Build a transparent baseline','Read the result carefully','How to make the decision','Important exceptions','What to do this week'),('Why this topic is easy to misread','An example with visible assumptions','The useful takeaway','A repeatable process','Limits and trade-offs','Reader action list')][seed%3]
 openings=[f"{title} sounds like a conclusion, but a reader needs a decision process. The useful starting point is not a promise of a better outcome; it is a clear account of what changes, what it costs and what could go wrong.",f"Most money decisions become confusing when the headline arrives before the arithmetic. For {title.lower()}, the first job is to separate the reader's goal from the product, habit or shortcut being discussed.",f"There is no single answer to {title.lower()}. Income stability, country, debt, family obligations and time horizon can change the result. What follows is a framework readers can test with their own numbers."][seed%3]
 source_list=''.join(f'<li><a href="{esc(url)}" rel="noopener" target="_blank">{esc(name)}</a> — primary or specialist reference used to check the framework.</li>' for name,url in lens['sources'])
 action_list=''.join(f'<li>{esc(x)}</li>' for x in lens['actions'])
 meta=(desc or f'A practical, sourced decision framework for {title}.')[:155].rstrip(' .')+'.'
 labels=[category,'Kushal K. Daga']
 url=f"{BLOG}/{pub_date[:7].replace('-','/')}/{slug}.html"
 faq=[(f"What is the first number to check for {title}?",f"Start with {lens['measure']}. Use household-specific figures and write down every assumption."),(f"What is the main limitation of this framework?",lens['risk']),(f"How often should the decision be reviewed?","Review it when rates, income, law, family obligations or the goal changes, and at least once a year for a long-term plan.")]
 schema={'@context':'https://schema.org','@graph':[{'@type':'BlogPosting','@id':url+'#article','url':url,'mainEntityOfPage':{'@type':'WebPage','@id':url},'headline':title,'description':meta,'articleSection':category,'inLanguage':'en','author':{'@type':'Person','name':AUTHOR,'url':BLOG+'/p/about-us_02080501126.html','sameAs':['https://www.linkedin.com/in/dailyyeild']},'publisher':{'@type':'Organization','name':'Daily Yield','url':BLOG+'/'},'datePublished':f'{pub_date}T{pub_time}:00+05:30','dateModified':f'{pub_date}T{pub_time}:00+05:30'},{'@type':'FAQPage','mainEntity':[{'@type':'Question','name':q,'acceptedAnswer':{'@type':'Answer','text':a}} for q,a in faq]}]}
 css='''.dyv{max-width:920px;margin:auto;color:#17231d;line-height:1.72;font:17px Georgia,serif}.dyv h1,.dyv h2{font-family:Arial,sans-serif;color:#073b2b}.dyv h1{font-size:clamp(32px,6vw,56px);line-height:1.08}.dyv h2{margin-top:34px;font-size:clamp(23px,4vw,32px)}.dyv .lead{font-size:20px;color:#46534d}.dyv .note,.dyv .example{padding:18px;border-radius:14px;background:#f2f8f5;border:1px solid #d8e8df}.dyv table{width:100%;border-collapse:collapse}.dyv th,.dyv td{padding:10px;border:1px solid #d8e2dc;text-align:left}.dyv a{color:#08744f}.dyv .by{font:13px Arial,sans-serif;color:#65716b}.dyv li{margin:8px 0}@media(max-width:640px){.dyv{font-size:16px}.dyv table{font-size:13px}}'''
 interpretation=[
  f"The value of this example is its audit trail: every result can be traced to an input. It cannot show that a product or method will deliver the modeled outcome. Recalculate after fees, taxes, delays and a deliberately unfavorable case. {lens['risk']}",
  f"Read the table from inputs to result, not backward from the most attractive number. None of the assumptions is a prediction. Ask whether the choice still works after a cost increase, an income interruption or a longer timetable. The main caution for this topic is straightforward: {lens['risk']}",
  f"The arithmetic creates a baseline, not a recommendation. Its useful question is how sensitive the answer is to one changed input. Replace estimates with records, rerun the weaker case and reject any conclusion that needs unexplained precision. In this area, {lens['risk']}"
 ][seed%3]
 process=[
  f"Compare at least two choices. Record the immediate cash effect, recurring commitment, largest uncertainty and exit cost for each. Rank them using {lens['measure']}. Unknown fees or rules stay marked unknown until a primary document resolves them.",
  f"Work backward from the decision date. Identify what must be known, what can remain an estimate and which mistake would be hardest to reverse. Then compare the status quo with one simpler alternative using {lens['measure']}. A precise score should never conceal missing evidence.",
  f"Use a one-page decision record: objective, alternatives, known figures, assumptions, downside and review trigger. For this subject the most revealing measures are {lens['measure']}. Prefer the option that remains workable under a realistic setback, not merely the option with the largest best case."
 ][(seed//3)%3]
 application=[
  f"Apply this topic's proposed idea—{idea}—to one live decision. Start by asking: {lens['question']} Collect matching-period records and mark every figure observed, quoted or assumed.",
  f"The practical test of {title} is whether a reader can reproduce it with household records. Use this question to begin: {lens['question']} Translate {idea} into a dated choice with a base case and a weaker case.",
  f"Do not apply {title} to an imaginary average person. Choose a real amount and deadline, then ask: {lens['question']} The working idea is {idea}; it should survive replacement of convenient estimates with documented figures."
 ][(seed//9)%3]
 body=f'''<article class="dyv"><style>{css}</style><header><p class="by">{esc(category)} · By <strong>{AUTHOR}</strong> · Published {pub_date} · Educational content</p><h1>{esc(title)}</h1><p class="lead">{esc(desc)}</p></header>{hero}<section><h2>{headings[0]}</h2><p>{esc(openings)}</p><p>{esc(idea)} That idea becomes useful only after it is translated into a measurable choice. For this topic, ask: <strong>{esc(lens['question'])}</strong></p><p>The core measures are {esc(lens['measure'])}. They are deliberately ordinary. Readers can verify them from statements, account documents and household records rather than relying on a dramatic prediction.</p></section><section><h2>{headings[1]}</h2><div class="example"><p><strong>Worked example with disclosed assumptions.</strong> {esc(example_context)}</p></div><table><caption>Illustrative scenario—not a promised outcome</caption><tr><th>Input</th><th>Assumption</th></tr>{example_rows}</table><p>Readers should replace every input with their own figures and also test a worse case. If the decision fails when return is lower, income pauses or costs rise, the plan needs more margin.</p></section><section><h2>{headings[2]}</h2><p>{esc(interpretation)}</p><p>A sound conclusion identifies the downside, the continuing cost and the evidence that would cause a review. Write those conditions beside the result instead of treating the result as permanent.</p></section><section><h2>{headings[3]}</h2><p>{esc(process)}</p><p>For <strong>{esc(title)}</strong>, keep the chosen action beside the number that justified it. That record makes a later correction possible when the evidence changes.</p></section><section><h2>{headings[4]}</h2><p>The principal risk has already been stated beside the calculation; now test whether that risk would make the choice unaffordable, irreversible or unsuitable for the reader's deadline.</p><p>The calculation above answers only what follows from its stated inputs. For this subject, test {esc(lens['measure'])}. Country, product and household details must come from current records; where an error is expensive or difficult to reverse, use an appropriately qualified professional. Before relying on the conclusion about {esc(title)}, note the date, jurisdiction, document version and unresolved assumption in the same decision record.</p></section><section><h2>Evidence and further reading</h2><p>These references are provided so readers can inspect primary or specialist guidance rather than accepting the article on authority:</p><ul>{source_list}</ul><p>Source links do not imply that an agency endorses Daily Yield. Publication dates and limits should be checked on the linked official pages. For current context, readers can also use Daily Yield's <a href="/p/markets-today.html">Markets Today</a> and <a href="/p/global-snapshot.html">Global Snapshot</a>; those pages are context tools, not evidence for the worked assumptions above.</p></section><section><h2>{headings[5]}</h2><p>{esc(application)}</p><ol>{action_list}</ol><p>After using real figures, change the weakest assumption and calculate again. Compare the answer with doing nothing and with one simpler alternative. Tie the review to a relevant event—such as a rate reset, renewal, income change or official rule update—so the plan responds to evidence rather than noise.</p></section><section><h2>Questions readers often ask</h2>{''.join(f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q,a in faq)}</section><section class="note"><h2>Editorial method</h2><p>This article separates sourced guidance, transparent arithmetic and editorial interpretation. For {esc(title)}, the description and proposed idea define the scope; the worked example exposes its inputs; the downside section challenges the result; and the linked references let readers inspect relevant public guidance. No source is presented as endorsing Daily Yield. The article does not contain a testimonial, undocumented personal experience or a claim that one result fits every reader. Figures remain illustrative until replaced with dated household records and current product or official documents. Corrections can be sent to <a href="mailto:dailyyield.official@gmail.com">dailyyield.official@gmail.com</a>.</p></section><p class="by"><strong>Important:</strong> Educational information only; not personalised financial, tax, investment, credit or legal advice.</p></article><script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script>'''
 body,_=repair_image_alts(body,title);body=ensure_seo_meta(body,title,meta)
 return title,slug,meta,labels,body
