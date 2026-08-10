"""Create Notion "Idea" pages in the Content Calendar for staged drafts.

One page per article per API call (setup guide rule 7: batch payloads
fail). Page body is the converted article, followed by an SEO metadata
callout (publishing rule: meta description at the bottom of the draft).

Usage:
    python3 push_to_notion_idea.py rewrites/new-66-*.md [more .md files]
Each <name>.md must have a sibling <name>.meta.json.
"""

import glob
import json
import os
import re
import sys

from common import NOTION_DB_ID, load_env, notion


def rich_text(text):
    """Inline markdown ([links](url), **bold**) -> Notion rich text."""
    out = []
    pattern = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*")
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append({"type": "text", "text": {"content": text[pos:m.start()]}})
        if m.group(1):
            out.append({"type": "text",
                        "text": {"content": m.group(1), "link": {"url": m.group(2)}}})
        else:
            out.append({"type": "text", "text": {"content": m.group(3)},
                        "annotations": {"bold": True}})
        pos = m.end()
    if pos < len(text):
        out.append({"type": "text", "text": {"content": text[pos:]}})
    return out or [{"type": "text", "text": {"content": ""}}]


def table_block(lines):
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue  # separator row
        rows.append({"type": "table_row",
                     "table_row": {"cells": [rich_text(c) for c in cells]}})
    width = max(len(r["table_row"]["cells"]) for r in rows)
    for r in rows:  # pad ragged rows
        r["table_row"]["cells"] += [[{"type": "text", "text": {"content": ""}}]
                                    ] * (width - len(r["table_row"]["cells"]))
    return {"type": "table",
            "table": {"table_width": width, "has_column_header": True,
                      "has_row_header": False, "children": rows}}


def md_to_blocks(md):
    blocks = []
    for chunk in re.split(r"\n\s*\n", md.strip()):
        lines = chunk.strip().split("\n")
        first = lines[0]
        if first.startswith("# ") and len(lines) == 1:
            continue  # H1 = page title, skip
        if first.startswith("|"):
            blocks.append(table_block(lines))
        elif first.startswith("### "):
            blocks.append({"type": "heading_3",
                           "heading_3": {"rich_text": rich_text(first[4:])}})
            lines = lines[1:]
            if lines:
                blocks.append({"type": "paragraph",
                               "paragraph": {"rich_text": rich_text(" ".join(lines))}})
        elif first.startswith("## "):
            blocks.append({"type": "heading_2",
                           "heading_2": {"rich_text": rich_text(first[3:])}})
        elif all(re.match(r"^\d+\.\s+", ln) for ln in lines):
            for ln in lines:
                blocks.append({"type": "numbered_list_item",
                               "numbered_list_item": {
                                   "rich_text": rich_text(re.sub(r"^\d+\.\s+", "", ln))}})
        elif all(re.match(r"^[-*]\s+", ln) for ln in lines):
            for ln in lines:
                blocks.append({"type": "bulleted_list_item",
                               "bulleted_list_item": {
                                   "rich_text": rich_text(re.sub(r"^[-*]\s+", "", ln))}})
        else:
            blocks.append({"type": "paragraph",
                           "paragraph": {"rich_text": rich_text(" ".join(lines))}})
    return blocks


def push_idea(md_path):
    meta_path = md_path.rsplit(".md", 1)[0] + ".meta.json"
    with open(md_path) as f:
        body = f.read()
    with open(meta_path) as f:
        meta = json.load(f)

    blocks = md_to_blocks(body)
    seo_text = (f"SEO metadata\nTarget keyword: {meta['target_keyword']}\n"
                f"SEO title: {meta['seo_title']}\n"
                f"Meta description: {meta['meta_description']}\n"
                f"Slug: {meta['slug']}\nHero alt: {meta['hero_alt']}")
    blocks.append({"type": "callout",
                   "callout": {"rich_text": [{"type": "text", "text": {"content": seo_text}}],
                               "icon": {"type": "emoji", "emoji": "🔎"}}})

    status, resp = notion("POST", "pages", {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Content name": {"title": [{"type": "text", "text": {"content": meta["title"]}}]},
            "Status": {"status": {"name": "Idea"}},
        },
        "children": blocks,
    })
    if status == 200:
        return True, resp["id"], resp.get("url", "")
    return False, None, str(resp)[:300]


def main():
    load_env()
    paths = []
    for arg in sys.argv[1:]:
        paths.extend(sorted(glob.glob(arg)))
    paths = [p for p in paths if p.endswith(".md")]
    if not paths:
        raise SystemExit("usage: python3 push_to_notion_idea.py draft.md [...]")
    for p in paths:
        ok, page_id, info = push_idea(p)
        print(("OK  " if ok else "ERR ") + os.path.basename(p),
              "->", page_id or info)


if __name__ == "__main__":
    main()
