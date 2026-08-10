"""Push approved Ryder articles to Shopify.

Reads the manifest (articles-to-push.json), and for each article:
gate-check -> hero image -> dedup against Shopify -> create article ->
Notion Status=Published + Post URL -> Slack announcement. Results are
appended to push-results.json after every article, so the script can be
run repeatedly in time-boxed slices until everything reports ok or
dedup_skip (see CONTENT-MACHINE-SETUP.md).

Env overrides:
    REGEN_BUDGET_S=38        seconds per budget slice (0 = no budget)
    PUSH_HERO_ONLY=1         skip body images (default on)
    PUSH_SKIP_CHECKLIST=1    bypass editorial gate (emergency only)
    PUSH_MANIFEST=/path      custom manifest path
    PUSH_DRY_RUN=1           everything except writes to Shopify/Notion/Slack
    PUSH_UPDATE_NOTION=0     skip the Notion status update
    PUSH_ANNOUNCE=0          skip the Slack announcement

Usage:
    REGEN_BUDGET_S=38 timeout 41 python3 push_articles.py
"""

import glob
import json
import os
import re
import sys
import time

import common
from common import (ARTICLE_TAG, ARTICLE_URL_PATTERN, BODIES_DIR,
                    DEFAULT_MANIFEST, HEROES_DIR, RESULTS_FILE, REWRITES_DIR,
                    SHOPIFY_BLOG_ID, b64_file, load_env, md_to_html,
                    notion_mark_published, shopify, slack_announce)
from generate_visuals import generate_hero
from prepublish_check import check_article

# Explicit slug -> body file overrides (setup guide step 7). The default
# resolution order below finds staged bodies without an entry here.
BODY_BY_SLUG = {}


def find_body(slug):
    candidates = [os.path.join(BODIES_DIR, f"{slug}.html"),
                  os.path.join(BODIES_DIR, f"{slug}.md")]
    if slug in BODY_BY_SLUG:
        candidates.insert(0, BODY_BY_SLUG[slug])
    candidates += sorted(glob.glob(os.path.join(REWRITES_DIR, f"*{slug}*.md")))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_results():
    try:
        with open(RESULTS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_results(results):
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def article_exists(slug):
    status, body = shopify("GET",
                           f"blogs/{SHOPIFY_BLOG_ID}/articles.json?handle={slug}")
    if status == 200 and isinstance(body, dict):
        articles = body.get("articles", [])
        return articles[0] if articles else None
    return None


def push_one(item, dry_run=False):
    slug = item["slug"]
    live_url = ARTICLE_URL_PATTERN.format(handle=slug)

    body_path = find_body(slug)
    if not body_path:
        return {"slug": slug, "ok": False, "error": "body file not found"}
    with open(body_path) as f:
        body_raw = f.read()
    # The Shopify theme renders the article title itself; a leading H1 in
    # the body would duplicate it on the page.
    body_md = re.sub(r"^#\s+.*\n+", "", body_raw.lstrip(), count=1)
    body_html = body_raw if body_path.endswith(".html") else md_to_html(body_md)

    # Editorial gate (rule 6: must pass before Shopify)
    if os.environ.get("PUSH_SKIP_CHECKLIST") != "1":
        gate = check_article(body_raw, mode="shopify")
        if not gate["passed"]:
            return {"slug": slug, "ok": False,
                    "error": "gate failed: " + "; ".join(gate["errors"][:6])}

    # Dedup (rule 7 adjacent: never double-publish)
    existing = article_exists(slug)
    if existing:
        return {"slug": slug, "ok": True, "dedup_skip": True,
                "live_url": live_url}

    hero_path = os.path.join(HEROES_DIR, f"{slug}.png")
    if not os.path.exists(hero_path):
        # Banners use the short SEO title + subtitle per the brand template;
        # a "| Ryder" SEO suffix stays in the meta tag but not on the art.
        import re as _re
        hero_title = _re.sub(r"\s*\|\s*Ryder\s*$", "",
                             item.get("seo_title") or item["title"])
        hero_path = generate_hero(hero_title, slug,
                                  subtitle=item.get("hero_subtitle"),
                                  colorway=item.get("hero_colorway"))

    if dry_run:
        return {"slug": slug, "ok": True, "dry_run": True, "live_url": live_url,
                "hero": hero_path}

    payload = {"article": {
        "title": item["title"],
        "handle": slug,
        "author": "Ryder",
        "tags": ARTICLE_TAG,  # exactly one tag (rule 1)
        "body_html": body_html,
        "published": True,
        "image": {"attachment": b64_file(hero_path),
                  "alt": item.get("hero_alt", "")},
        "metafields": [
            {"namespace": "global", "key": "title_tag", "type": "single_line_text_field",
             "value": item.get("seo_title", item["title"])[:70]},
            {"namespace": "global", "key": "description_tag", "type": "single_line_text_field",
             "value": item.get("meta_description", "")[:320]},
        ],
    }}
    status, body = shopify("POST", f"blogs/{SHOPIFY_BLOG_ID}/articles.json", payload)
    if status not in (200, 201):
        err = body.get("errors") if isinstance(body, dict) else str(body)[:300]
        return {"slug": slug, "ok": False, "error": f"shopify HTTP {status}: {err}"}

    result = {"slug": slug, "ok": True, "live_url": live_url,
              "article_id": body["article"]["id"]}

    if os.environ.get("PUSH_UPDATE_NOTION", "1") == "1" and item.get("notion_page_id"):
        ok, err = notion_mark_published(item["notion_page_id"], live_url)
        result["notion_updated"] = ok
        if not ok:
            result["notion_error"] = str(err)[:200]

    if os.environ.get("PUSH_ANNOUNCE", "1") == "1":
        ok, err = slack_announce(item["title"],
                                 item.get("content_angle", ""), live_url)
        result["slack_announced"] = ok
        if not ok:
            result["slack_error"] = err

    return result


def main():
    load_env()
    started = time.time()
    budget = float(os.environ.get("REGEN_BUDGET_S", "0") or 0)
    dry_run = os.environ.get("PUSH_DRY_RUN") == "1"

    manifest_path = os.environ.get("PUSH_MANIFEST", DEFAULT_MANIFEST)
    with open(manifest_path) as f:
        manifest = json.load(f)

    results = load_results()
    done = {r["slug"] for r in results if r.get("ok")}

    for item in manifest:
        if item["slug"] in done:
            continue
        if budget and time.time() - started > budget:
            print(f"budget reached ({budget}s); run again to continue")
            break
        outcome = push_one(item, dry_run=dry_run)
        results = [r for r in results if r["slug"] != item["slug"]] + [outcome]
        save_results(results)
        tag = "OK " if outcome.get("ok") else "ERR"
        print(f"{tag} {item['slug']} -> {outcome.get('live_url', outcome.get('error'))}")

    remaining = [i["slug"] for i in manifest
                 if i["slug"] not in {r["slug"] for r in results if r.get("ok")}]
    print(f"done: {len(manifest) - len(remaining)}/{len(manifest)}"
          + (f", remaining: {', '.join(remaining)}" if remaining else ""))
    sys.exit(0 if not remaining else 2)


if __name__ == "__main__":
    main()
