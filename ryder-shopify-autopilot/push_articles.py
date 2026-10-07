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
    REGEN_BUDGET_S=38 perl -e 'alarm 41; exec @ARGV' python3 push_articles.py

    (macOS ships no `timeout`/`gtimeout`; the perl alarm is the portable
    stand-in for the outer backstop. It exits 142 when it fires, so it
    never collides with this script's exit 2 = "articles remaining".)
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
                    notion_mark_published, notion_page_owners, shopify,
                    slack_announce)
from generate_visuals import BRAND_DIR, generate_hero
from prepublish_check import check_article


def topic_art_path(slug):
    """Per-article engraving from SKILL.md step 4. Its absence means the hero
    fell back to the generic gravure texture, which must never be announced."""
    return os.path.join(BRAND_DIR, "art", f"{slug}.png")

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

    # Hard rule: autopilot never publishes (and so never re-statuses) a
    # page a human owns. Checked here, not just at manifest-build time, so
    # a manifest built by any other route still can't slip one through.
    # Fails closed: an unverifiable page is skipped, not published.
    page_id = item.get("notion_page_id")
    if page_id:
        ok, owners = notion_page_owners(page_id)
        if not ok:
            return {"slug": slug, "ok": False,
                    "error": f"owner check failed: {owners}"}
        if owners:
            return {"slug": slug, "ok": False, "terminal": True,
                    "error": "skipped: human-owned (" + ", ".join(owners) + ")"}

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

    # Never announce a post that shipped on the fallback gravure art. The
    # publish itself still goes through (SKILL.md step 4 says art failure
    # must not block it), but Slack is the shop window: generate the topic
    # engraving, re-run the hero, then announce.
    if not os.path.exists(topic_art_path(slug)):
        result["slack_announced"] = False
        result["slack_skipped"] = ("no topic artwork at assets/brand/art/"
                                   f"{slug}.png; generate it per visual-system.md, "
                                   "rebuild the hero, then announce")
    elif os.environ.get("PUSH_ANNOUNCE", "1") == "1":
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

    # Pre-flight: surface missing topic art before anything publishes, so the
    # step-4 engraving gets generated up front rather than noticed afterwards.
    missing_art = [i["slug"] for i in manifest
                   if not os.path.exists(topic_art_path(i["slug"]))]
    if missing_art:
        print(f"WARNING: no topic artwork for {len(missing_art)} article(s); "
              "these will publish on the fallback gravure and will NOT be "
              "announced in Slack:")
        for slug in missing_art:
            print(f"  - {slug}")
        print("  generate per visual-system.md into assets/brand/art/<slug>.png")

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
        # Enter the index watch at push time, not at check time. The manifest
        # is rewritten for every new batch, so anything that reads it later
        # has already lost this slug — indexing takes days, batches take hours.
        if outcome.get("ok") and not dry_run:
            from index_watch import add_items
            add_items([item])
        tag = "OK " if outcome.get("ok") else "ERR"
        print(f"{tag} {item['slug']} -> {outcome.get('live_url', outcome.get('error'))}")

    # Terminally-skipped articles (human-owned) are settled, not pending:
    # counting them as remaining would hold the exit code at 2 and spin the
    # caller's retry loop for nothing. They stay out of `done` above, so a
    # later run re-checks them if ownership changes.
    settled = {r["slug"] for r in results if r.get("ok") or r.get("terminal")}
    remaining = [i["slug"] for i in manifest if i["slug"] not in settled]
    print(f"done: {len(manifest) - len(remaining)}/{len(manifest)}"
          + (f", remaining: {', '.join(remaining)}" if remaining else ""))
    sys.exit(0 if not remaining else 2)


if __name__ == "__main__":
    main()
