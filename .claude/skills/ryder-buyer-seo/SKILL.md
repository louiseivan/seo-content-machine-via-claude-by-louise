---
name: ryder-buyer-seo
description: Select Ryder SEO topics from keyword research for exchange holders choosing their first hardware wallet. Use before drafting content calendars, article briefs, or SEO articles; review buyer fit, SERP intent, evidence, and existing coverage.
---

# Buyer-led Ryder SEO

The primary reader already holds crypto on an exchange and is considering a
first hardware wallet. Switching wallet owners are exploratory. Gift and
referral topics are secondary. Advanced PSBT and power-user topics are
deprioritized. Search volume is a signal only after buyer fit and evidence.
These priorities are a public strategy summary, not a private ICP document.

Unvalidated seed ideas to research: exchange-to-wallet transfer and first
wallet setup; beginner purchase comparisons and recovery choices; switching
from another hardware wallet. These are prompts for investigation, not
measured demand or confirmed opportunities. General exchange news or trading
topics require an actual wallet purchase connection; audience overlap alone
does not establish product fit.

## Topic selection before drafting

1. Start with keyword candidates from the existing research command. With
   research-provider credentials configured, run from the repository root:
   `python3 ryder-shopify-autopilot/keyword_research.py matching "hardware wallet" 50 --json > /tmp/ryder-keywords.json`.
   This invokes paid providers only when their credentials are available.
   For an offline demonstration use the bundled synthetic files below.
2. Create a candidate JSON using
   `ryder-shopify-autopilot/examples/topics.synthetic.json` as the shape.
   Do not copy its synthetic metrics, SERP notes, or example evidence into
   real work. For each candidate, record a buyer question and angle, one of
   `exchange_holder`, `switching_owner`, `gift_referral`, `power_user`,
   and one of `decision`, `comparison`, `how_to_buy`, `informational`,
   `other`. The JSON has `schema_version: 1` and a `topics` array. Each
   topic requires `keyword`, `persona`, and `buyer_intent`; the selectors
   use `product_fit`, `serp`, `existing_coverage`, and `evidence` as
   review objects. A human must verify product fit with reviewer, date, and
   rationale. Record a dated US SERP inspection with its URL and intent
   notes, a dated existing-content inventory source, and dated sources for
   claims with HTTP(S) source URLs. Use null for unknown provider metrics;
   zero means a measured zero. The selector validates shape and date, while
   the human must assess source quality and factual accuracy.
3. Run `python3 ryder-shopify-autopilot/topic_selector.py --candidates
   /path/to/candidates.json --research /tmp/ryder-keywords.json --pretty`.
   Store outputs locally; inspect `research_needed` reasons and fill gaps.
   The research JSON records country, collection date, providers, and notes.
   Stale/future research or review older than 120 days is held for research.
4. Draft only `draft_brief` items after confirming sources and product fit.
   `update_existing` calls for a refresh or internal link plan for the
   existing URL; do not create a duplicate. `reject` stays out of the
   calendar. The 0-100 score is a deterministic priority heuristic, not a
   traffic, ranking, or conversion forecast. Read the brief's buyer question,
   angle, evidence, and SERP notes; do not treat sample citations as facts.
5. Write the article and run `prepublish_check.py`. Human editorial review
   and the Notion `Approved for publishing` status are separate from topic
   selection. Never set status to approved on the basis of a selector result.

Offline demo, no credentials or network:

```bash
python3 ryder-shopify-autopilot/topic_selector.py \
  --candidates ryder-shopify-autopilot/examples/topics.synthetic.json \
  --research ryder-shopify-autopilot/examples/research.synthetic.json \
  --as-of 2026-10-07 --pretty
```

This repo contains the skill and command but does not install an external
Claude schedule or run research automatically. If using a scheduled Claude
task, make topic research and this selection sequence its first steps. Keep
all private ICP source material, credentials, internal metrics, and screenshots
outside this public repository.
