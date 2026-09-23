#!/usr/bin/env python3
"""
Fix the Share & Market page price engine on FINANCE BY CA KUSHAL.

Bugs fixed (all verified against live TradingView/Blogger APIs):
  P1  scan() sent ALL stock tickers to scanner.tradingview.com/futures/scan
      which returns nothing for stocks -> every country board and the quote
      panel showed no prices. Now routes by exchange prefix to the correct
      regional endpoint (america/india/uk/japan/germany/...), futures to
      /futures, spot metals & world indices to /global, plus one /global
      retry pass for anything missed.
  P2  UK explorer tabs queried the /global endpoint (which has no LSE
      stocks) -> now queries /uk.
  P3  Indices tab relied on exchange filters on /global which return 0-1
      rows for almost every country -> now uses curated, verified index
      ticker lists per country + world majors.
  P4  Dead geo provider ipapi.co (HTTP 403) replaced by api.country.is.
  P5  Crypto desk had no fallback when CoinGecko rate-limits -> now falls
      back to data-api.binance.vision (official public market-data mirror,
      CORS-open, no key, not geo-blocked), converted to the desk currency
      via the page's own FX table.

Mode A (local dry-run):  python3 fix_share_market.py --dry-run-file FILE
Mode B (live, in Actions): no args -> uses BLOGGER_* env vars/secrets.
"""
import json
import os
import re
import sys

MARKERS = {
    "P1_router": "regionOf",
    "P2_uk": "isUK ? 'uk'",
    "P3_indices": "TASE:TA35",
    "P4_geo": "api.country.is",
    "P5_crypto_fallback": "data-api.binance.vision",
}

# ----------------------------------------------------------------------------
# New JS blocks (plain ES5, no backslashes -> safe inside python raw strings)
# ----------------------------------------------------------------------------

SCAN_NEW = r"""function scan(tickers, cb){
    // Route tickers to the correct TradingView scanner endpoint by exchange prefix.
    // Stocks live on regional endpoints, futures on /futures, spot metals and
    // world indices on /global; anything missed is retried once on /global.
    var REG = { NASDAQ:'america', NYSE:'america', NYSEARCA:'america', ARCA:'america', AMEX:'america', BATS:'america', OTC:'america', PINK:'america',
      NSE:'india', BSE:'india', LSE:'uk', LSIN:'uk', TSE:'japan', XETR:'germany', ETR:'germany',
      EURONEXT:'france', EPA:'france', SIX:'switzerland', BX:'switzerland', ASX:'australia',
      TSX:'canada', TSXV:'canada', NEO:'canada', NEOE:'canada', CVE:'canada',
      SSE:'china', SZSE:'china', HKEX:'hongkong', KRX:'korea', KOSDAQ:'korea',
      TWSE:'taiwan', BMFBOVESPA:'brazil', B3:'brazil', SGX:'singapore' };
    var FUT = { COMEX:1, NYMEX:1, CBOT:1, CME:1, ICEUS:1, ICEEUR:1, MCX:1, DCE:1, SHFE:1, ZCE:1, LME:1 };
    var GLB = { TVC:1, SP:1, DJ:1, HSI:1, BMV:1, FX:1, FOREXCOM:1, CRYPTOCAP:1, CRYPTO:1 };
    function regionOf(t){
      var ex = t.split(':')[0];
      if (GLB[ex]) return 'global';
      if (t.indexOf('!') !== -1 || FUT[ex]) return 'futures';
      return REG[ex] || 'global';
    }
    var groups = {}, i;
    for (i = 0; i !== tickers.length; i++){
      var rg = regionOf(tickers[i]);
      (groups[rg] = groups[rg] || []).push(tickers[i]);
    }
    var merged = {}, done = 0, keys = Object.keys(groups);
    function absorb(j){
      if (j && j.data){ for (var k = 0; k !== j.data.length; k++){ var dd = j.data[k].d; if (dd) merged[j.data[k].s] = { sym: j.data[k].s, name: dd[0], close: dd[1], chg: dd[2], chga: dd[3], cur: dd[4], mode: dd[5], logo: dd[6] }; } }
    }
    function hit(ep, list, after){
      fetch('https://scanner.tradingview.com/' + ep + '/scan', { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, body: JSON.stringify({ symbols: { tickers: list }, columns: ['name','close','change','change_abs','currency','update_mode','logoid'] }) })
        .then(function(r){ return r.json(); })
        .then(absorb)
        .catch(function(){})
        .then(after);
    }
    function retryGlobal(){
      var missing = [], i2;
      for (i2 = 0; i2 !== tickers.length; i2++){ if (!merged[tickers[i2]]) missing.push(tickers[i2]); }
      if (!missing.length){ finalize(); return; }
      hit('global', missing, finalize);
    }
    function finalize(){
      var out = [], i3;
      for (i3 = 0; i3 !== tickers.length; i3++) if (merged[tickers[i3]]) out.push(merged[tickers[i3]]);
      cb(out.length ? out : null);
    }
    if (!keys.length){ finalize(); return; }
    keys.forEach(function(k){ hit(k, groups[k], function(){ done++; if (done === keys.length) retryGlobal(); }); });
  }"""

IDX_NEW = r"""if (XTAB === 'idx'){
      var IX = {
        us: 'SP:SPX|S&P 500,DJ:DJI|Dow 30,NASDAQ:IXIC|Nasdaq Composite,TVC:RUT|Russell 2000',
        in: 'NSE:NIFTY|Nifty 50,BSE:SENSEX|BSE Sensex,NSE:BANKNIFTY|Nifty Bank',
        gb: 'TVC:UKX|FTSE 100',
        jp: 'TVC:NI225|Nikkei 225',
        de: 'XETR:DAX|DAX 40',
        fr: 'EURONEXT:PX1|CAC 40',
        ch: 'SIX:SMI|Swiss Market Index',
        au: 'ASX:XJO|S&P/ASX 200',
        ca: 'TSX:TSX|S&P/TSX Composite',
        cn: 'SSE:000001|SSE Composite,SZSE:399001|Shenzhen Component',
        hk: 'HSI:HSI|Hang Seng',
        kr: 'KRX:KOSPI|KOSPI',
        tw: 'TWSE:IX0001|Taiwan Weighted',
        br: 'BMFBOVESPA:IBOV|Bovespa',
        mx: 'BMV:ME|S&P/BMV IPC',
        sg: 'TVC:STI|Straits Times',
        nl: 'EURONEXT:AEX|AEX Index',
        il: 'TASE:TA35|TA-35 Index'
      };
      var WORLD = 'SP:SPX|S&P 500,DJ:DJI|Dow 30,NASDAQ:IXIC|Nasdaq,TVC:UKX|FTSE 100,TVC:NI225|Nikkei 225,TVC:DXY|US Dollar Index,TVC:VIX|Volatility S&P 500';
      var ixl = (IX[XMK] ? IX[XMK] + ',' : '') + WORLD;
      var seen = {}, tks = [], labs = {};
      ixl.split(',').forEach(function(p){
        var bits = p.split('|');
        if (bits[0] && !seen[bits[0]]){ seen[bits[0]] = 1; tks.push(bits[0]); labs[bits[0]] = bits[1] || bits[0]; }
      });
      scan(tks, function(rows){
        if (seq !== xSeq) return;
        if (!rows){ xWorldIdx(seq); return; }
        XROWS = rows.map(function(r){ return { sym: r.sym, name: r.name, desc: labs[r.sym] || r.name, close: r.close, chg: r.chg, cur: r.cur, mode: r.mode, logo: r.logo }; });
        XTOTAL = XROWS.length; xBusy = false; xRender();
      });
      return;
    }
    if (XTAB === 'gold'){"""

CRYPTO_NEW = r"""var url = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=' + CUR +
      '&order=market_cap_desc&per_page=12&page=1&price_change_percentage=24h&sparkline=true';
    fetch(url).then(function(r){ return r.json(); }).then(function(rows){
      busy = false;
      if (!rows || !rows.length || rows.error) throw new Error('cg down');
      if (want !== CUR){ load(); return; }
      draw(rows); tick = 0;
    }).catch(function(){ busy = false; loadAlt(); });
  }
  function loadAlt(){
    if (busy || d.hidden) return;
    busy = true;
    var want = CUR;
    var ALT = { BTCUSDT:['Bitcoin','btc'], ETHUSDT:['Ethereum','eth'], SOLUSDT:['Solana','sol'], BNBUSDT:['BNB','bnb'], XRPUSDT:['XRP','xrp'], DOGEUSDT:['Dogecoin','doge'], ADAUSDT:['Cardano','ada'], AVAXUSDT:['Avalanche','avax'], LINKUSDT:['Chainlink','link'], TRXUSDT:['TRON','trx'], DOTUSDT:['Polkadot','dot'], LTCUSDT:['Litecoin','ltc'] };
    var q = encodeURIComponent(JSON.stringify(Object.keys(ALT)));
    fetch('https://data-api.binance.vision/api/v3/ticker/24hr?symbols=' + q)
      .then(function(r){ return r.json(); })
      .then(function(list){
        busy = false;
        if (!list || !list.length || list.error) return;
        if (want !== CUR) return;
        var rows = [];
        list.forEach(function(t){
          var nm = ALT[t.symbol] || [t.symbol, 'cc'];
          var ic = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28"><rect width="28" height="28" rx="14" fill="%23bc5b33"/><text x="14" y="19" font-size="13" font-family="Arial" font-weight="bold" fill="%23fffdf8" text-anchor="middle">' + nm[1].charAt(0).toUpperCase() + '</text></svg>';
          rows.push({ id: nm[1], symbol: nm[1], name: nm[0], image: ic, current_price: convert(parseFloat(t.lastPrice), 'usd', CUR), price_change_percentage_24h: parseFloat(t.priceChangePercent), sparkline_in_7d: null });
        });
        draw(rows); tick = 0;
      })
      .catch(function(){ busy = false; });
  }"""


def apply_patches(content: str):
    """Apply the 5 patches. Returns (new_content, report list). Idempotent."""
    report = []
    already = [m for m, s in MARKERS.items() if s in content]

    # ---- P1: replace scan() ----
    pat1 = re.compile(
        r"function scan\(tickers, cb\)\{.*?endpoints\.forEach\(finOne\);\s*\}",
        re.DOTALL,
    )
    if pat1.search(content):
        content = pat1.sub(lambda m: SCAN_NEW, content, count=1)
        report.append("P1 scan() multi-endpoint router  : PATCHED")
    elif MARKERS["P1_router"] in content:
        report.append("P1 scan() multi-endpoint router  : already patched")
    else:
        report.append("P1 scan() multi-endpoint router  : !! ANCHOR NOT FOUND !!")

    # ---- P2: UK explorer endpoint ----
    old2 = "var ep = isUK ? 'global' : XM[XMK][0];"
    if old2 in content:
        content = content.replace(old2, "var ep = isUK ? 'uk' : XM[XMK][0];", 1)
        report.append("P2 UK explorer endpoint -> /uk   : PATCHED")
    elif MARKERS["P2_uk"] in content:
        report.append("P2 UK explorer endpoint -> /uk   : already patched")
    else:
        report.append("P2 UK explorer endpoint -> /uk   : !! ANCHOR NOT FOUND !!")

    # ---- P3: indices tab curated lists ----
    pat3 = re.compile(
        r"if \(XTAB === 'idx'\)\{.*?if \(XTAB === 'gold'\)\{",
        re.DOTALL,
    )
    if pat3.search(content):
        content = pat3.sub(lambda m: IDX_NEW, content, count=1)
        report.append("P3 indices tab curated lists    : PATCHED")
    elif MARKERS["P3_indices"] in content:
        report.append("P3 indices tab curated lists    : already patched")
    else:
        report.append("P3 indices tab curated lists    : !! ANCHOR NOT FOUND !!")

    # ---- P4: geo provider swap ----
    old4 = "'https://ipapi.co/json/'"
    if old4 in content:
        content = content.replace(old4, "'https://api.country.is/'", 1)
        report.append("P4 geo provider api.country.is  : PATCHED")
    elif MARKERS["P4_geo"] in content:
        report.append("P4 geo provider api.country.is  : already patched")
    else:
        report.append("P4 geo provider api.country.is  : !! ANCHOR NOT FOUND !!")

    # ---- P5: crypto fallback ----
    pat5 = re.compile(
        re.escape("var url = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=' + CUR +")
        + r".*?catch\(function\(\)\{ busy = false; \}\);\s*\n\s*\}",
        re.DOTALL,
    )
    if pat5.search(content):
        content = pat5.sub(lambda m: CRYPTO_NEW, content, count=1)
        report.append("P5 crypto fallback (binance)    : PATCHED")
    elif MARKERS["P5_crypto_fallback"] in content:
        report.append("P5 crypto fallback (binance)    : already patched")
    else:
        report.append("P5 crypto fallback (binance)    : !! ANCHOR NOT FOUND !!")

    return content, report, already


def main():
    # Mode A: local dry-run
    if len(sys.argv) >= 3 and sys.argv[1] == "--dry-run-file":
        with open(sys.argv[2], encoding="utf-8") as f:
            content = f.read()
        new, report, _ = apply_patches(content)
        print("\n".join(report))
        missing = [r for r in report if "NOT FOUND" in r]
        if missing:
            print("\nDRY-RUN FAILED — do not deploy.")
            sys.exit(1)
        with open(sys.argv[2].rsplit(".", 1)[0] + "_PATCHED.html", "w", encoding="utf-8") as f:
            f.write(new)
        ok = all(s in new for s in MARKERS.values())
        print(f"\nDRY-RUN OK. All markers present: {ok}. Patched copy saved "
              + sys.argv[2].rsplit(".", 1)[0] + "_PATCHED.html")
        sys.exit(0 if ok else 1)

    # Mode B: live patch via Blogger API
    import requests

    cid = os.environ["BLOGGER_CLIENT_ID"]
    csec = os.environ["BLOGGER_CLIENT_SECRET"]
    rt = os.environ["BLOGGER_REFRESH_TOKEN"]
    blog_id = os.environ["BLOGGER_BLOG_ID"]

    # 1. OAuth access token
    tok_r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": cid,
            "client_secret": csec,
            "refresh_token": rt,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    tok_r.raise_for_status()
    access = tok_r.json()["access_token"]
    print("OAuth token acquired.")
    H = {"Authorization": "Bearer " + access}

    # 2. Find the Share & Market page
    base = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}"
    pages = requests.get(base + "/pages", params={"maxResults": "50"}, headers=H, timeout=30)
    pages.raise_for_status()
    target = None
    for p in pages.json().get("items", []):
        if "share-market" in (p.get("url") or ""):
            target = p
            break
    if not target:
        print("!! Share & Market page NOT FOUND. Pages seen:")
        for p in pages.json().get("items", []):
            print("   -", p.get("title"), p.get("url"))
        sys.exit(1)
    print(f"Target page: {target['title']} -> {target['url']} (id {target['id']})")

    # 3. Fetch current stored content
    page = requests.get(f"{base}/pages/{target['id']}",
                        params={"fetchBody": "true"}, headers=H, timeout=30)
    page.raise_for_status()
    page = page.json()
    content = page.get("content", "")
    print(f"Current stored content: {len(content)} chars")
    if len(content) < 50000:
        print("!! Suspiciously small page content — aborting for safety.")
        sys.exit(1)

    # 4. Apply patches
    new_content, report, _ = apply_patches(content)
    print("\n".join(report))
    if any("NOT FOUND" in r for r in report):
        print("\nABORT: not all anchors matched — page left untouched.")
        sys.exit(1)
    if new_content == content:
        print("\nNo changes needed (already patched). Verifying live state only.")
    else:
        # 5. Update the page
        upd = requests.put(
            f"{base}/pages/{target['id']}",
            params={"publish": "true"},
            headers=H,
            json={"kind": "blogger#page", "id": target["id"],
                  "title": page.get("title", "Share & Market"),
                  "content": new_content},
            timeout=60,
        )
        print(f"\nUpdate response: HTTP {upd.status_code}")
        upd.raise_for_status()
        print("Page updated on Blogger.")

    # 6. Verify
    chk = requests.get(f"{base}/pages/{target['id']}",
                       params={"fetchBody": "true"}, headers=H, timeout=30)
    chk.raise_for_status()
    live = chk.json().get("content", "")
    print("\n=== VERIFICATION ===")
    all_ok = True
    for name, marker in MARKERS.items():
        ok = marker in live
        all_ok = all_ok and ok
        print(f"  {'OK ' if ok else 'FAIL'} {name}: '{marker}' present={ok}")
    print("\nRESULT:", "ALL FIXES LIVE ON THE PAGE ✔" if all_ok else "SOME FIXES MISSING ✘")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
