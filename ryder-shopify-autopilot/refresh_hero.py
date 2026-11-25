"""Swap in topic art for an article that already went live on the fallback.

push_articles.py publishes even when topic art is missing (an art failure
must not block a publish), uses the generic gravure, and holds back the
Slack announcement. Once assets/brand/art/<slug>.png exists, this rebuilds
the hero from the draft's .meta.json, replaces the live article's image on
Shopify, and posts the announcement that was held back.

    python3 refresh_hero.py <slug> [<slug> ...]            # hero + announce
    python3 refresh_hero.py --no-announce <slug> [...]      # hero only

Never deletes anything; never touches body, title, tags or Notion.
"""
import glob
import json
import os
import re
import sys

from common import (HEROES_DIR, REWRITES_DIR, SHOPIFY_BLOG_ID, b64_file,
                    load_env, shopify, slack_announce)
from generate_visuals import BRAND_DIR, generate_hero

LIVE = "https://ryder.id/blogs/post/{}"


def meta_for(slug):
    hits = [p for p in glob.glob(os.path.join(REWRITES_DIR, f"*{slug}*.meta.json"))
            if json.load(open(p)).get("slug") == slug]
    if len(hits) != 1:
        raise ValueError(f"expected one .meta.json for {slug}, found {len(hits)}")
    return json.load(open(hits[0]))


def refresh(slug, announce=True):
    art = os.path.join(BRAND_DIR, "art", f"{slug}.png")
    if not os.path.exists(art):
        return {"slug": slug, "ok": False, "error": f"no topic art at {art}"}
    meta = meta_for(slug)
    status, body = shopify(
        "GET", f"blogs/{SHOPIFY_BLOG_ID}/articles.json?handle={slug}")
    articles = body.get("articles", []) if status == 200 and isinstance(body, dict) else []
    if not articles:
        return {"slug": slug, "ok": False, "error": f"not live on Shopify (HTTP {status})"}
    article = articles[0]

    os.makedirs(HEROES_DIR, exist_ok=True)
    hero_title = re.sub(r"\s*\|\s*Ryder\s*$", "",
                        meta.get("seo_title") or meta["title"])
    hero = generate_hero(hero_title, slug, os.path.join(HEROES_DIR, f"{slug}.png"),
                         subtitle=meta.get("hero_subtitle"),
                         colorway=meta.get("hero_colorway"))
    status, body = shopify(
        "PUT", f"blogs/{SHOPIFY_BLOG_ID}/articles/{article['id']}.json",
        {"article": {"id": article["id"],
                     "image": {"attachment": b64_file(hero),
                               "alt": meta.get("hero_alt", "")}}})
    if status != 200:
        return {"slug": slug, "ok": False, "error": f"image update HTTP {status}"}
    result = {"slug": slug, "ok": True, "hero": hero, "live_url": LIVE.format(slug)}
    if announce:
        # meta_description is the public summary; content_angle is internal
        ok, err = slack_announce(meta["title"], meta.get("meta_description", ""),
                                 LIVE.format(slug))
        result["slack_announced"] = ok
        if not ok:
            result["slack_error"] = str(err)[:200]
    return result


def main(argv):
    announce = "--no-announce" not in argv
    slugs = [a for a in argv[1:] if not a.startswith("--")]
    if not slugs:
        raise SystemExit(__doc__)
    load_env()
    out = [refresh(s, announce) for s in slugs]
    print(json.dumps(out, indent=2))
    return 0 if all(r["ok"] for r in out) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
