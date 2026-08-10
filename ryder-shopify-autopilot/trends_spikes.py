"""Google Trends spike detector for the Ryder content machine.

For each seed keyword, pulls Google Trends "rising" related queries
(US, last 90 days) via the endpoints behind trends.google.com. A value
of "Breakout" means the query grew >5000%: that's the spike signal that
feeds a batch. Rising terms should then be sized with keyword_research.py
(Ahrefs/DataForSEO) before they earn an article.

No credentials needed. Unofficial endpoints: Google throttles bursts, so
the module sleeps between seeds and retries once on 429. Run it before
each batch, not in tight loops.

Usage:
    python3 trends_spikes.py                       # default Ryder seed set
    python3 trends_spikes.py "tangem" "trezor"     # custom seeds
    from trends_spikes import rising_queries
"""

import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://trends.google.com"
GEO = "US"          # ICP rule: US only
TIMEFRAME = "today 3-m"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126.0.0.0 Safari/537.36"}

DEFAULT_SEEDS = ["hardware wallet", "crypto wallet", "cold wallet",
                 "seed phrase", "self custody", "ledger wallet",
                 "trezor", "tangem"]


def _session_cookie():
    req = urllib.request.Request(f"{BASE}/trends/", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        for part in resp.headers.get_all("Set-Cookie") or []:
            if part.startswith("NID"):
                return part.split(";")[0]
    return ""


def _get_json(url, cookie, retries=1):
    req = urllib.request.Request(url, headers={**HEADERS, "Cookie": cookie})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        if e.code == 429 and retries:
            time.sleep(12)
            return _get_json(url, cookie, retries - 1)
        raise RuntimeError(f"HTTP {e.code}")
    # responses are prefixed with )]}' or )]}'\n
    return json.loads(raw[raw.index("{"):])


def rising_queries(seed, cookie=None):
    """Rising related queries for one seed. Returns a list of
    {query, growth} where growth is 'Breakout' or '+N%'."""
    cookie = cookie or _session_cookie()
    explore_req = {"comparisonItem": [{"keyword": seed, "geo": GEO,
                                       "time": TIMEFRAME}],
                   "category": 0, "property": ""}
    url = (f"{BASE}/trends/api/explore?hl=en-US&tz=240&req="
           + urllib.parse.quote(json.dumps(explore_req)))
    widgets = _get_json(url, cookie)["widgets"]
    related = next(w for w in widgets if w["id"] == "RELATED_QUERIES")
    url = (f"{BASE}/trends/api/widgetdata/relatedsearches?hl=en-US&tz=240"
           f"&req={urllib.parse.quote(json.dumps(related['request']))}"
           f"&token={related['token']}")
    data = _get_json(url, cookie)
    ranked = data["default"]["rankedList"]
    rising = ranked[1]["rankedKeyword"] if len(ranked) > 1 else []
    return [{"query": r["query"], "growth": r.get("formattedValue", "?")}
            for r in rising]


def main():
    seeds = sys.argv[1:] or DEFAULT_SEEDS
    cookie = _session_cookie()
    for i, seed in enumerate(seeds):
        if i:
            time.sleep(6)  # stay under the radar
        try:
            rows = rising_queries(seed, cookie)
        except (RuntimeError, StopIteration, KeyError, ValueError) as e:
            print(f"\n## {seed}: unavailable ({e})")
            continue
        print(f"\n## {seed}")
        if not rows:
            print("  (no rising queries)")
        for r in rows[:10]:
            print(f"  {r['growth']:>10}  {r['query']}")


if __name__ == "__main__":
    main()
