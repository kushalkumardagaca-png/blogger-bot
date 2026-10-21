# Google News and Discover readiness · 2026-10-21T21:00:14+00:00

- feed entries read: **18**, of which **6** have at least one listing defect
- pages inspected: **6**

| what is wrong | how many | why it matters |
| --- | --- | --- |
| clippedByOurTitleCap | 5 | headline stops exactly at this blog's own 46-character title limit: the limit, not Google, is what shortens it |
| noOpenGraphImage | 4 | the page has no og:image, so News and Discover have no picture to show |
| noHeadDescription | 4 | the page has no meta description in the head, so Google writes its own snippet |
| truncatedHeadline | 2 | headline ends on a fragment - a headline is what a News reader decides on |

## What to do with this

1. Fix the entries in this repository's own hands first - a headline that ends on a fragment is a bug we publish, not a Google decision (headline_repair.py already works through the backlog nightly).
2. Then submit the feed to Publisher Center with the section mapping the labels give us.
3. Then re-run this file: the gap counts should fall, and that is the proof - not a green tick in Actions.
