"""Durable index watch: track new articles until Google indexes them.

The push manifest (articles-to-push.json) is rewritten every time a new
batch is prepared, so anything that reads "the current manifest" loses
sight of older articles the moment the next batch lands. Index coverage
takes days; batches rotate in hours. Articles were silently falling out
of the watch before Google had ever crawled them.

This keeps its own append-only watch list instead. Slugs enter when they
are pushed and leave only when Google reports them indexed.

The watch file is manifest-shaped (slug + target_keyword per record), so
linkback_sweep.py can read it directly:

    python3 linkback_sweep.py --manifest <watch file> --dry-run

Usage:
    python3 index_watch.py add [--manifest PATH]   # merge manifest -> watch
    python3 index_watch.py check                   # inspect pending slugs
    python3 index_watch.py list                    # show current state

`check` exits 0 when every watched slug is indexed, 2 while any are still
pending, so a scheduled caller can stop itself on a clean 0.
"""

import datetime
import json
import os
import sys

from common import ARTICLE_URL_PATTERN, DEFAULT_MANIFEST, OUTPUTS_DIR, load_env

WATCH_FILE = os.environ.get("INDEX_WATCH_FILE",
                            os.path.join(OUTPUTS_DIR, "index-watch.json"))

# Coverage states that mean Google has the page in its index. Matched
# exactly, never by substring: "Crawled - currently not indexed" contains
# the word "indexed" and is the opposite of what we are looking for.
INDEXED_STATES = {
    "Submitted and indexed",
    "Indexed, not submitted in sitemap",
    "Indexed, low interest",
}


def _today():
    return datetime.date.today().isoformat()


def load_watch():
    try:
        with open(WATCH_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_watch(records):
    os.makedirs(os.path.dirname(WATCH_FILE), exist_ok=True)
    with open(WATCH_FILE, "w") as f:
        json.dump(records, f, indent=2)


def add_items(items):
    """Merge manifest-shaped dicts into the watch list. Returns added slugs.

    Existing records are never overwritten: a slug already being watched
    keeps its added date and its accumulated check history.
    """
    records = load_watch()
    known = {r["slug"] for r in records}
    added = []
    for item in items:
        slug = item.get("slug")
        if not slug or slug in known:
            continue
        records.append({
            "slug": slug,
            "target_keyword": item.get("target_keyword", ""),
            "title": item.get("title", ""),
            "added": _today(),
            "coverage_state": None,
            "last_crawl": None,
            "checked": None,
            "indexed_on": None,
        })
        known.add(slug)
        added.append(slug)
    if added:
        save_watch(records)
    return added


def check_all(verbose=True):
    """Inspect every pending slug. Returns (pending, newly_indexed)."""
    from gsc import inspect, submit_sitemap

    records = load_watch()
    pending, newly_indexed = [], []

    for rec in records:
        if rec.get("indexed_on"):
            continue
        url = ARTICLE_URL_PATTERN.format(handle=rec["slug"])
        try:
            result = inspect(url)["inspectionResult"]["indexStatusResult"]
        except (SystemExit, KeyError, TypeError) as e:
            # One bad lookup must not abort the sweep; leave the record
            # pending and report it so a transient failure stays visible.
            rec["checked"] = _today()
            if verbose:
                print(f"  ERR  {rec['slug']}: {str(e)[:120]}")
            pending.append(rec)
            continue

        was = rec.get("coverage_state")
        state = result.get("coverageState")
        rec["coverage_state"] = state
        rec["last_crawl"] = result.get("lastCrawlTime")
        rec["checked"] = _today()

        if state in INDEXED_STATES:
            rec["indexed_on"] = _today()
            newly_indexed.append(rec)
        else:
            pending.append(rec)

        if verbose:
            mark = "NEW " if state in INDEXED_STATES else "    "
            change = f"  (was: {was})" if was and was != state else ""
            print(f"{mark} {rec['slug']}: {state} | "
                  f"crawl {rec['last_crawl'] or 'never'}{change}")

    save_watch(records)

    if pending:
        try:
            submit_sitemap()
            if verbose:
                print("sitemap re-submitted "
                      f"({len(pending)} slug(s) still pending)")
        except SystemExit as e:
            if verbose:
                print(f"sitemap re-submit failed: {str(e)[:120]}")

    return pending, newly_indexed


def main():
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "add":
        path = DEFAULT_MANIFEST
        if "--manifest" in sys.argv:
            path = sys.argv[sys.argv.index("--manifest") + 1]
        with open(path) as f:
            items = json.load(f)
        added = add_items(items)
        print(f"watching {len(load_watch())} slug(s); "
              f"added {len(added)}" + (": " + ", ".join(added) if added else ""))

    elif cmd == "check":
        pending, indexed = check_all()
        total = len(load_watch())
        print(f"\n{total - len(pending)}/{total} indexed"
              + (f"; pending: {', '.join(r['slug'] for r in pending)}"
                 if pending else " — batch fully indexed"))
        sys.exit(0 if not pending else 2)

    elif cmd == "list":
        for r in load_watch():
            state = r.get("indexed_on") or r.get("coverage_state") or "unchecked"
            print(f"{r['slug']:<55} {state:<32} added {r['added']}")

    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
