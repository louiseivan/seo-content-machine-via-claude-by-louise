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
- **`notion_topic_intake.py`** — pulls `Topic queued` pages from the Content Calendar, prefers `Blog`, skips human-owned pages, and runs fresh keyword overview research for every seed and the existing selector. A current-day Claude/human SERP inspection is required before drafting. Decisions and drafts stay on the original Notion page; intake never grants publishing approval.
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

## Notion queue to draft

With `NOTION_API_KEY` configured locally, preview the queue without Notion
writes or paid research:

```bash
python3 ryder-shopify-autopilot/notion_topic_intake.py \
  --dry-run --output /tmp/ryder-topics.json
```

Grok X Bot only supplies topic seeds and source context. It never fills search
volume, keyword difficulty, SERP review, or `product_fit`; its keyword is an
unverified seed. Research stays in this repo, and every live intake/review/claim
runs `keyword_research.py overview --json` even when cached metrics exist.

The preview includes candidates, planned keyword-research calls (US/en),
required Claude/human SERP checks, status writes, and skipped human-owned
pages. Add
`--research-in-dry-run` only to explicitly allow provider calls during a
preview. Run without `--dry-run` to perform research and write selector notes:

```bash
python3 ryder-shopify-autopilot/notion_topic_intake.py \
  --output /tmp/ryder-topics.json --research-output /tmp/ryder-keywords.json
```

`--research PATH` can supply research to a dry-run preview; live runs always
replace it with fresh provider output. Unknown volume stays null, even when
older metrics were available. Inspect live US/English SERPs for each seed and
record the query/result URL, intent notes, and today's `serp.reviewed_on` in
the exported candidates. This is a Claude/human inspection, not a SERP API
implemented here; keyword overview does not perform it. Missing product-fit
or current-day SERP reviews block drafting. Complete real reviews using
the [buyer skill](.claude/skills/ryder-buyer-seo/SKILL.md), preserving
`notion_page_id`. To claim one reviewed `draft_brief` when writing begins:

```bash
python3 ryder-shopify-autopilot/notion_topic_intake.py \
  --candidates /tmp/ryder-topics.json \
  --claim PAGE_ID
```

This recomputes the decision before setting `Drafting`. `update_existing`
means refresh/link the existing URL and stays `Research needed`; `reject`
gets Status `Archived` and a note, without deleting the record.

After writing and checking the draft, update the original page:

```bash
python3 ryder-shopify-autopilot/prepublish_check.py /path/to/draft.md
python3 ryder-shopify-autopilot/push_to_notion_idea.py \
  /path/to/draft.md --page-id PAGE_ID
```

A sibling `draft.meta.json` is still required. Its `notion_page_id` can also
select the existing page; conflicting IDs are rejected. The uploader enforces
the editorial gate on the body and metadata, appends the draft/SEO callout,
and sets `Idea` on that same unowned page. It preserves intake notes; reruns
append revisions, so inspect partial failed uploads before retrying. Without
a known ID, local drafts retain the create path. Keep that ID in the existing
Shopify publishing manifest.

Intake/drafting never sets `Approved for publishing`, writes `Owner`, touches
`Post URL`/`Publish date`, or deletes records. Fresh ownership/status checks
fail closed, but are not a transactional lock: use one worker per page.
Keep credentials and real queue/research exports outside the public repo;
only synthetic test fixtures are included. The API stays pinned to
`2022-06-28`, querying `NOTION_DB_ID`; the collection ID is separately named
`NOTION_DATA_SOURCE_ID`, not an invalid database ID.

## License

Code is MIT (see LICENSE). The Ryder name, logo, brand assets, and article content are © Ryder / Light Labs — use the machinery, not the brand. Fonts are SIL OFL (see `ryder-shopify-autopilot/assets/fonts/FONT-LICENSES.md`).

Built 2026-08-10 by Louise Ivan (co-founder/CXO, Ryder) pair-working with Claude.
