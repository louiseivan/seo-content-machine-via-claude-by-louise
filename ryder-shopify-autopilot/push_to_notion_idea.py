"""Create or update Notion "Idea" pages in the Content Calendar for staged drafts.

One page per article per API call (setup guide rule 7: batch payloads
fail). Page body is the converted article, followed by an SEO metadata
callout (publishing rule: meta description at the bottom of the draft).

Usage:
    python3 push_to_notion_idea.py rewrites/new-66-*.md [more .md files]
Each <name>.md must have a sibling <name>.meta.json.
Use --page-id ID for one draft, or notion_page_id in its metadata, to append
the draft to the existing page. Existing intake notes are preserved.
"""

import argparse
import glob
import json
import os
import re
from uuid import UUID

from common import (NOTION_DB_ID, NOTION_STATUS_DRAFTING, NOTION_STATUS_IDEA,
                    load_env, notion, notion_writable_page)
from prepublish_check import check_article


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


def push_idea(md_path, page_id=None):
    md_path = os.fspath(md_path)
    meta_path = md_path.rsplit(".md", 1)[0] + ".meta.json"
    with open(md_path) as f:
        body = f.read()
    with open(meta_path) as f:
        meta = json.load(f)

    metadata_id = meta.get("notion_page_id")
    if page_id is not None and metadata_id is not None and UUID(page_id) != UUID(metadata_id):
        raise ValueError("page_id conflicts with sibling metadata")
    # An invalid known ID must never fall back to creating another page.
    known_id = page_id if page_id is not None else metadata_id
    page_id = str(UUID(known_id)) if known_id is not None else None

    blocks = md_to_blocks(body)
    seo_text = (f"SEO metadata\nTarget keyword: {meta['target_keyword']}\n"
                f"SEO title: {meta['seo_title']}\n"
                f"Meta description: {meta['meta_description']}\n"
                f"Slug: {meta['slug']}\nHero alt: {meta['hero_alt']}")
    gate = check_article(body + "\n\n# " + meta["title"] + "\n\n" + seo_text)
    if not gate["passed"]:
        return False, None, "editorial gate failed; run prepublish_check.py and check metadata"
    blocks.append({"type": "callout",
                   "callout": {"rich_text": [{"type": "text", "text": {"content": seo_text}}],
                               "icon": {"type": "emoji", "emoji": "🔎"}}})

    properties = {
        "Content name": {"title": [{"type": "text", "text": {"content": meta["title"]}}]},
        "Status": {"status": {"name": NOTION_STATUS_IDEA}},
    }
    if page_id:
        # Append a revision without deleting source notes or earlier human edits.
        allowed = {NOTION_STATUS_DRAFTING, NOTION_STATUS_IDEA}
        for start in range(0, len(blocks), 100):
            notion_writable_page(page_id, allowed)
            status, _ = notion("PATCH", f"blocks/{page_id}/children", {
                "children": blocks[start:start + 100]})
            if status != 200:
                return False, page_id, f"draft append failed (HTTP {status}); status unchanged"
        notion_writable_page(page_id, allowed)
        status, resp = notion("PATCH", f"pages/{page_id}", {"properties": properties})
    else:
        # shortcut: one create request, split drafts exceeding 100 blocks before uploading.
        if len(blocks) > 100:
            return False, None, "local draft exceeds Notion's 100-block create limit"
        status, resp = notion("POST", "pages", {
            "parent": {"database_id": NOTION_DB_ID},
            "properties": properties,
            "children": blocks,
        })
    if status == 200:
        return True, resp["id"], resp.get("url", "")
    return False, page_id, f"Notion Idea write failed (HTTP {status})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drafts", nargs="+")
    parser.add_argument("--page-id", help="Update this existing page (one draft only)")
    args = parser.parse_args()
    paths = []
    for arg in args.drafts:
        paths.extend(sorted(glob.glob(arg)))
    paths = [p for p in paths if p.endswith(".md")]
    if not paths:
        raise SystemExit("usage: python3 push_to_notion_idea.py draft.md [...]")
    if args.page_id and len(paths) != 1:
        parser.error("--page-id requires exactly one draft")
    load_env(required_keys=("NOTION_API_KEY",))
    failed = False
    for p in paths:
        try:
            ok, page_id, info = push_idea(p, args.page_id)
        except (ValueError, KeyError, TypeError, OSError):
            ok, page_id, info = False, None, "check draft/metadata and page ownership/status"
        failed = failed or not ok
        print(("OK  " if ok else "ERR ") + os.path.basename(p),
              "->", page_id if ok else info)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
