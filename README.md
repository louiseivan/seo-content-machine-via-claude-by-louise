# SEO Content Machine via Claude by Louise

An automated SEO blog pipeline built in one day with [Claude Code](https://claude.com/claude-code), running in production at [ryder.id](https://ryder.id) (Ryder makes the Ryder One hardware wallet). Published here so other teams can borrow the architecture.

## What it does

```
keyword research ──► drafting (parallel agents) ──► editorial gate (code, not vibes)
      │                                                      │
   Ahrefs /                                                  ▼
  DataForSEO                                    brand cover generation (Figma tokens)
      │                                                      │
      ▼                                                      ▼
Google Search Console ◄── link-back sweep ◄── Shopify publish ──► Notion + Slack
 (sitemap + index watch)
```

Every hour, a scheduled agent checks a Notion content calendar for approved articles and ships them end to end: editorial gate, cover image, Shopify article with SEO metafields, Notion status update with the live URL, Slack announcement, internal link-backs from older posts, and a sitemap resubmission to Google.

## The interesting parts

- **`prepublish_check.py`** — an editorial style guide enforced as code. Banned-word scans, sentence-rhythm heuristics, price verification, claim-citation rules. A draft physically cannot ship while failing. This is the piece that keeps 100% automated content from reading like 100% automated content.
- **`generate_visuals.py`** — on-brand cover images with zero design tools at runtime: brand tokens extracted from Figma once, variable fonts (weight/width axes via Pillow), four colorways, per-article engraved illustrations composited so line art inherits the colorway's ink.
- **`linkback_sweep.py`** — new posts get internal links from topically-related older posts, with anti-spam caps (max 8 per new post, relevance-ranked, never inside anchors/headings).
- **`keyword_research.py`** — merges Ahrefs and DataForSEO per keyword so volumes can be cross-checked; degrades gracefully when a provider is missing.
- **`gsc.py`** — Search Console service-account integration: performance queries, per-URL index inspection, sitemap submission. Paired with a daily scheduled task that watches new posts until Google indexes them, then disables itself.

## Layout

- `ryder-shopify-autopilot/` — all pipeline code + the autopilot skill definition (`SKILL.md`), visual spec (`visual-system.md`), status (`STATUS.md`)
- `CLAUDE OUTPUTS/Ryder One/rewrites/` — published article drafts with their metadata sidecars, as real examples of gate-passing output

## Running it yourself

1. Copy `CLAUDE OUTPUTS/Ryder One/shopify.env.example` to `shopify.env` and fill your credentials (Shopify custom app, Notion integration, Slack bot, keyword APIs). A GSC service-account JSON enables the indexing tools.
2. Swap the constants in `common.py` (shop, blog ID, Notion database, Slack channel) for yours.
3. Replace the brand assets and editorial rules with your own — the gate's checks in `prepublish_check.py` are the template; the taste encoded in them should be yours.
4. Python 3.9+, deps: `Pillow cairosvg markdown google-auth requests` (plus native cairo).

## License

Code is MIT (see LICENSE). The Ryder name, logo, brand assets, and article content are © Ryder / Light Labs — use the machinery, not the brand. Fonts are SIL OFL (see `ryder-shopify-autopilot/assets/fonts/FONT-LICENSES.md`).

Built 2026-08-10 by Louise Ivan (co-founder/CXO, Ryder) pair-working with Claude.
