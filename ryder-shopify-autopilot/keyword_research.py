"""Keyword research for the Ryder content machine — dual provider.

Queries every provider with credentials in shopify.env and merges the
results per keyword, so volumes can be cross-checked:

- DataForSEO Labs (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD): Google
  search volume + keyword difficulty. Pay-per-call.
- Ahrefs API v3 (AHREFS_API_KEY): volume + difficulty from Ahrefs'
  index. Needs an active Ahrefs API subscription (a dashboard login
  alone is not enough; keys come from app.ahrefs.com/api-keys).

US-only per the ICP rule in RYDER_CONTENT_SYSTEM_PROMPT.md; widen only
via the 8-week review.

Usage:
    python3 keyword_research.py overview "hardware wallet,cold storage"
    python3 keyword_research.py matching "hardware wallet" [limit]
    python3 keyword_research.py related "seed phrase" [limit]

    from keyword_research import research   # research(mode, arg, limit)
"""

import base64
import datetime
import json
import os
import sys
import urllib.parse

from common import http, load_env

# ---------------------------------------------------------------- dataforseo

D4S_API = "https://api.dataforseo.com/v3"
LOCATION_US = 2840
LANGUAGE = "en"


def _d4s_enabled():
    return all(os.environ.get(k) not in (None, "", "REPLACE_ME")
               for k in ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"))


def _d4s_post(path, payload):
    token = base64.b64encode(
        f"{os.environ['DATAFORSEO_LOGIN']}:{os.environ['DATAFORSEO_PASSWORD']}"
        .encode()).decode()
    status, body = http("POST", f"{D4S_API}/{path}",
                        headers={"Authorization": f"Basic {token}"},
                        payload=[payload])
    if status != 200:
        raise RuntimeError(f"dataforseo HTTP {status}: {str(body)[:200]}")
    task = (body.get("tasks") or [{}])[0]
    if task.get("status_code") != 20000:
        raise RuntimeError(f"dataforseo task {task.get('status_code')} "
                           f"{task.get('status_message')}")
    return (task.get("result") or [{}])[0].get("items") or []


def _d4s(mode, arg, limit):
    if mode == "overview":
        items = _d4s_post("dataforseo_labs/google/keyword_overview/live",
                          {"keywords": arg, "location_code": LOCATION_US,
                           "language_code": LANGUAGE})
    elif mode == "matching":
        items = _d4s_post("dataforseo_labs/google/keyword_suggestions/live",
                          {"keyword": arg, "location_code": LOCATION_US,
                           "language_code": LANGUAGE, "limit": limit})
    else:
        items = [i.get("keyword_data") or {} for i in
                 _d4s_post("dataforseo_labs/google/related_keywords/live",
                           {"keyword": arg, "location_code": LOCATION_US,
                            "language_code": LANGUAGE, "depth": 2,
                            "limit": limit})]
    out = {}
    for i in items:
        kw = i.get("keyword")
        if not kw:
            continue
        info = i.get("keyword_info") or {}
        props = i.get("keyword_properties") or {}
        out[kw] = {"volume": info.get("search_volume"),
                   "difficulty": props.get("keyword_difficulty")}
    return out


# ---------------------------------------------------------------- ahrefs

AHREFS_API = "https://api.ahrefs.com/v3"


def _ahrefs_enabled():
    return os.environ.get("AHREFS_API_KEY") not in (None, "", "REPLACE_ME")


def _ahrefs_get(path, params):
    params = {"country": "us",
              "select": "keyword,volume,difficulty", **params}
    url = f"{AHREFS_API}/{path}?{urllib.parse.urlencode(params)}"
    status, body = http("GET", url, headers={
        "Authorization": f"Bearer {os.environ['AHREFS_API_KEY']}",
        "Accept": "application/json"})
    if status != 200:
        raise RuntimeError(f"ahrefs HTTP {status}: {str(body)[:200]}")
    rows = body.get("keywords") or body.get("terms") or []
    return {r["keyword"]: {"volume": r.get("volume"),
                           "difficulty": r.get("difficulty")}
            for r in rows if isinstance(r, dict) and r.get("keyword")}


def _ahrefs(mode, arg, limit):
    if mode == "overview":
        return _ahrefs_get("keywords-explorer/overview",
                           {"keywords": ",".join(arg)})
    if mode == "matching":
        return _ahrefs_get("keywords-explorer/matching-terms",
                           {"keywords": arg, "limit": limit})
    return _ahrefs_get("keywords-explorer/related-terms",
                       {"keywords": arg, "limit": limit})


# ---------------------------------------------------------------- merge

def research(mode, arg, limit=50):
    """Returns (rows, notes). Each row: {keyword, d4s_volume,
    d4s_difficulty, ahrefs_volume, ahrefs_difficulty}. Providers that
    error are reported in notes rather than sinking the whole call."""
    providers, notes = {}, []
    for name, enabled, fn in (("d4s", _d4s_enabled, _d4s),
                              ("ahrefs", _ahrefs_enabled, _ahrefs)):
        if not enabled():
            notes.append(f"{name}: no credentials, skipped")
            continue
        try:
            providers[name] = fn(mode, arg, limit)
        except RuntimeError as e:
            notes.append(f"{name}: {e}")
    merged = {}
    for name, rows in providers.items():
        for kw, vals in rows.items():
            row = merged.setdefault(kw, {"keyword": kw})
            row[f"{name}_volume"] = vals["volume"]
            row[f"{name}_difficulty"] = vals["difficulty"]
    rows = sorted(merged.values(),
                  key=lambda r: r.get("d4s_volume") or r.get("ahrefs_volume") or 0,
                  reverse=True)
    return rows, notes


def main():
    load_env(required_keys=())
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv[1:]
    if len(args) < 2:
        raise SystemExit(__doc__)
    mode, arg = args[0], args[1]
    if mode not in ("overview", "matching", "related"):
        raise SystemExit(f"unknown mode {mode}")
    if mode == "overview":
        arg = [k.strip() for k in arg.split(",")]
    limit = int(args[2]) if len(args) > 2 else 50
    rows, notes = research(mode, arg, limit)
    if as_json:
        # Explicit nulls preserve the distinction between no provider value
        # and an observed zero. Provider errors remain in notes.
        for row in rows:
            for provider in ("d4s", "ahrefs"):
                row.setdefault(f"{provider}_volume", None)
                row.setdefault(f"{provider}_difficulty", None)
        print(json.dumps({"schema_version": 1, "country": "US",
                          "language": LANGUAGE,
                          "collected_on": datetime.date.today().isoformat(),
                          "providers": [name for name, prefix in
                                        (("DataForSEO", "d4s"), ("Ahrefs", "ahrefs"))
                                        if any(r.get(prefix + "_volume") is not None or
                                               r.get(prefix + "_difficulty") is not None
                                               for r in rows)],
                          "metric_sources": {"d4s": "DataForSEO Labs Google",
                                             "ahrefs": "Ahrefs Keywords Explorer"},
                          "mode": mode, "rows": rows, "notes": notes}, indent=2))
        return
    for n in notes:
        print(f"note: {n}", file=sys.stderr)
    fmt = lambda v: "?" if v is None else v
    print(f"{'google-vol':>10} {'kd':>4} {'ahrefs-vol':>11} {'kd':>4}  keyword")
    for r in rows:
        print(f"{fmt(r.get('d4s_volume')):>10} {fmt(r.get('d4s_difficulty')):>4} "
              f"{fmt(r.get('ahrefs_volume')):>11} {fmt(r.get('ahrefs_difficulty')):>4}  "
              f"{r['keyword']}")


if __name__ == "__main__":
    main()
