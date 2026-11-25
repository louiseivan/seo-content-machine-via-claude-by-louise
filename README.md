# Ryder SEO content machine

A buyer-led SEO workflow for [Ryder](https://ryder.id), makers of the Ryder One
hardware wallet. Grok bots discover stories and queue topic seeds in Notion;
Claude researches, drafts and auto-approves; the Shopify autopilot publishes.
The Content Calendar is the system of record, with one page retained from
queued topic through publication.

Repository: [louiseivan/seo-content-machine-via-claude-by-louise](https://github.com/louiseivan/seo-content-machine-via-claude-by-louise).

## New flow from November 24, 2026

All scheduled slots below are **weekdays in Asia/Tokyo**. These are the
operating schedule and responsibilities; schedules and Grok bots are configured
outside this repository. Cloning or updating the repo does not activate them.

| Who | When (Asia/Tokyo) | Responsibility |
| --- | --- | --- |
| Wallet Security Watch (Grok bot) | About 06:00 / 11:30 / 17:30 | Find competitor wallet news, hacks, and phone/OS flaws; send findings to News Hi-jack X Bot. |
| News Hi-jack X Bot (Grok bot) | 06:30 / 12:00 / 18:00 | Scan X trends in crypto, AI, finance, and prediction markets alongside the watcher's findings; send Louise a digest and queue stories with an honest wallet-buyer question in Notion. |
| Ryder Fact-Check (Grok bot) | On request | Verify claims and check ryder.id for existing coverage. Claude still re-verifies sources before drafting. |
| Claude | 06:45 / 12:15 / 18:15 | Run SEO research, decide buyer fit, draft up to four eligible topics per slot, and auto-approve finished drafts. |
| Louise | Any time | Spot-check published articles; approve or fix anything the drafter left at Idea. |
| Shopify autopilot (this repo) | 07:45 / 13:45 / 19:45 daily | Publish approved pages using the existing publishing workflow. |
| Measurement | Weekly check-in on Mondays | Review Google Search Console, Ahrefs, and index watch against the November 24 baseline; final review around December 15, 2026. |

```
Wallet Security Watch ──► News Hi-jack X Bot ◄── X trends
                                   │
                                   ▼
                          Notion: Topic queued
                                   │
                                   ▼
                      Claude: SEO + SERP + buyer-fit review
                                   │
                ┌──────────────────┼───────────────────┐
                ▼                  ▼                   ▼
         Research needed        Archived            Drafting
                                                       │
                                            verify claims + draft + gate
                                                       ▼
                                                      Idea
                                                       │
                                     Claude auto-approves
                                                       ▼
                                            Approved for publishing
                                                       │
                                             Shopify autopilot publishes
                                                       ▼
                                     Published ──► index watch + measurement
```

## Content Calendar

- Database: `20a0b656-6cfd-8067-82de-eddd645ae75e` (`NOTION_DB_ID`).
- Data source: `collection://20a0b656-6cfd-8051-ac3e-000b9cbbd53f`.
- Status flow: `Topic queued` → `Research needed` / `Drafting` → `Idea` →
  `Approved for publishing` → `Published`, or `Archived` for rejected topics.

Grok fills these existing fields:

| Field | Queued content |
| --- | --- |
| `Content name` | Story/topic title |
| `Status` | `Topic queued` |
| `Content type` | Includes `Blog` |
| `keyword` | Seed only, never verified demand |
| `persona`, `buyer_intent`, `buyer_question`, `angle` | Proposed reader, intent, honest wallet-buyer question, and angle |
| `evidence` | JSON array of `{claim, source_url, checked_on}` |
| `existing_coverage_status`, `existing_coverage_url` | Only when coverage has been checked |
| `X source`, `X likes` | Source context; likes are not search demand |
| `Queued by` | `Grok X Bot` |

The page body contains **Claims to check**. Bot-created pages leave `Owner`
empty; automation must never set or clear it. Skip human-owned pages and fail
closed when ownership cannot be verified. Grok never fills search volume,
keyword difficulty, SERP review, or `product_fit`.

## Claude's run at each slot

1. Pull `Topic queued` pages with empty `Owner`. Select **at most four per
   run, oldest first by creation time**; skip anything already `Drafting` or
   `Idea`. Keep the original page IDs. The caller must enforce this selection
   before live intake; see the implementation notes below.
2. Treat each keyword as a seed. Always run `keyword_research.py` for US/en
   volume and difficulty, inspect live Google results, and judge product fit
   honestly. Audience overlap alone does not establish product fit. Record
   today's SERP inspection and actual product-fit review; never invent them.
3. Run `topic_selector.py` and write the decision and reasons to the **same page**:
   - `research_needed` → `Research needed` plus a note.
   - `update_existing` → `Research needed` plus a note to refresh or link
     `existing_coverage_url`; do not draft a duplicate article.
   - `reject` → Status `Archived` plus a note; do not delete the page.
   - `draft_brief` → explicitly claim `Drafting`, then begin writing.
4. Re-verify every claim in `evidence` and **Claims to check** against original
   sources. Drop or soften anything unverified. Never invent numbers, quotes,
   or sources. A Grok fact-check is context, not a substitute for this step.
5. Draft with the [ryder-buyer-seo skill](.claude/skills/ryder-buyer-seo/SKILL.md):
   answer `buyer_question` first, use the trend as the hook, and mention Ryder
   only where it genuinely answers the question.
6. Pass `prepublish_check.py`, then use `push_to_notion_idea.py` to put the
   draft on the **same page** at `Idea`. Preserve `notion_page_id` in the
   sibling `.meta.json`; never create a duplicate page for a queued topic.
7. Log pages processed, the decision for each, and why. Intake returns the
   decision report and writes notes to the original pages; retain run reports
   locally, outside this public repository.

## Approval and publishing rules

- Auto-approval (Louise, 2026-11-24): the scheduled drafter approves its own finished drafts by setting `Approved for publishing` after they pass the editorial gate and its source checks, and stamps the page's internal review notes with "Auto-approved by ryder-article-drafter". The autopilot publishes those pages exactly like human-approved ones; never skip a page because automation approved it.
  The drafter never fills or clears `Owner` and never publishes; a selector
  result alone is not approval.
- The separate [Shopify autopilot](ryder-shopify-autopilot/SKILL.md)
  publishes approved pages. The required handoff is `Published`, `Post URL`,
  and `Publish date` on the original Notion page; see the current date-write
  gap below. Intake must not touch either publishing field.
- Log each new article URL for index watch and the weekly check-in. The
  publisher records live URLs in its results and adds successful new article
  slugs to `index_watch.py`; carry those URLs into the weekly review.
- Never delete Notion or Shopify records, and never commit credentials.

### Current implementation limits

The intake CLI prefers Blog pages but currently has no two-page limit or
oldest-first sort. The scheduled caller must select the oldest four eligible
pages before passing a restricted `--candidates` file to live intake.
Do not run unrestricted live intake for a two-topic slot.

The publishing helper currently writes `Published` and `Post URL`, but does
**not yet write `Publish date`**. That write remains required to complete the
new publishing handoff. The publishing skill filters approval status; a
direct `push_articles.py` call trusts its manifest and does not independently
recheck approval. No schedule is installed by this repository.

## Measurement baseline

Use **2026-11-24** as the comparison baseline for Monday check-ins, with a
final review around **2026-12-15**. These are recorded historical snapshots,
not live metrics.

| Source / snapshot | Metric | Baseline |
| --- | --- | ---: |
| GSC `sc-domain:ryder.id`, 28 days ending 2026-11-21 | Clicks | 1,301 |
| Same GSC window | Impressions | 154,298 |
| Same GSC window | Average position | 6.94 |
| Index watch at baseline | Newest posts indexed | 10 / 10 |
| Ahrefs, 2026-11-23 | Domain Rating (DR) | 43 |
| Ahrefs, 2026-11-23 | Referring domains | 1,229 |
| Ahrefs, 2026-11-23 | Organic keywords | 145 |

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
preview. For a weekday slot, use Notion's creation timestamps to select the
oldest four eligible pages from the preview and save only those topics in
`/tmp/ryder-slot.json`, preserving `schema_version: 1` and `notion_page_id`.
Run live intake against that restricted file to research and write notes:

```bash
python3 ryder-shopify-autopilot/notion_topic_intake.py \
  --candidates /tmp/ryder-slot.json --output /tmp/ryder-slot.json \
  --research-output /tmp/ryder-keywords.json
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
  --candidates /tmp/ryder-slot.json \
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

Intake (the scripts) never sets `Approved for publishing`; the scheduled drafter does that after the gate. Nothing writes `Owner` or touches
`Post URL`/`Publish date`, or deletes records. Fresh ownership/status checks
fail closed, but are not a transactional lock: use one worker per page.
Keep credentials and real queue/research exports outside the public repo;
only synthetic test fixtures are included. The API stays pinned to
`2022-06-28`, querying `NOTION_DB_ID`; the collection ID is separately named
`NOTION_DATA_SOURCE_ID`, not an invalid database ID.

## License

Code is MIT (see LICENSE). The Ryder name, logo, brand assets, and article content are © Ryder / Light Labs — use the machinery, not the brand. Fonts are SIL OFL (see `ryder-shopify-autopilot/assets/fonts/FONT-LICENSES.md`).

Built 2026-08-10 by Louise Ivan (co-founder/CXO, Ryder) pair-working with Claude.
