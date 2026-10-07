---
name: ryder-shopify-autopilot
description: Publish approved Ryder blog articles from Notion to Shopify automatically. Queries the Notion content database for articles with Status "Approved for publishing", runs the editorial gate, pushes them to the Shopify blog with a generated hero image, marks them Published in Notion with the live URL, and announces in Slack. Use on a configured schedule or when asked to "publish approved articles" or "run the autopilot".
---

# Ryder Shopify Autopilot

For new article ideas or drafts, first use
`.claude/skills/ryder-buyer-seo/SKILL.md`. This skill starts only after a
human has set the Notion page status to `Approved for publishing`. The
selector's `draft_brief` result never constitutes publishing approval.
The scheduled-agent step below filters Notion status; `push_articles.py`
itself trusts its manifest and does not recheck that status.

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
   article missing `assets/brand/art/<slug>.png`, generate an engraving
   with vidiq_generate_thumbnail using the house prompt from
   visual-system.md, filling `<subject>` with a concrete object that
   stands for the article's topic (from `art_subject` in the manifest if
   present, else choose one). Poll vidiq_job_poll, download the PNG to
   `assets/brand/art/<slug>.png`. If generation fails, continue with the
   fallback gravure art rather than blocking the publish; note it in the
   summary. Never let generated art contain text, faces, or logos: if it
   does, regenerate once, then fall back.
5. Run the push in budget slices until complete:
   ```bash
   cd /Users/l/CodingStudio/ryder-shopify-autopilot
   REGEN_BUDGET_S=38 timeout 41 python3 push_articles.py
   ```
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
- Never delete anything in Shopify or Notion (the API layer only allows
  GET/POST/PUT).
- Tag is exactly `Industry Insights`; the scripts enforce this.
- Do not change the status of articles owned by Nish.
- If Shopify auth fails, report it and stop; do not retry in a loop.
