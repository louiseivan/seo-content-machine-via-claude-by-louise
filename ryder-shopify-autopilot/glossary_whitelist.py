"""Print the live glossary whitelist as a markdown table.

Fetches published articles from the glossary blog and prints the table
for RYDER_CONTENT_SYSTEM_PROMPT.md's "Confirmed glossary slugs" section.
Known duplicate handles are excluded.

Usage: python3 glossary_whitelist.py
"""

from common import load_env, shopify

GLOSSARY_BLOG_ID = "120709939503"
EXCLUDE = {"what-is-a-hardware-wallet", "what-is-an-nfc-tag-1"}  # dups


def main():
    load_env()
    status, body = shopify(
        "GET", f"blogs/{GLOSSARY_BLOG_ID}/articles.json"
               "?limit=250&fields=handle,title,published_at")
    if status != 200:
        raise SystemExit(f"shopify HTTP {status}")
    print("| Term | URL |\n|---|---|")
    for a in sorted(body["articles"], key=lambda x: x["title"]):
        if a["handle"] in EXCLUDE or not a["published_at"]:
            continue
        term = a["title"].replace("What Is ", "").replace("What is ", "").rstrip("?")
        print(f"| {term} | https://ryder.id/blogs/glossary/{a['handle']} |")


if __name__ == "__main__":
    main()
