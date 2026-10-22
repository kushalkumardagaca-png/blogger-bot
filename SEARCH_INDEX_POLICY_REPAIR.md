# Search index policy repair

**AUDIT_ONLY** · inventory 602 live URLs · 0 title and alt-text repairs planned · 0 URL(s) to take down · 42 deliberately left alone
- written this run: **0** · failed: 0 · backup of everything touched: `none (audit only)`

| url | why |
|---|---|

## Left alone on purpose

- `https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-12_01065225874.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18_01443792159.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0271866575.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01140619784.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0512615699.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01450325346.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01559215980.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_02014784419.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01893468813.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0558819666.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/canada-2026-10-01_0922194937.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_02023327578.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0777916234.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_02075404004.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0259378603.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0978730797.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01760479359.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01971481127.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01660061060.html` — held back: other automation links to this URL, so taking it down would break a live reference
- `https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_01348401010.html` — left alone: the two copies no longer say the same thing (45% alike), so this is an edition rather than a duplicate

## The limit of a repair like this

Titles, alt attributes and the removal of junk URLs are all mechanical, so they are fixed here. Two findings in the audit are content decisions and stay with the desk: the country editions that share one template, and the evergreen library's photo file names. Both have a gate in `index_policy_gate.py` now, so new posts cannot make the mistake again.
