"""Google Search Console for the Ryder content machine.

Closes the measurement loop (which queries ryder.id ranks for, which
articles get impressions/clicks) and the indexing loop (sitemap
submission + per-URL index status). Honest scope note: Google's public
API cannot trigger "Request indexing" for a blog URL (that API is
restricted to job-posting/livestream pages); what we CAN do is submit
the sitemap and inspect a URL's index state, which is the legitimate
automatable equivalent.

Setup (one-time, needs Louise):
1. console.cloud.google.com -> new project (or existing) -> enable
   "Google Search Console API".
2. Create a service account, download its JSON key, save it as
   CLAUDE OUTPUTS/Ryder One/gsc-service-account.json (chmod 600).
3. In Search Console (search.google.com/search-console) -> Settings ->
   Users and permissions -> add the service account's email as a Full
   user on the ryder.id property.
4. Set GSC_PROPERTY in shopify.env if the property is URL-prefix style
   (default assumes domain property sc-domain:ryder.id).

Usage:
    python3 gsc.py perf 28                # top queries, last 28 days
    python3 gsc.py pages 28               # top pages, last 28 days
    python3 gsc.py inspect <url>          # index status of one URL
    python3 gsc.py sitemap                # submit /sitemap.xml
"""

import datetime
import json
import os
import sys

from common import RYDER_DIR, http, load_env

KEY_FILE = os.path.join(RYDER_DIR, "gsc-service-account.json")
SCOPES = ["https://www.googleapis.com/auth/webmasters"]


def _property():
    return os.environ.get("GSC_PROPERTY", "sc-domain:ryder.id")


def _token():
    if not os.path.exists(KEY_FILE):
        raise SystemExit(
            f"service account key missing: {KEY_FILE}\n"
            "Follow the setup steps in this file's docstring.")
    from google.oauth2 import service_account
    import google.auth.transport.requests
    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE, scopes=SCOPES)
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _api(method, url, payload=None):
    status, body = http(method, url,
                        headers={"Authorization": f"Bearer {_token()}"},
                        payload=payload)
    if status not in (200, 204):
        raise SystemExit(f"gsc HTTP {status}: {str(body)[:300]}")
    return body


def perf(days=28, dimension="query", limit=25):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    site = urllib_quote(_property())
    body = _api("POST",
                f"https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query",
                {"startDate": start.isoformat(), "endDate": end.isoformat(),
                 "dimensions": [dimension], "rowLimit": limit})
    return body.get("rows", [])


def inspect(url):
    return _api("POST",
                "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                {"inspectionUrl": url, "siteUrl": _property()})


def submit_sitemap(sitemap_url="https://ryder.id/sitemap.xml"):
    site = urllib_quote(_property())
    feed = urllib_quote(sitemap_url)
    return _api("PUT",
                f"https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}")


def urllib_quote(s):
    import urllib.parse
    return urllib.parse.quote(s, safe="")


def main():
    load_env()
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd in ("perf", "pages"):
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 28
        dim = "query" if cmd == "perf" else "page"
        for r in perf(days, dim):
            print(f"{r['clicks']:>6.0f} clicks {r['impressions']:>8.0f} impr "
                  f"pos {r['position']:>5.1f}  {r['keys'][0]}")
    elif cmd == "inspect":
        result = inspect(sys.argv[2])["inspectionResult"]["indexStatusResult"]
        print(result.get("coverageState"), "| last crawl:",
              result.get("lastCrawlTime", "never"))
    elif cmd == "sitemap":
        submit_sitemap()
        print("sitemap submitted")
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
