"""How many new articles may go live today: a daily cap plus an index brake.

Google treats a sudden flood of automated pages as a possible "scaled
content" pattern. The cap keeps the publishing pace steady, and the brake
slows down on its own when Google starts declining to index recent posts,
which is the earliest visible sign of a quality problem.

    python3 publish_budget.py            # prints the JSON budget

Rules (Louise, 2026-11-25, "be cautious"):
- DAILY_CAP new articles per Tokyo calendar day (server clock), counted
  from outputs/publish-log.json, which push_articles.py appends to on every
  successful new publish.
- Brake: look at posts published 7-30 days ago (enough time for Google to
  decide). If 2+ of them are still not indexed AND that is 25%+ of them, the
  cap drops to 1/day. If 3+ and 50%+, publishing pauses (cap 0) until the
  index watch shows recovery. The summary says why.
"""
import datetime as dt
import json
import os
import sys

from common import OUTPUTS_DIR
from index_watch import INDEXED_STATES, WATCH_FILE

DAILY_CAP = int(os.environ.get("PUBLISH_DAILY_CAP", "4"))
PUBLISH_LOG = os.path.join(OUTPUTS_DIR, "publish-log.json")
# Watch entries older than the log were all published by earlier flows.
LEDGER_START = dt.date(2026, 11, 25)


def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def record_publish(slug, title=""):
    log = _load(PUBLISH_LOG, [])
    log.append({"slug": slug, "title": title,
                "date": dt.date.today().isoformat(),
                "at": dt.datetime.now().isoformat(timespec="seconds")})
    os.makedirs(os.path.dirname(PUBLISH_LOG), exist_ok=True)
    tmp = PUBLISH_LOG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(log, f, indent=2)
    os.replace(tmp, PUBLISH_LOG)


def budget(today=None):
    today = today or dt.date.today()
    log = _load(PUBLISH_LOG, [])
    published = {e["slug"] for e in log}
    today_count = sum(1 for e in log if e.get("date") == today.isoformat())

    window = []
    for rec in _load(WATCH_FILE, []):
        try:
            added = dt.date.fromisoformat(rec.get("added") or "")
        except ValueError:
            continue
        age = (today - added).days
        if 7 <= age <= 30 and (added < LEDGER_START or rec["slug"] in published):
            window.append(rec)
    stuck = [r["slug"] for r in window if r.get("coverage_state") not in INDEXED_STATES]
    share = len(stuck) / len(window) if window else 0.0

    cap, reason = DAILY_CAP, f"normal pace: up to {DAILY_CAP}/day"
    if len(stuck) >= 3 and share >= 0.5:
        cap, reason = 0, (f"PAUSED: {len(stuck)} of {len(window)} posts from 7-30 "
                          "days ago are not indexed; Google may be judging new "
                          "pages as low value. Review before publishing more.")
    elif len(stuck) >= 2 and share >= 0.25:
        cap, reason = 1, (f"BRAKE: {len(stuck)} of {len(window)} posts from 7-30 "
                          "days ago are not indexed; slowed to 1/day.")
    return {"date": today.isoformat(), "cap": cap,
            "published_today": today_count,
            "remaining_today": max(0, cap - today_count),
            "reason": reason, "not_indexed_7_30d": stuck,
            "checked_7_30d": len(window)}


if __name__ == "__main__":
    print(json.dumps(budget(), indent=2))
    sys.exit(0)
