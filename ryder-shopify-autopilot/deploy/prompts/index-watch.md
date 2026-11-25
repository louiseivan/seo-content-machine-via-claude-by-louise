Check Google index coverage for Ryder blog posts that are not yet indexed.

1. cd {{ROOT}}/ryder-shopify-autopilot
2. Run: python3 -W ignore index_watch.py add
   Merges any slugs from the current push manifest into the durable watch
   list. Safe to run every time; existing entries are never overwritten.
3. Run: python3 -W ignore index_watch.py check
   Inspects every pending slug, prints one line per URL (slug, coverage
   state, last crawl time), flags state changes, marks newly-indexed slugs
   as resolved, and re-submits the sitemap if anything is still pending.
   Exit code 0 = everything indexed, 2 = some still pending.
4. Report the output as-is, calling out any state change (e.g. "URL is
   unknown to Google" -> "Discovered" / "Crawled - currently not indexed"
   / "Submitted and indexed").
5. When step 3 exits 0, report "everything indexed" and stop. Do NOT disable
   anything: on the cloud server this job runs from cron every night at
   00:00 Tokyo, and new articles are published every day, so the watch list
   refills on its own.

Do NOT read articles-to-push.json directly for the slug list. That manifest
is rewritten for every new batch, so slugs disappear from it within hours
while indexing takes days. The watch list at outputs/index-watch.json is the
source of truth; slugs leave it only once Google reports them indexed.

If a slug sits at "URL is unknown to Google" for more than ~5 days, note in
the report that it likely needs a manual "Request Indexing" in Search Console
(the Google API cannot trigger that for blog URLs) and that
`linkback_sweep.py --manifest <watch file> --dry-run` will show what internal
links could be added to help discovery. Do not run the sweep with --apply.

Never echo credentials. This task only reads index status and re-submits the
sitemap; it must not modify articles, Notion, or Slack.
