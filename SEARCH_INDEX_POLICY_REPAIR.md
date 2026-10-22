# Search index policy repair

**RESTORE** · inventory 79 live URLs · 79 title and alt-text repairs planned · 0 URL(s) to take down · 0 deliberately left alone
- written this run: **79** · failed: 0 · backup of everything touched: `SEARCH_INDEX_POLICY_REPAIR_BACKUP.json.gz`

| url | why |
|---|---|
| `https://dailyyield.blogspot.com/p/about-us_02080501126.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/article.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/calculator_0908148622.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/contact-us_01883938366.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/disclaimer.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/for-corporate_01804417406.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/money-atlas_01486068069.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/daily-news.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/privacy-policy.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/share-market_0718113516.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/09/run-recession-checklist-while-employed.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/markets-today.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/global-snapshot.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/p/terms-and-conditions.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01660061060.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/the-real-price-of-career-break.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01971481127.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01760479359.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0978730797.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0259378603.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/australia-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/south-korea-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/global-wire-top15-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/india-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-market-and-trading-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0694295104.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/germany-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/france-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/japan-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/uk-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/china-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/spain-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/italy-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_02075404004.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/us-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/canada-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/mexico-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/category-personal-finance-2026-10-07.html` | restored from the run's own backup |
| `https://dailyyield.blogspot.com/2026/10/russia-2026-10-07.html` | restored from the run's own backup |

## The limit of a repair like this

Titles, alt attributes and the removal of junk URLs are all mechanical, so they are fixed here. Two findings in the audit are content decisions and stay with the desk: the country editions that share one template, and the evergreen library's photo file names. Both have a gate in `index_policy_gate.py` now, so new posts cannot make the mistake again.
