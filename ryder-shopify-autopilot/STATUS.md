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

## Python deps (installed)
Pillow 11.3.0, cairosvg 2.8.2 (+ brew cairo, symlinked into ~/lib),
markdown. All on system Python 3.9.
