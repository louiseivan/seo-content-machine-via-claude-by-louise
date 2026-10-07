# SEO Content Machine via Claude by Louise

An automated SEO blog pipeline built in one day with [Claude Code](https://claude.com/claude-code), running in production at [ryder.id](https://ryder.id) (Ryder makes the Ryder One hardware wallet). Published here so other teams can borrow the architecture.

## What it does

```
keyword research ──► buyer topic selection ──► drafting ──► editorial gate
      │                                                      │
   Ahrefs /                                                  ▼
  DataForSEO                                    brand cover generation (Figma tokens)
      │                                                      │
      ▼                                                      ▼
Google Search Console ◄── link-back sweep ◄── Shopify publish ──► Notion + Slack
 (sitemap + index watch)
```

When separately configured, a scheduled Claude agent can check a Notion content calendar for approved articles and ship them end to end: editorial gate, cover image, Shopify article with SEO metafields, Notion status update with the live URL, Slack announcement, internal link-backs from older posts, and a sitemap resubmission to Google.

## The interesting parts

- **`prepublish_check.py`** — an editorial style guide enforced by the normal publishing path. Banned-word scans, sentence-rhythm heuristics, price and claim review markers. The publisher has an emergency bypass environment flag, so this is an operational gate rather than an unconditional guarantee.
- **`generate_visuals.py`** — on-brand cover images with zero design tools at runtime: brand tokens extracted from Figma once, variable fonts (weight/width axes via Pillow), four colorways, per-article engraved illustrations composited so line art inherits the colorway's ink.
- **`linkback_sweep.py`** — new posts get internal links from topically-related older posts, with anti-spam caps (max 8 per new post, relevance-ranked, never inside anchors/headings).
- **`keyword_research.py`** — merges Ahrefs and DataForSEO per keyword so volumes can be cross-checked; degrades gracefully when a provider is missing.
- **`topic_selector.py`** — turns research and human buyer review into draft briefs, research-needed lists, existing-page updates, or rejects. Search volume never overrides failed product fit. See [the Claude topic skill](.claude/skills/ryder-buyer-seo/SKILL.md).
- **`gsc.py`** — Search Console service-account integration: performance queries, per-URL index inspection, sitemap submission. Paired with a daily scheduled task that watches new posts until Google indexes them, then disables itself.

## Layout

- `ryder-shopify-autopilot/` — all pipeline code + the autopilot skill definition (`SKILL.md`), visual spec (`visual-system.md`), status (`STATUS.md`)
- `CLAUDE OUTPUTS/Ryder One/rewrites/` — published article drafts with their metadata sidecars, as real examples of gate-passing output

## Running it yourself

1. Copy `CLAUDE OUTPUTS/Ryder One/shopify.env.example` to `shopify.env` and fill your credentials (Shopify custom app, Notion integration, Slack bot, keyword APIs). A GSC service-account JSON enables the indexing tools.
2. Swap the constants in `common.py` (shop, blog ID, Notion database, Slack channel) for yours.
3. Replace the brand assets and editorial rules with your own — the gate's checks in `prepublish_check.py` are the template; the taste encoded in them should be yours.
4. Python 3.9+, deps: `Pillow cairosvg markdown google-auth requests` (plus native cairo).

To use the buyer-led topic workflow in Claude Code, clone this repo and ask:
`Use the ryder-buyer-seo skill to research first-hardware-wallet topics, review product fit and existing coverage, then create draft briefs. Do not publish.`
The project skill is at `.claude/skills/ryder-buyer-seo/SKILL.md`, and
`CLAUDE.md` points Claude to it. From a fresh checkout, run the offline demo
without credentials:

```bash
python3 ryder-shopify-autopilot/topic_selector.py \
  --candidates ryder-shopify-autopilot/examples/topics.synthetic.json \
  --research ryder-shopify-autopilot/examples/research.synthetic.json \
  --as-of 2026-10-07 --pretty
```

The example data is synthetic. Real candidate reviews and keyword results
should stay in local files outside this public repo. For live research, the
existing provider command supports `--json`; it loads any available research
credentials from the local env file and needs no Shopify, Notion, or Slack
credentials. It incurs provider charges if configured. Nothing in this repo
activates a Claude schedule. The publishing skill filters Notion pages with
status `Approved for publishing`, while a direct `push_articles.py` call
trusts its manifest and does not independently recheck that status.

## License

Code is MIT (see LICENSE). The Ryder name, logo, brand assets, and article content are © Ryder / Light Labs — use the machinery, not the brand. Fonts are SIL OFL (see `ryder-shopify-autopilot/assets/fonts/FONT-LICENSES.md`).

Built 2026-08-10 by Louise Ivan (co-founder/CXO, Ryder) pair-working with Claude.
