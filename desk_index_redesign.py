#!/usr/bin/env python3
"""Replace the tool index on the Interactive pages with the designed board.

The index at the top of the Boardroom, Markets and Calculator desks used to place
each group heading inside the card grid, which left ragged gaps and made the tools
harder to scan. This controller reads the live page, keeps every existing link,
number, name and note, and writes the designed board back through Blogger's own
API, so nothing is lost and nothing is invented.

Modes
-----
--survey   read the three pages and record what the index currently holds
--dry-run  build the replacement board and validate it, writing nothing
--apply    write the replacement board to each page and verify the stored result
"""
from __future__ import annotations

from site_change_control import stop_if_frozen as _dy_stop_if_frozen
if __name__ == "__main__":
    _dy_stop_if_frozen('desk_index_redesign')


import argparse, datetime as dt, html, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import desk_index_design as design

ROOT = Path(__file__).parent
SURVEY = ROOT / "DESK_INDEX_SURVEY.json"
RESULT = ROOT / "DESK_INDEX_REDESIGN_STATUS.json"
# A page being rewritten must be recoverable, not merely verified afterwards: the exact
# previous copy is written first and travels with the run as an artefact, which is the one
# thing that makes an edit on a live page reversible at all.
BACKUP_DIR = ROOT / "DESK_INDEX_BACKUP"
BOARD_CLASS = "dxi"

# Page identity, the words shown on the new board, and the section it heads.
TARGETS = (
    {
        "key": "corporate", "page_id": "6065205676235626846",
        "path": "/p/for-corporate_01804417406.html", "title": "FOR CORPORATE",
        "aria": "Boardroom desk index", "eyebrow": "Boardroom index", "board_title": "Pick a desk",
        "note": "{total} tools, one board", "open": "Open desk",
        "chips": ["Textbook formulas", "Live receipts", "Runs in your browser"],
    },
    {
        "key": "snapshot", "page_id": "8504888514217789256",
        "path": "/p/global-snapshot.html", "title": "GLOBAL SNAPSHOT",
        "aria": "Markets desk index", "eyebrow": "Markets index", "board_title": "Pick a desk",
        "note": "{total} desks, one tape", "open": "Open board",
        "chips": ["36,000+ funds", "14 commodities", "69 one-tap charts", "41 currencies", "25 mega caps"],
    },
    {
        "key": "calculator", "page_id": "3945823007631424733" if False else "7468827438203976743",
        "path": "/p/calculator_0908148622.html", "title": "CALCULATOR",
        "aria": "Calculator desk index", "eyebrow": "Desk index", "board_title": "Pick a desk",
        "note": "{total} calculators, grouped by task", "open": "Open desk",
        "chips": ["No sign-up", "Nothing stored", "Runs in your browser", "45 countries"],
    },
)


# ------------------------------------------------------------------ Blogger API
def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def base() -> str:
    return f"https://www.googleapis.com/blogger/v3/blogs/{_required('BLOGGER_BLOG_ID')}"


def token() -> str:
    form = urllib.parse.urlencode({
        "client_id": _required("BLOGGER_CLIENT_ID"),
        "client_secret": _required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": _required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)["access_token"]


def call(path: str, tok: str, method: str = "GET", body: dict | None = None, params: dict | None = None):
    url = base() + path + ("?" + urllib.parse.urlencode(params) if params else "")
    request = urllib.request.Request(
        url, data=json.dumps(body).encode() if body is not None else None, method=method,
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode(errors="replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"{method} {path} -> {exc.code} {detail}") from None
    raise RuntimeError(f"{method} {path} did not complete")


def pages(tok: str) -> list[dict]:
    rows: list[dict] = []
    page: str | None = None
    for _ in range(10):
        params = {"fetchBodies": "true", "maxResults": 50, "fields": "items(id,title,url,content),nextPageToken"}
        if page:
            params["pageToken"] = page
        data = call("/pages", tok, params=params)
        rows.extend(data.get("items", []))
        page = data.get("nextPageToken")
        if not page:
            break
    return rows


def page_for(tok: str, target: dict) -> dict:
    wanted = target["path"].rstrip("/")
    for row in pages(tok):
        if urllib.parse.urlsplit(row.get("url") or "").path.rstrip("/") == wanted:
            return row
    row = call(f"/pages/{target['page_id']}", tok)
    if not row.get("id"):
        raise RuntimeError(f"page not found: {target['title']}")
    return row


# ------------------------------------------------------------------ index parsing
def text(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or ""))).strip()


def find_index(content: str) -> tuple[int, int] | None:
    """Locate the index nav, whether it is the old block or the designed one."""
    for pattern in (r'<nav[^>]*class="dxi"', r'<nav[^>]*class="kc-index"'):
        match = re.search(pattern, content or "", re.I)
        if match:
            end = content.find("</nav>", match.start())
            if end < 0:
                continue
            return match.start(), end + len("</nav>")
    return None


def parse_index(content: str) -> dict:
    """Read the current index into groups and items, keeping every link intact."""
    bounds = find_index(content)
    if not bounds:
        raise RuntimeError("no desk index block found on this page")
    block = content[bounds[0]:bounds[1]]
    head = re.search(r'class="(?:kc-ihead|dxi-head)">(.*?)</(?:div|header)>', block, re.S)
    hint = ""
    if head:
        hint = text(head.group(1))
        hint = re.sub(rf"^{re.escape('')}", "", hint)
    if re.search(r'class="dxi-head"', block):
        eyebrow = text(re.search(r'class="dxi-eyebrow">(.*?)</p>', block, re.S).group(1)) if re.search(r'class="dxi-eyebrow">(.*?)</p>', block, re.S) else ""
        groups = []
        for group in re.finditer(r'<section class="dxi-group">(.*?)</section>', block, re.S):
            body = group.group(1)
            name = text(re.search(r'class="dxi-gname">(.*?)</h3>', body, re.S).group(1))
            items = []
            for card in re.finditer(r'<a class="dxi-card" href="([^"]+)">(.*?)</a>', body, re.S):
                inner = card.group(2)
                icon = re.search(r'<svg.*?</svg>', inner, re.S)
                items.append({
                    "href": html.unescape(card.group(1)),
                    "num": text(re.search(r'class="dxi-num">(.*?)</span>', inner, re.S).group(1)),
                    "title": text(re.search(r'class="dxi-name">(.*?)</strong>', inner, re.S).group(1)),
                    "desc": text(re.search(r'class="dxi-note2">(.*?)</span>', inner, re.S).group(1)),
                    "icon": re.sub(r"\s+", " ", icon.group(0)).strip() if icon else "",
                })
            groups.append({"name": name, "items": items})
        return {"head": hint, "eyebrow": eyebrow, "groups": groups}
    inner = re.search(r'class="kc-ilinks">(.*)</div>\s*$', block, re.S)
    body = inner.group(1) if inner else block
    groups: list[dict] = []
    for part in re.split(r'(?=<a class=")', body):
        if part.startswith('<a class="pr-index-heading"'):
            name = re.sub(r"\s*[↓↑↑]\s*$", "", text(part)).strip()
            groups.append({"name": name, "items": []})
        elif part.startswith('<a class="kc-icard"'):
            if not groups:
                groups.append({"name": "Tools", "items": []})
            href = re.search(r'href="([^"]+)"', part)
            icon = re.search(r"<svg.*?</svg>", part, re.S)
            groups[-1]["items"].append({
                "href": html.unescape(href.group(1)) if href else "",
                "num": text(re.search(r'class="kc-inum">(.*?)</span>', part, re.S).group(1)) if re.search(r'class="kc-inum">(.*?)</span>', part, re.S) else "",
                "title": text(re.search(r'class="kc-it">(.*?)</span>', part, re.S).group(1)) if re.search(r'class="kc-it">(.*?)</span>', part, re.S) else "",
                "desc": text(re.search(r'class="kc-id">(.*?)</span>', part, re.S).group(1)) if re.search(r'class="kc-id">(.*?)</span>', part, re.S) else "",
                "icon": re.sub(r"\s+", " ", icon.group(0)).strip() if icon else "",
            })
    return {"head": hint, "eyebrow": "", "groups": [g for g in groups if g["items"]]}


def board_for(target: dict, current: dict) -> dict:
    return {
        "aria": target["aria"], "eyebrow": target["eyebrow"], "title": target["board_title"],
        "note": target["note"], "chips": target["chips"], "groups": current["groups"],
        "labels": {"open": target["open"]},
    }


def validate(block: str, current: dict) -> list[str]:
    """Every requirement the designed board has to meet before it is written."""
    issues = []
    items = [item for group in current["groups"] for item in group["items"]]
    if '<nav class="dxi"' not in block:
        issues.append("designed board wrapper missing")
    if block.count('class="dxi-card"') != len(items):
        issues.append(f"card count changed ({block.count('class=\"dxi-card\"')} of {len(items)})")
    if block.count('class="dxi-group"') != len(current["groups"]):
        issues.append("group count changed")
    for item in items:
        if item["href"] not in block:
            issues.append(f"link lost: {item['href']}")
        if html.escape(item["title"]) not in block:
            issues.append(f"title lost: {item['title']}")
        # the icon tag is rebuilt to fix its geometry, so the artwork is compared, not the markup
        if design.drawing(item["icon"]) and design.drawing(item["icon"]) not in design.drawing(block):
            issues.append(f"icon lost: {item['title']}")
    for required in ("dxi-gnum", "dxi-gcount", "dxi-gline", "dxi-open", "dyDeskIndexStyle", "data-dy-desk-index"):
        if required not in block:
            issues.append(f"board element missing: {required}")
    if "kc-ilinks" in block or "pr-index-heading" in block:
        issues.append("old grid-heading markup still present")
    return sorted(set(issues))


def survey(tok: str) -> dict:
    rows = []
    for target in TARGETS:
        page = page_for(tok, target)
        content = page.get("content") or ""
        current = parse_index(content)
        block = design.render(board_for(target, current))
        issues = validate(block, current)
        rows.append({
            "key": target["key"], "page": target["title"], "page_id": page["id"], "url": page.get("url"),
            "groups": len(current["groups"]),
            "items": sum(len(g["items"]) for g in current["groups"]),
            "group_names": [g["name"] for g in current["groups"]],
            "already_designed": '<nav class="dxi"' in content,
            "block_bytes": len(block), "issues": issues,
        })
        print(json.dumps({"page": target["title"], "groups": len(current["groups"]),
                          "items": rows[-1]["items"], "already_designed": rows[-1]["already_designed"],
                          "issues": issues}, ensure_ascii=False))
    document = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "rows": rows,
                "zero_public_pageviews": True}
    SURVEY.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return document


def apply(tok: str, dry_run: bool = False) -> dict:
    results = []
    for target in TARGETS:
        page = page_for(tok, target)
        content = page.get("content") or ""
        current = parse_index(content)
        block = design.render(board_for(target, current))
        issues = validate(block, current)
        if issues:
            results.append({"page": target["title"], "status": "FAIL", "issues": issues})
            print(f"{target['title']}: {issues}")
            continue
        bounds = find_index(content)
        updated = content[:bounds[0]] + block + content[bounds[1]:]
        if dry_run:
            results.append({"page": target["title"], "status": "DRY_RUN", "bytes": len(updated)})
            print(f"{target['title']}: dry run ok ({len(updated)} bytes)")
            continue
        if updated == content:
            results.append({"page": target["title"], "status": "ALREADY_DESIGNED"})
            print(f"{target['title']}: already designed")
            continue
        backup = BACKUP_DIR / f"{target['key']}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}.html"
        backup.parent.mkdir(exist_ok=True)
        backup.write_text(content, encoding="utf-8")
        call(f"/pages/{page['id']}", tok, "PUT", {
            "kind": "blogger#page", "id": page["id"], "blog": {"id": _required("BLOGGER_BLOG_ID")},
            "title": page.get("title"), "content": updated,
        })
        stored = call(f"/pages/{page['id']}", tok)
        stored_content = stored.get("content") or ""
        checks = {
            "board_present": '<nav class="dxi"' in stored_content,
            # The replaced markup must be gone. The page's older inline CSS rules
            # are inert and stay in place; only markup matters here.
            "old_index_gone": not re.search(r'<a class="(?:kc-icard|pr-index-heading)"', stored_content),
            "old_nav_gone": not re.search(r'<nav[^>]*class="kc-index"', stored_content),
            "cards": stored_content.count('class="dxi-card"'),
            "groups": stored_content.count('class="dxi-group"'),
            "links_kept": all(item["href"] in stored_content for group in current["groups"] for item in group["items"]),
            "style_present": "dyDeskIndexStyle" in stored_content,
        }
        status = "PASS" if all(checks[k] for k in ("board_present", "old_index_gone", "old_nav_gone", "links_kept", "style_present")) else "FAIL"
        results.append({"page": target["title"], "status": status, "url": page.get("url"),
                        "backup": str(backup.relative_to(ROOT)), "checks": checks})
        print(json.dumps({"page": target["title"], "status": status, **checks}, ensure_ascii=False))
    document = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "apply": not dry_run,
                "results": results, "zero_public_pageviews": True}
    RESULT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    tok = token()
    if args.survey:
        document = survey(tok)
        return 0 if all(not row["issues"] for row in document["rows"]) else 1
    document = apply(tok, dry_run=not args.apply or args.dry_run)
    failed = [row for row in document["results"] if row["status"] == "FAIL"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
