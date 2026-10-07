"""Shared config and API helpers for the Ryder content machine.

Local rebuild (2026-08-10) of the pipeline described in
CLAUDE OUTPUTS/Ryder One/CONTENT-MACHINE-SETUP.md. Paths are localized
for this machine; override via env vars where noted.
"""

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------- paths

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RYDER_DIR = os.path.join(BASE_DIR, "CLAUDE OUTPUTS", "Ryder One")
AUTOPILOT_DIR = os.path.join(BASE_DIR, "ryder-shopify-autopilot")
ENV_FILE = os.path.join(RYDER_DIR, "shopify.env")
REWRITES_DIR = os.path.join(RYDER_DIR, "rewrites")
OUTPUTS_DIR = os.path.join(RYDER_DIR, "outputs")

# Staging paths kept identical to the setup guide's runbook.
STAGING_DIR = os.environ.get("PUSH_STAGING_DIR", "/tmp/visual-test")
BODIES_DIR = os.path.join(STAGING_DIR, "push-bodies")
HEROES_DIR = os.path.join(STAGING_DIR, "heroes")
RESULTS_FILE = os.path.join(STAGING_DIR, "push-results.json")
TOKEN_CACHE = os.path.join(STAGING_DIR, ".shopify_token.json")

DEFAULT_MANIFEST = os.path.join(OUTPUTS_DIR, "articles-to-push.json")

# ---------------------------------------------------------------- constants

SHOPIFY_BLOG_ID = "111885680943"
SHOPIFY_API_VERSION = "2024-10"
ARTICLE_URL_PATTERN = "https://ryder.id/blogs/post/{handle}"
ARTICLE_TAG = "Industry Insights"  # exactly this, one tag, never variations

# Content Calendar. The setup guide's old ID (...8051-ac3e-000b9cbbd53f)
# was a bad copy and 404s; verified against the live workspace 2026-08-10.
NOTION_DB_ID = "20a0b656-6cfd-8067-82de-eddd645ae75e"
NOTION_STATUS_APPROVED = "Approved for publishing"  # not plain "Approved"
NOTION_STATUS_PUBLISHED = "Published"
NOTION_VERSION = "2022-06-28"

SLACK_CHANNEL_ID = "C0B2ARN0Y01"  # #ws-blogs-published


PUBLISH_KEYS = ("SHOPIFY_SHOP", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET",
                "NOTION_API_KEY", "SLACK_BOT_TOKEN")


def load_env(path=ENV_FILE, required_keys=PUBLISH_KEYS):
    """Parse shopify.env into os.environ. Values never get printed."""
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
    missing = [k for k in required_keys
               if not os.environ.get(k) or os.environ[k] == "REPLACE_ME"]
    if missing:
        raise SystemExit(f"credentials missing for: {', '.join(missing)}")


# ---------------------------------------------------------------- http

def http(method, url, headers=None, payload=None, timeout=30):
    """JSON request helper. Returns (status_code, parsed_body_or_text)."""
    data = None
    headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        status = e.code
    try:
        return status, json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return status, body


# ---------------------------------------------------------------- shopify

def shopify_token():
    """Client-credentials token for the custom app, cached until expiry."""
    if os.environ.get("SHOPIFY_ACCESS_TOKEN"):
        return os.environ["SHOPIFY_ACCESS_TOKEN"]
    try:
        with open(TOKEN_CACHE) as f:
            cached = json.load(f)
        if cached.get("expires_at", 0) > time.time() + 60:
            return cached["access_token"]
    except (OSError, ValueError, KeyError):
        pass
    shop = os.environ["SHOPIFY_SHOP"]
    status, body = http(
        "POST", f"https://{shop}/admin/oauth/access_token",
        payload={
            "client_id": os.environ["SHOPIFY_CLIENT_ID"],
            "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"],
            "grant_type": "client_credentials",
        })
    if status != 200 or "access_token" not in body:
        raise SystemExit(f"shopify token exchange failed (HTTP {status})")
    os.makedirs(STAGING_DIR, exist_ok=True)
    cached = {"access_token": body["access_token"],
              "expires_at": time.time() + int(body.get("expires_in", 86000))}
    with open(TOKEN_CACHE, "w") as f:
        json.dump(cached, f)
    os.chmod(TOKEN_CACHE, 0o600)
    return cached["access_token"]


def shopify(method, path, payload=None):
    """Shopify Admin REST call. DELETE is structurally impossible (rule 4)."""
    if method not in ("GET", "POST", "PUT"):
        raise ValueError(f"method {method} not allowed against Shopify")
    shop = os.environ["SHOPIFY_SHOP"]
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/{path.lstrip('/')}"
    return http(method, url,
                headers={"X-Shopify-Access-Token": shopify_token()},
                payload=payload)


# ---------------------------------------------------------------- notion

def notion(method, path, payload=None):
    return http(method, f"https://api.notion.com/v1/{path.lstrip('/')}",
                headers={
                    "Authorization": f"Bearer {os.environ['NOTION_API_KEY']}",
                    "Notion-Version": NOTION_VERSION,
                }, payload=payload)


def notion_mark_published(page_id, live_url):
    status, body = notion("PATCH", f"pages/{page_id}", {
        "properties": {
            "Status": {"status": {"name": "Published"}},
            "Post URL": {"url": live_url},
        }})
    return status == 200, body if status != 200 else None


# ---------------------------------------------------------------- slack

def slack_announce(title, summary, live_url):
    text = f"📝 New post live: *{title}*\n{summary}\n🔗 {live_url}"
    payload = {"channel": SLACK_CHANNEL_ID, "text": text,
               # Post under Louise's name (needs chat:write.customize;
               # falls back to the bot identity below if the scope is absent).
               "username": os.environ.get("SLACK_POST_AS", "Louise Ivan"),
               "icon_emoji": os.environ.get("SLACK_POST_ICON", ":ryder:")}
    headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
    status, body = http("POST", "https://slack.com/api/chat.postMessage",
                        headers=headers, payload=payload)
    if isinstance(body, dict) and body.get("error") == "missing_scope":
        payload.pop("username"), payload.pop("icon_emoji")
        status, body = http("POST", "https://slack.com/api/chat.postMessage",
                            headers=headers, payload=payload)
    ok = status == 200 and isinstance(body, dict) and body.get("ok")
    return ok, None if ok else body.get("error", f"HTTP {status}")


# ---------------------------------------------------------------- markdown

def md_to_html(text):
    """Markdown to HTML. Uses python-markdown when available, else a
    minimal converter good enough for our blog bodies."""
    try:
        import markdown
        return markdown.markdown(text, extensions=["extra"])
    except ImportError:
        pass

    def inline(s):
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        return s

    html, in_list = [], False
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().split("\n")
        m = re.match(r"^(#{1,6})\s+(.*)$", lines[0])
        if m and len(lines) == 1:
            level = len(m.group(1))
            html.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
        elif all(re.match(r"^[-*]\s+", ln) for ln in lines):
            stripped_items = [inline(re.sub(r"^[-*]\s+", "", ln)) for ln in lines]
            html.append("<ul>" + "".join(f"<li>{it}</li>" for it in stripped_items) + "</ul>")
        elif all(re.match(r"^\d+\.\s+", ln) for ln in lines):
            stripped_items = [inline(re.sub(r"^\d+\.\s+", "", ln)) for ln in lines]
            html.append("<ol>" + "".join(f"<li>{it}</li>" for it in stripped_items) + "</ol>")
        elif all(ln.startswith(">") for ln in lines):
            inner = " ".join(ln.lstrip("> ") for ln in lines)
            html.append(f"<blockquote><p>{inline(inner)}</p></blockquote>")
        else:
            html.append(f"<p>{inline(' '.join(lines))}</p>")
    return "\n".join(html)


def b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
