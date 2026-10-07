# ryder-shopify-autopilot — folder status

Last updated: 2026-08-10 (pipeline rebuilt from scratch this session)

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
  was a bad copy), and the trigger status option is exactly
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
- `ryder-daily-drafts` scheduled task added: 07:07 daily, ahead of the
  hourly autopilot and the 09:35 index watch. Researches topics, drafts 3
  articles, runs `prepublish_check.py`, then creates Notion cards via
  `push_to_notion_idea.py` at Status "Idea". It is hard-blocked from
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
