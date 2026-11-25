---
name: ryder-shopify-autopilot
description: Publish approved Ryder blog articles from Notion to Shopify automatically. Queries the Notion content database for articles with Status "Approved for publishing", runs the editorial gate, pushes them to the Shopify blog with a generated hero image, marks them Published in Notion with the live URL, and announces in Slack. Use on a configured schedule or when asked to "publish approved articles" or "run the autopilot".
---

# Ryder Shopify Autopilot

For new article ideas or drafts, first use
`.claude/skills/ryder-buyer-seo/SKILL.md`. This skill starts once a page's
Notion status is `Approved for publishing`, set either by Louise or by the
scheduled drafter's auto-approval. A selector `draft_brief` alone is not
approval; a finished, gate-passing draft is.

Auto-approval (Louise, 2026-11-24): the scheduled drafter approves its own finished drafts by setting `Approved for publishing` after they pass the editorial gate and its source checks, and stamps the page's internal review notes with "Auto-approved by ryder-article-drafter". The autopilot publishes those pages exactly like human-approved ones; never skip a page because automation approved it.
The scheduled-agent step below filters Notion status; `push_articles.py`
itself trusts its manifest and does not recheck that status.

Daily drafts start with `notion_topic_intake.py` pulling `Topic queued`
pages from the existing Content Calendar. Follow the buyer skill for research
and review: Grok supplies unverified keyword seeds, never volume, difficulty,
SERP reviews or `product_fit`. Always run the repository's keyword research
and a live US/English SERP inspection for each queued seed. Record today's
SERP review; only then explicitly claim a `draft_brief` as `Drafting` and run the
editorial gate. `push_to_notion_idea.py --page-id PAGE_ID draft.md` then
appends the draft and SEO callout to that same page and lands it at `Idea`.
Keep `notion_page_id` in the draft metadata and the publishing manifest.
After the draft lands at `Idea`, the drafter sets `Approved for publishing`
itself (auto-approval). It never writes or clears `Owner`.
`update_existing` stays `Research needed` with a refresh/link note;
`reject` gets Status `Archived` with a note, without deleting the page.
This repository does not activate a Claude schedule; any schedule is
configured separately.

Runs unattended. All constants and credential handling live in
`common.py`; credentials come from `CLAUDE OUTPUTS/Ryder One/shopify.env`
and must never be echoed in output or logs.

## Steps

1. Query the Notion Content Calendar database
   (`20a0b656-6cfd-8067-82de-eddd645ae75e`) for pages with
   `Status = "Approved for publishing"` (exact option name). One query,
   filter on the `Status` status property. If none: report "no approved
   articles" and stop.
2. For each approved page, confirm a body draft exists (staged in
   `/tmp/visual-test/push-bodies/<slug>.md` or matching
   `CLAUDE OUTPUTS/Ryder One/rewrites/*<slug>*.md`). Pages without a body
   are skipped with a note; never invent content at publish time.
3. Build the manifest at `CLAUDE OUTPUTS/Ryder One/outputs/articles-to-push.json`
   using the schema in CONTENT-MACHINE-SETUP.md (notion_page_id, slug,
   title, seo_title, meta_description, hero_alt, target_keyword,
   blog_categories_raw = ["Industry Insights"], content_angle).
4. Topic artwork (branding guideline, see visual-system.md): for each
   article missing `assets/brand/art/<slug>.png`, pick ONE concrete object
   that stands for the topic (`art_subject` in the manifest if present;
   dice for randomness, vault door for cold storage, shipping box for a
   shipping leak) and describe it so it reads TALLER than wide, then run
   `python3 gemini_art.py <slug> "<subject>"`. It uses the house prompt,
   Google Gemini (GEMINI_API_KEY in shopify.env, gemini-3-pro-image first),
   a second model's check for text, faces, logos and a white ground, and
   one retry. Open the PNG: if the object is a thin sliver (width_to_height
   under about 0.5) or reads wrong, rerun once with a fuller, more compact
   description. Never use vidIQ.
   Backup only if gemini_art.py exits non-zero (credit, quota or outage):
   draw the art with `engrave_art.py` from an SVG of simple toned shapes
   (see that file's docstring; keep the drawing no wider than ~0.8x its
   height), and say in the summary that the cover used the backup.
   For an article already live without good art, add the art and run
   `python3 refresh_hero.py <slug>` (it swaps the Shopify cover and posts
   the held-back Slack announcement; `--no-announce` if one already went out).
5. Run the push in budget slices until complete:
   ```bash
   cd ryder-shopify-autopilot   # from the repository root
   REGEN_BUDGET_S=38 perl -e 'alarm 41; exec @ARGV' python3 push_articles.py
   ```
   macOS has no `timeout`/`gtimeout` binary, so the perl alarm stands in
   for it: same hard backstop, no install. It exits 142 when it fires.
   Repeat while the exit code is 2 (articles remaining). The script
   handles the editorial gate, hero generation (topic art + colorway per
   visual-system.md), dedup, the Notion Published update, and the Slack
   announcement itself.
6. Link-back sweep (feeds internal authority to the new posts):
   `python3 linkback_sweep.py --dry-run`, sanity-check the plan (capped
   at 8 links per new article, 2 edits per old article, relevance-ranked),
   then `python3 linkback_sweep.py --apply`.
7. If `CLAUDE OUTPUTS/Ryder One/gsc-service-account.json` exists, run
   `python3 gsc.py sitemap` so Google re-reads the sitemap with the new
   URLs. Skip silently if the key file is absent.
8. Read `/tmp/visual-test/push-results.json` and report a one-line
   summary per article: slug, live URL or error, plus the link-back
   count.

## Hard rules

- Gate failures stop that article; never set `PUSH_SKIP_CHECKLIST=1`.
- Step 4 is not optional. Every article gets its own engraving at
  `assets/brand/art/<slug>.png` before the push. `push_articles.py`
  warns up front about any manifest entry missing art and refuses to
  announce that article in Slack, because the fallback gravure must
  never go out as a launch. If art generation fails, the publish still
  proceeds (per step 4), but fix the art and rebuild the hero before
  announcing.
- Never delete anything in Shopify or Notion. Shopify's helper restricts
  methods to GET/POST/PUT; Notion updates use PATCH without trashing records.
- Tag is exactly `Industry Insights`; the scripts enforce this.
- Do not change the status of any human-owned page. A page is
  human-owned if its Notion `Owner` people property has any value;
  autopilot only publishes pages with an empty `Owner`. Skip owned pages
  at manifest-build time and list them as "skipped: human-owned (<name>)".
- Never set or clear `Owner`. Missing/malformed ownership data or a failed
  lookup blocks the page too.
- If Shopify auth fails, report it and stop; do not retry in a loop.
