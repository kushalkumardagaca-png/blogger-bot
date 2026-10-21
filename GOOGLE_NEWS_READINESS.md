# Google News and Discover readiness · 2026-10-21T11:47:44+00:00

- feed entries read: **20**, of which **6** have at least one listing defect
- pages inspected: **6**

| what is wrong | how many | why it matters |
| --- | --- | --- |
| truncatedHeadline | 3 | headline ends on a fragment - a headline is what a News reader decides on |
| clippedByOurTitleCap | 3 | headline stops exactly at this blog's own 46-character title limit: the limit, not Google, is what shortens it |

## What to do with this

1. Fix the entries in this repository's own hands first - a headline that ends on a fragment is a bug we publish, not a Google decision (headline_repair.py already works through the backlog nightly).
2. Then submit the feed to Publisher Center with the section mapping the labels give us.
3. Then re-run this file: the gap counts should fall, and that is the proof - not a green tick in Actions.
