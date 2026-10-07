"""Link-back sweep: point older blog articles at newly published ones.

For each new article, finds older published posts that mention its
target keyword in plain prose and wraps the first mention in a link.
This feeds internal authority to new posts instead of leaving them
orphaned. Conservative by design:

- only the first mention per old article gets linked
- at most MAX_EDITS_PER_ARTICLE insertions per old article per run
- never inside existing <a> tags, headings, or HTML attributes
- never edits the new articles themselves, never touches anything else
  in the body, and never publishes/unpublishes anything

Usage:
    python3 linkback_sweep.py --dry-run      # show planned insertions
    python3 linkback_sweep.py --apply        # apply them

Targets default to the current push manifest, which only ever holds the
newest batch. Older articles that are still unindexed need links too, so
the target set can be pointed anywhere:

    --manifest PATH          any manifest-shaped JSON (index-watch.json works)
    --slugs slug=phrase,...  explicit targets, no manifest needed
"""

import json
import os
import re
import sys

from common import (ARTICLE_URL_PATTERN, DEFAULT_MANIFEST, SHOPIFY_BLOG_ID,
                    load_env, shopify)

MAX_EDITS_PER_ARTICLE = 2
MAX_LINKS_PER_TARGET = 8  # >8 identical-anchor links in one sweep reads as spam


def fetch_all_articles():
    """Every published article, following pagination.

    A single limit=250 call silently truncates: the blog is past 300 posts
    and the REST default order is id ascending, so the un-paginated version
    returned the OLDEST 250 and never saw the newest ~60 — the posts most
    likely to mention a new article's keyword. since_id walks the whole set.
    """
    articles, since_id = [], 0
    fields = "id,handle,title,body_html,published_at"
    while True:
        status, body = shopify(
            "GET", f"blogs/{SHOPIFY_BLOG_ID}/articles.json"
                   f"?limit=250&since_id={since_id}&fields={fields}")
        if status != 200:
            raise SystemExit(f"shopify HTTP {status}")
        page = body.get("articles", [])
        if not page:
            break
        articles += page
        since_id = max(a["id"] for a in page)
        if len(page) < 250:
            break
    return [a for a in articles if a.get("published_at")]


def resolve_targets(argv):
    """Target list from --slugs, --manifest, or the default manifest."""
    if "--slugs" in argv:
        raw = argv[argv.index("--slugs") + 1]
        targets = []
        for chunk in raw.split(","):
            slug, sep, phrase = chunk.strip().partition("=")
            if not sep or not phrase.strip():
                raise SystemExit(
                    f"--slugs needs slug=phrase pairs; got '{chunk.strip()}'. "
                    "The phrase is the anchor text to link, e.g. "
                    "--slugs tangem-vs-ryder-one='tangem wallet'")
            targets.append({"slug": slug.strip(), "phrase": phrase.strip()})
    else:
        path = (argv[argv.index("--manifest") + 1] if "--manifest" in argv
                else os.environ.get("PUSH_MANIFEST", DEFAULT_MANIFEST))
        with open(path) as f:
            targets = [{"slug": m["slug"], "phrase": m["target_keyword"]}
                       for m in json.load(f) if m.get("target_keyword")]
    for t in targets:
        t["url"] = ARTICLE_URL_PATTERN.format(handle=t["slug"])
    if not targets:
        raise SystemExit("no targets with a target_keyword to link to")
    return targets


def _segments(html):
    """Split body into (text, is_linkable) segments. Text inside tags,
    anchors, and headings is not linkable."""
    parts = re.split(r"(<a\b.*?</a>|<h[1-6]\b.*?</h[1-6]>|<[^>]+>)",
                     html, flags=re.S | re.I)
    return [(p, not p.startswith("<")) for p in parts if p]


def plan_insertion(html, phrase, url):
    """Return new html with the first plain-prose mention of phrase
    linked to url, or None if no safe mention exists or the article
    already links there."""
    if url in html:
        return None
    pattern = re.compile(r"\b(" + re.escape(phrase) + r")\b", re.I)
    out, done = [], False
    for text, linkable in _segments(html):
        if not done and linkable:
            m = pattern.search(text)
            if m:
                text = (text[:m.start()]
                        + f'<a href="{url}">{m.group(1)}</a>'
                        + text[m.end():])
                done = True
        out.append(text)
    return "".join(out) if done else None


def main():
    load_env()
    apply = "--apply" in sys.argv
    if not apply and "--dry-run" not in sys.argv:
        raise SystemExit("usage: python3 linkback_sweep.py --dry-run | --apply")

    targets = resolve_targets(sys.argv)
    new_slugs = {t["slug"] for t in targets}

    articles = fetch_all_articles()
    old_articles = [a for a in articles if a["handle"] not in new_slugs]

    # Rank candidates per target: old posts whose TITLE shares a word with
    # the keyword first (topical relevance), then the rest; cap per target.
    chosen = {}  # article id -> list of targets
    for t in targets:
        kw_words = set(t["phrase"].lower().split())
        candidates = sorted(
            old_articles,
            key=lambda a: -len(kw_words & set(re.findall(r"\w+", a["title"].lower()))))
        picked = 0
        for art in candidates:
            if picked >= MAX_LINKS_PER_TARGET:
                break
            if len(chosen.get(art["id"], [])) >= MAX_EDITS_PER_ARTICLE:
                continue
            if plan_insertion(art["body_html"] or "", t["phrase"], t["url"]):
                chosen.setdefault(art["id"], []).append(t)
                picked += 1

    total = 0
    for art in old_articles:
        edits = chosen.get(art["id"], [])
        if not edits:
            continue
        html = art["body_html"] or ""
        applied_edits = []
        for t in edits:
            updated = plan_insertion(html, t["phrase"], t["url"])
            if updated:
                html = updated
                applied_edits.append(t)
        total += len(applied_edits)
        label = "APPLY" if apply else "PLAN "
        for t in applied_edits:
            print(f"{label} {art['handle']}: link '{t['phrase']}' -> {t['slug']}")
        if apply and applied_edits:
            status, body = shopify(
                "PUT", f"blogs/{SHOPIFY_BLOG_ID}/articles/{art['id']}.json",
                {"article": {"id": art["id"], "body_html": html}})
            if status != 200:
                print(f"  ERROR updating {art['handle']}: HTTP {status}")
    print(f"{'applied' if apply else 'planned'}: {total} insertions "
          f"across {len(old_articles)} candidate articles")


if __name__ == "__main__":
    main()
