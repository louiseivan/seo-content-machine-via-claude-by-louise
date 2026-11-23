# ryder-shopify-autopilot — folder status

Last updated: 2026-11-24 (Notion topic intake and same-page draft handoff)

## Notion intake and draft handoff

- `notion_topic_intake.py` reads `Topic queued`, prefers `Blog`, skips
  human-owned pages, and fails closed on unknown ownership. It maps the
  existing properties without inventing product-fit or SERP reviews, runs
  fresh US/en keyword overview JSON for every seed, then the existing selector.
  Grok provides only topic seeds/context, never search volume, keyword
  difficulty, SERP reviews or `product_fit`. Cached metrics do not skip live
  research; `--research` is for dry-run previews only.
- Every queued seed requires a live US/English SERP inspection by Claude/a
  human, with the query/result URL, intent notes and today's `reviewed_on`.
  Intake lists these checks and blocks drafting without a current-day review.
  It does not fabricate reviews or implement a separate SERP API.
- `--dry-run --output /tmp/ryder-topics.json` prints candidates, planned
  research and status writes. Dry-run never writes Notion and calls no paid
  providers unless `--research-in-dry-run` is explicitly supplied.
- `research_needed` -> `Research needed`; `reject` -> Status `Archived`
  plus a note; `update_existing` -> `Research needed` plus a refresh/link
  note. No record is deleted and no duplicate article is started.
- Reviewed exports can be passed back with `--candidates`; live runs repeat
  keyword research, including when claiming a page.
  `--claim PAGE_ID` moves only a recomputed `draft_brief` to `Drafting` when
  Claude starts writing. Failed/missing reviews cannot claim a page.
- A passing draft and sibling `.meta.json` go through
  `push_to_notion_idea.py --page-id PAGE_ID draft.md` (or metadata
  `notion_page_id`). It enforces `prepublish_check.py`, appends the body/SEO
  callout without deleting notes, and sets `Idea` on the same page. Reruns
  append revisions; inspect partial failed uploads before retrying. Existing
  pages must still be unowned and in `Drafting`/`Idea`; local drafts without
  a known page ID retain the create path.
- Intake/drafting is hard-blocked from `Approved for publishing`. `Owner`
  is never set or cleared; intake leaves `Post URL` and `Publish date` alone.
  The existing publishing workflow remains separate and uses the same page ID.
- Offline unittest coverage exercises mapping, evidence recovery, transitions,
  ownership failures, dry-run, and same-page uploads. No live Notion/provider
  smoke test or schedule activation was performed for this change.

Schedule entries below describe historical, separately configured local
tasks. This repository does not activate or verify any Claude schedule.
Daily draft tasks should now start with the intake above and land `Idea`
on the original queued page.

## Historical pipeline notes

The original Cowork scripts were lost; everything below is a local
rebuild driven by CONTENT-MACHINE-SETUP.md and
RYDER_CONTENT_SYSTEM_PROMPT.md. Paths are localized for this machine
(no /sessions/.../mnt/ anywhere).

## Built and smoke-tested
- `common.py` — shared config, env loading, Shopify/Notion/Slack helpers.
  Shopify layer only allows GET/POST/PUT (delete rule enforced in code).
- `prepublish_check.py` — editorial gate; encodes the full pre-publish
  checklist incl. banned words, em dashes, rhythm, contrast, prices
  ($149/$179 current), banned spec phrasings, TapSafe-in-backup-sections.
  Tested: catches 10/10 planted violations, passes a clean draft.
- `generate_visuals.py` — 1200x630 hero per visual-system.md. Tested,
  renders. Uses system Helvetica until brand fonts land in assets/fonts/.
- `inject_images_into_body.py` — body-image injector (idle while
  PUSH_HERO_ONLY=1 default).
- `push_articles.py` — orchestrator: gate → hero → dedup → Shopify →
  Notion Published → Slack. Budget slices via REGEN_BUDGET_S, results in
  /tmp/visual-test/push-results.json, PUSH_DRY_RUN=1 supported. Exit
  code 2 = articles remaining.
- `SKILL.md` — autopilot skill definition.
- `visual-system.md` — rebuilt hero design spec (original lost;
  hero-template.html superseded by generate_visuals.py).

## Credentials / API status (checked 2026-08-10)
- Shopify: WORKING. Note: shop is `ryder-id.myshopify.com` (the guide's
  old `ryder-rzg6170` subdomain is dead; both docs corrected). Blog
  111885680943 (`post`) confirmed, plus glossary 120709939503 and
  guides 121655329071.
- Slack: WORKING (bot `seo_automation` in the Ryder workspace).
- Notion: WORKING (connected 2026-08-10 via integration "SEO Automation
  by Louise"). Two corrections vs the setup guide: the real database is
  "Content Calendar" `20a0b656-6cfd-8067-82de-eddd645ae75e` (guide's ID
  is its data-source/collection ID `20a0b656-6cfd-8051-ac3e-000b9cbbd53f`,
  not a bad database ID), and the trigger status option is exactly
  "Approved for publishing", not "Approved". Both fixed in common.py,
  SKILL.md, and the guide. 10 items sit in that status as of today, but
  several look like non-blog content (IG captions); review before any
  autopilot run, and no local body drafts exist yet in any case.

## Still missing (nice-to-have, not blocking)
- `assets/fonts/` — AnekLatin, Geist, Poppins files
- `assets/logo/` — Ryder SVG logo
- `assets/product-renders/` — product photos
- `Ryder_SEO_Content_Report_Q2_2026.docx` in CLAUDE OUTPUTS/Ryder One/
- ~~Hourly scheduled task for the autopilot~~ DONE 2026-08-10: runs at
  :06 every hour (task id `ryder-shopify-autopilot`; only while the
  Claude app is open). The `ryder-icp-country-review` one-shot is also
  scheduled: fires 2026-09-22 09:00, asks the Aisha question, then
  reschedules itself 8 weeks out.

## Index watch (added 2026-08-11)
- `index_watch.py` keeps `outputs/index-watch.json`, a durable list of
  pushed slugs tracked until Google reports them indexed. Slugs are added
  automatically by `push_articles.py` on a successful push, or manually
  with `index_watch.py add [--manifest PATH]`.
- Why: `articles-to-push.json` is rewritten per batch (hours), while
  indexing takes days. Anything reading "the current manifest" for index
  status silently dropped articles before Google had crawled them. The
  `ryder-index-watch` scheduled task now reads the watch list instead.
- `linkback_sweep.py` gained `--manifest PATH` and `--slugs slug=phrase`
  so internal links can be fed to older orphans, not just the newest batch.
- Fixed in the same pass: `fetch_all_articles()` was a single limit=250
  call against a 310-post blog, returning the OLDEST 250 in id order and
  never seeing the newest ~60. Now paginates via `since_id`; the candidate
  pool went 244 -> 266 and a dry run went from 1 to 10 planned insertions.

## Daily drafts + toolchain notes (added 2026-08-13)
- A separately configured `ryder-daily-drafts` task was recorded at 07:07
  daily. Its current configuration is not verified here. Daily drafts should
  now pull `Topic queued`, research/select, explicitly claim `Drafting`, run
  `prepublish_check.py`, and update the same page via
  `push_to_notion_idea.py` at Status "Idea". They are hard-blocked from
  setting "Approved for publishing": the human approval gate is what keeps
  unread drafts off Shopify.
- `timeout`/`gtimeout` do not exist on this machine, so the documented
  `timeout 41 python3 push_articles.py` exited 127 and pushed nothing.
  Replaced everywhere with `perl -e 'alarm 41; exec @ARGV'` (/usr/bin/perl
  is always present). It exits 142 on kill, which never collides with the
  script's exit 2 = "articles remaining".
- `trends_spikes.py` with no args fires all 8 seeds back to back and
  reliably 429s. Two or three seeds per invocation works. Not a code bug:
  run it in small batches.
- DataForSEO and Ahrefs are both live and verified. A one-off 403 (40104)
  on a Labs call was transient; `/v3/appendix/user_data` returns 20000 with
  a positive balance. Expect the two providers to disagree on volume and
  difficulty; that spread is worth reading, not averaging.
- `ryder-index-watch` had been sitting disabled; re-enabled 2026-08-13.
- TRAP: `PUSH_DRY_RUN=1` writes `ok: true` records into
  `/tmp/visual-test/push-results.json`, and `main()` builds its skip set as
  `{r["slug"] for r in results if r.get("ok")}`. A dry run therefore marks
  every article permanently done, and the live run that follows prints
  "done: 4/4" while pushing nothing. Verify against Shopify and Notion
  rather than trusting that line. Until this is fixed, either skip the dry
  run or strip the dry-run slugs from push-results.json before going live.

## Python deps (installed)
Pillow 11.3.0, cairosvg 2.8.2 (+ brew cairo, symlinked into ~/lib),
markdown. All on system Python 3.9.
