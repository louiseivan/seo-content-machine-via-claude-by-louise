"""Pull queued Notion topics through the existing buyer selector, without publishing.

Dry runs read Notion but never write it or call paid research unless explicitly
requested. Every live run researches the queued keyword seeds in this repo;
Grok supplies neither demand metrics nor product-fit/SERP verification.
Exported candidates retain notion_page_id for review and drafting.
"""

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import UUID

from common import (NOTION_DB_ID, NOTION_STATUS_ARCHIVED, NOTION_STATUS_DRAFTING,
                    NOTION_STATUS_QUEUED, NOTION_STATUS_RESEARCH, load_env,
                    notion, notion_page_owners, notion_writable_page)
from topic_selector import INTENTS, PERSONAS, select

INTAKE_STATUSES = {NOTION_STATUS_QUEUED, NOTION_STATUS_RESEARCH}
DECISION_STATUSES = {"research_needed": NOTION_STATUS_RESEARCH,
                     "update_existing": NOTION_STATUS_RESEARCH,
                     "reject": NOTION_STATUS_ARCHIVED}


def property_text(prop):
    return "".join(item.get("plain_text", item.get("text", {}).get("content", ""))
                   for item in prop.get(prop.get("type", "rich_text"), [])).strip()


def parse_evidence(text):
    """Recover JSON surrounded by prose/fences or Notion's Markdown autolinks."""
    cleaned = text.replace(r"\_", "_")
    cleaned = re.sub(r"\[([^\[\]\r\n]+)\]\((https?://[^\s]+?)\)", r"\2", cleaned)
    decoder = json.JSONDecoder()
    for candidate in (cleaned, text):
        for match in re.finditer(r"\[", candidate):
            try:
                value, _ = decoder.raw_decode(candidate[match.start():])
            except ValueError:
                continue
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value
    raise ValueError("evidence must contain a JSON array of claim objects")


def map_page(page):
    props = page["properties"]
    topic = {"notion_page_id": str(UUID(page["id"])),
             "content_name": property_text(props.get("Content name", {}))}
    for name in ("keyword", "buyer_question", "angle"):
        topic[name] = property_text(props.get(name, {}))
    for name in ("persona", "buyer_intent"):
        topic[name] = (props.get(name, {}).get("select") or {}).get("name")
    if not topic["keyword"] or topic["persona"] not in PERSONAS or topic["buyer_intent"] not in INTENTS:
        raise ValueError("keyword, persona, and buyer_intent need valid values")
    topic["existing_coverage"] = {
        "status": (props.get("existing_coverage_status", {}).get("select") or {}).get("name"),
        "url": props.get("existing_coverage_url", {}).get("url"),
        "source": page.get("url"),
    }
    # A queue timestamp is not a coverage review date. Reviewers add checked_on.
    evidence = property_text(props.get("evidence", {}))
    topic["evidence"] = parse_evidence(evidence) if evidence else []
    return topic


def queued_pages():
    pages, cursor = [], None
    while True:
        payload = {"filter": {"property": "Status", "status": {"equals": NOTION_STATUS_QUEUED}},
                   "page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        status, body = notion("POST", f"databases/{NOTION_DB_ID}/query", payload)
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise ValueError(f"Notion queue query failed (HTTP {status})")
        pages.extend(body["results"])
        if not body.get("has_more"):
            break
        next_cursor = body.get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            raise ValueError("Notion queue pagination cursor missing or repeated")
        cursor = next_cursor
    return sorted(pages, key=lambda p: not any(
        item.get("name") == "Blog" for item in
        p.get("properties", {}).get("Content type", {}).get("multi_select", [])))


def research_command(topics):
    return [sys.executable, str(Path(__file__).with_name("keyword_research.py")),
            "overview", ",".join(t["keyword"] for t in topics), "--json"]


def decision_note(result):
    lines = ["Buyer selector: " + result["decision"], result["score_kind"]]
    lines.extend(result["reasons"])
    if result.get("existing_url"):
        lines.append("Refresh or link this existing article; do not draft a duplicate: " + result["existing_url"])
    if result["decision"] == "draft_brief":
        lines.append("Drafting requires an explicit Claude claim. This is not publishing approval.")
    return "\n".join(lines)[:1900]


def write_decision(page_id, result, status_name):
    expected = ({None, NOTION_STATUS_DRAFTING} if result["decision"] == "draft_brief"
                else {DECISION_STATUSES[result["decision"]]})
    if status_name not in expected:
        raise ValueError("unsupported intake status")
    notion_writable_page(page_id, INTAKE_STATUSES)
    status, _ = notion("PATCH", f"blocks/{page_id}/children", {"children": [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
            {"type": "text", "text": {"content": decision_note(result)}}]}}]})
    if status != 200:
        raise ValueError(f"selector note failed (HTTP {status}); status unchanged")
    if status_name:
        notion_writable_page(page_id, INTAKE_STATUSES)
        status, _ = notion("PATCH", f"pages/{page_id}", {
            "properties": {"Status": {"status": {"name": status_name}}}})
        if status != 200:
            raise ValueError(f"selector status update failed (HTTP {status})")


def run_intake(*, dry_run=False, research_in_dry_run=False, candidates=None,
               research=None, claim=None, today=None):
    today = today or dt.date.today()
    claim = str(UUID(claim)) if claim else None
    reviewed = {}
    if candidates is not None:
        if candidates.get("schema_version") != 1 or not isinstance(candidates.get("topics"), list):
            raise ValueError("candidates require schema_version 1 and topics array")
        for topic in candidates["topics"]:
            page_id = str(UUID(topic["notion_page_id"]))
            if page_id in reviewed:
                raise ValueError("duplicate candidate notion_page_id")
            reviewed[page_id] = topic
        if claim and claim not in reviewed:
            raise ValueError("claim must identify a reviewed candidate")
        pages = [{"id": p} for p in reviewed if not claim or p == claim]
    else:
        if claim:
            raise ValueError("--claim requires --candidates with completed reviews")
        pages = queued_pages()
    if not dry_run and ((candidates or {}).get("synthetic_example") or (research or {}).get("synthetic_example")):
        raise ValueError("synthetic examples cannot change live Notion pages")

    topics, skipped, invalid, seen = [], [], [], set()
    for queued in pages:
        page_id = str(UUID(queued["id"]))
        # Respect an owner in the query response too, even before a fresh lookup.
        if not reviewed:
            ok, owners = notion_page_owners(page_id, page=queued)
            if not ok or owners:
                skipped.append({"page_id": page_id, "reason": "human-owned" if owners and ok else "owner lookup failed"})
                continue
        try:
            page = notion_writable_page(page_id, INTAKE_STATUSES if reviewed else {NOTION_STATUS_QUEUED})
        except (ValueError, OSError) as exc:
            skipped.append({"page_id": page_id, "reason": str(exc) if isinstance(exc, ValueError) else "page lookup failed"})
            continue
        try:
            topic = map_page(page)
            if page_id in reviewed:
                previous = reviewed[page_id]
                if any(previous.get(k) != topic[k] for k in ("keyword", "persona", "buyer_intent")):
                    raise ValueError("queued topic changed since export; review it again")
                coverage = previous.get("existing_coverage", {})
                # Reviewers may discover coverage locally, but cannot erase a live existing URL.
                if topic["existing_coverage"].get("status") == "existing" and any(
                        coverage.get(k) != topic["existing_coverage"].get(k) for k in ("status", "url")):
                    raise ValueError("live existing coverage must be retained in the review")
                for key in ("product_fit", "serp", "existing_coverage", "evidence", "reader", "buyer_question", "angle", "news"):
                    if key in previous:
                        topic[key] = previous[key]
            key = topic["keyword"].strip().casefold()
            if key in seen:
                raise ValueError("duplicate queued keyword; reconcile pages before drafting")
            # Validate each candidate before any research or writes.
            select({"schema_version": 1, "topics": [topic]}, today=today)
            seen.add(key)
            topics.append(topic)
        except (ValueError, TypeError, KeyError):
            invalid.append({"page_id": page_id, "decision": "research_needed",
                            "score_kind": "not scored: invalid or changed candidate input",
                            "reasons": ["Check required fields, evidence JSON, duplicate keywords, and changes since export."]})

    output = {"schema_version": 1, "topics": topics}
    if (candidates or {}).get("synthetic_example"):
        output["synthetic_example"] = True
    planned_research = [research_command(topics)] if topics else []
    if planned_research and (not dry_run or research_in_dry_run):
        try:
            completed = subprocess.run(planned_research[0], capture_output=True, text=True, check=True)
            research = json.loads(completed.stdout)
        except (OSError, subprocess.CalledProcessError, ValueError):
            raise ValueError("keyword research failed; no Notion writes made") from None
    # Keep old SERP notes in exports, but only today's actual inspection can pass.
    selection_topics = [t if t.get("serp", {}).get("reviewed_on") == today.isoformat()
                        else {**t, "serp": {}} for t in topics]
    selection = select({**output, "topics": selection_topics}, research, today)
    if not dry_run and selection["synthetic_example"]:
        raise ValueError("synthetic research cannot change live Notion pages")
    by_keyword = {t["keyword"]: t for t in topics}
    decisions = selection["decisions"]
    for result in decisions:
        topic = by_keyword[result["keyword"]]
        result["page_id"] = topic["notion_page_id"]
        if topic["existing_coverage"].get("status") == "existing":
            result.setdefault("existing_url", topic["existing_coverage"].get("url"))
    decisions.extend(invalid)
    if claim and not any(r["page_id"] == claim and r["decision"] == "draft_brief" for r in decisions):
        raise ValueError("claim blocked: page must be unowned and have a current draft_brief decision")
    plans = [{"page_id": r["page_id"],
              "status": NOTION_STATUS_DRAFTING if r["decision"] == "draft_brief" and r["page_id"] == claim
              else DECISION_STATUSES.get(r["decision"]), "note": decision_note(r)} for r in decisions]
    if not dry_run:
        for result, plan in zip(decisions, plans):
            write_decision(plan["page_id"], result, plan["status"])
    return {"candidates": output, "research": research, "decisions": decisions,
            "planned_keyword_research_calls": planned_research,
            "planned_serp_checks": [{"page_id": t["notion_page_id"], "keyword": t["keyword"],
                                     "country": "US", "language": "en"} for t in topics],
            "planned_status_writes": plans, "skipped": skipped, "dry_run": dry_run}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--research-in-dry-run", action="store_true", help="Allow paid research, still no Notion writes")
    parser.add_argument("--output", type=Path, help="Write candidates JSON locally")
    parser.add_argument("--research-output", type=Path, help="Save provider JSON for subsequent review")
    parser.add_argument("--candidates", type=Path, help="Previously exported candidates with human/Claude reviews")
    parser.add_argument("--research", type=Path, help="Preview research JSON; live runs always replace it with fresh research")
    parser.add_argument("--claim", help="Claim one reviewed draft_brief page as Drafting")
    args = parser.parse_args()
    load_env(required_keys=("NOTION_API_KEY",))
    try:
        result = run_intake(dry_run=args.dry_run, research_in_dry_run=args.research_in_dry_run,
                            candidates=json.loads(args.candidates.read_text()) if args.candidates else None,
                            research=json.loads(args.research.read_text()) if args.research else None,
                            claim=args.claim)
        if args.output:
            args.output.write_text(json.dumps(result["candidates"], indent=2) + "\n")
        if args.research_output:
            args.research_output.write_text(json.dumps(result["research"], indent=2) + "\n")
    except (ValueError, OSError, KeyError, TypeError):
        raise SystemExit("Intake stopped: check inputs, page ownership/status, and service availability; no approval was set.") from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
