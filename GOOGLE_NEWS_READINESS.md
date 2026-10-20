# Google News and Discover readiness · 2026-10-20T20:59:41+00:00

- feed entries read: **19**, of which **9** have at least one listing defect
- pages inspected: **6**

| what is wrong | how many | why it matters |
| --- | --- | --- |
| truncatedHeadline | 9 | headline ends on a fragment - a headline is what a News reader decides on |
| noOpenGraphImage | 6 | the page has no og:image, so News and Discover have no picture to show |
| noHeadDescription | 6 | the page has no meta description in the head, so Google writes its own snippet |

## What to do with this

1. Fix the entries in this repository's own hands first - a headline that ends on a fragment is a bug we publish, not a Google decision (headline_repair.py already works through the backlog nightly).
2. Then submit the feed to Publisher Center with the section mapping the labels give us.
3. Then re-run this file: the gap counts should fall, and that is the proof - not a green tick in Actions.
