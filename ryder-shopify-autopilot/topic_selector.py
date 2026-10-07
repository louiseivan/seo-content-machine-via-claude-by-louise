"""Turn researched keywords and human review into buyer-focused draft briefs.

Offline: python3 topic_selector.py --candidates examples/topics.synthetic.json
        --research examples/research.synthetic.json --pretty
Live research is optional, but missing metrics are reported as missing, never zero.
No API calls or publishing occur here.
"""

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from urllib.parse import urlparse

PERSONAS = {"exchange_holder", "switching_owner", "gift_referral", "power_user"}
INTENTS = {"decision", "comparison", "how_to_buy", "informational", "other"}
WEIGHTS = {
    "persona": {"exchange_holder": 35, "switching_owner": 20,
                "gift_referral": 8, "power_user": 0},
    "intent": {"decision": 30, "comparison": 28, "how_to_buy": 25,
               "informational": 8, "other": 0},
}


def _date(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _recent(value, today, days=120):
    day = _date(value)
    return day is not None and 0 <= (today - day).days <= days


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _web_url(value):
    if not _nonempty(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _research_index(data, today):
    if data is None:
        return {}, ["research file absent"]
    if not isinstance(data, dict):
        raise ValueError("research must be an object")
    if data.get("schema_version") != 1 or not isinstance(data.get("rows"), list):
        raise ValueError("research requires schema_version 1 and rows array")
    if (not isinstance(data.get("providers"), list)
        or not all(_nonempty(p) for p in data["providers"])
        or not isinstance(data.get("metric_sources"), dict)):
        raise ValueError("research requires providers and metric_sources provenance")
    problems = []
    if data.get("country") != "US":
        problems.append("research country must be US")
    if data.get("language") != "en":
        problems.append("research language must be en")
    if not _recent(data.get("collected_on"), today):
        problems.append("research collected_on missing, future, or older than 120 days")
    index = {}
    for row in data["rows"]:
        if not isinstance(row, dict):
            raise ValueError("each research row must be an object")
        if not _nonempty(row.get("keyword")):
            raise ValueError("research row has no keyword")
        key = row["keyword"].strip().casefold()
        if key in index:
            raise ValueError("duplicate research keyword: " + row["keyword"])
        metrics = {}
        for provider in ("d4s", "ahrefs"):
            volume = row.get(provider + "_volume")
            difficulty = row.get(provider + "_difficulty")
            if volume is not None and (type(volume) is not int or volume < 0):
                raise ValueError("invalid " + provider + " volume for " + key)
            if difficulty is not None and (type(difficulty) not in (int, float)
                                           or not math.isfinite(difficulty)
                                           or not 0 <= difficulty <= 100):
                raise ValueError("invalid " + provider + " difficulty for " + key)
            metrics[provider] = {"volume": volume, "difficulty": difficulty}
            if (volume is not None or difficulty is not None) and not _nonempty(data["metric_sources"].get(provider)):
                problem = "research source missing for " + provider
                if problem not in problems:
                    problems.append(problem)
        index[key] = metrics
    return index, problems


def select(candidates, research=None, today=None):
    """Return decisions; manual review fields are gates, never inferred from volume."""
    today = today or dt.date.today()
    if not isinstance(candidates, dict) or candidates.get("schema_version") != 1:
        raise ValueError("candidates require schema_version 1")
    if not isinstance(candidates.get("topics"), list):
        raise ValueError("candidates require topics array")
    index, research_problems = _research_index(research, today)
    seen = set()
    out = []
    for topic in candidates["topics"]:
        if not isinstance(topic, dict):
            raise ValueError("each topic must be an object")
        keyword = topic.get("keyword")
        if not _nonempty(keyword):
            raise ValueError("topic keyword is required")
        key = keyword.strip().casefold()
        if key in seen:
            raise ValueError("duplicate candidate keyword: " + keyword)
        seen.add(key)
        persona, intent = topic.get("persona"), topic.get("buyer_intent")
        if (not isinstance(persona, str) or not isinstance(intent, str)
            or persona not in PERSONAS or intent not in INTENTS):
            raise ValueError("invalid persona or buyer_intent for " + keyword)
        reasons = []
        coverage = topic.get("existing_coverage", {})
        fit = topic.get("product_fit", {})
        serp = topic.get("serp", {})
        evidence = topic.get("evidence", [])
        if any(not isinstance(value, dict) for value in (coverage, fit, serp)):
            raise ValueError("coverage, product_fit, and serp must be objects for " + keyword)
        metrics = index.get(key)
        if not isinstance(evidence, list):
            raise ValueError("evidence must be an array for " + keyword)
        if persona == "power_user":
            reasons.append("power-user topic is outside current priority")
            decision = "reject"
        elif fit.get("verified") is False and _nonempty(fit.get("rationale")):
            reasons.append("reviewer confirmed product does not fit")
            decision = "reject"
        elif (coverage.get("status") == "existing"
              and _nonempty(coverage.get("url"))
              and _recent(coverage.get("checked_on"), today)):
            reasons.append("existing coverage: refresh or link before proposing a new article")
            decision = "update_existing"
        else:
            decision = "draft_brief"
            if (fit.get("verified") is not True or not _nonempty(fit.get("rationale"))
                or not _nonempty(fit.get("verified_by"))
                or not _recent(fit.get("verified_on"), today)):
                reasons.append("product fit needs current human verification, rationale, and reviewer")
            if (serp.get("intent_match") is not True
                or serp.get("country") != "US"
                or not _recent(serp.get("reviewed_on"), today)
                or not _web_url(serp.get("source_url"))
                or not _nonempty(serp.get("notes"))):
                reasons.append("US SERP intent needs dated review with source and notes")
            if (coverage.get("status") != "none"
                or not _recent(coverage.get("checked_on"), today)
                or not _nonempty(coverage.get("source"))):
                reasons.append("existing coverage check needs dated source and explicit none/existing")
            valid_evidence = [e for e in evidence if isinstance(e, dict)
                              and _nonempty(e.get("claim"))
                              and _web_url(e.get("source_url"))
                              and _recent(e.get("checked_on"), today)]
            if not valid_evidence:
                reasons.append("at least one claim needs a current cited source")
            if research_problems:
                reasons.extend(research_problems)
            if metrics is None:
                reasons.append("keyword metrics missing from research")
            elif all(v["volume"] is None for v in metrics.values()):
                reasons.append("search volume missing from both providers")
            if reasons:
                decision = "research_needed"
        score = (WEIGHTS["persona"][persona] + WEIGHTS["intent"][intent]
                 + (15 if fit.get("verified") is True else 0)
                 + (10 if serp.get("intent_match") is True else 0)
                 + (5 if evidence else 0))
        if metrics:
            volumes = [m["volume"] for m in metrics.values() if m["volume"] is not None]
            if volumes:
                score += 5 if max(volumes) > 0 else 0
        result = {"keyword": keyword, "decision": decision, "score": score,
                  "score_kind": "heuristic priority (0-100), not a ranking or conversion prediction",
                  "persona": persona, "buyer_intent": intent,
                  "reasons": reasons, "metrics": metrics,
                  "research_country": research.get("country") if research else None,
                  "research_collected_on": research.get("collected_on") if research else None}
        if decision == "draft_brief":
            result["brief"] = {
                "reader": ("Crypto holder on an exchange choosing a first hardware wallet"
                           if persona == "exchange_holder" else topic.get("reader")),
                "buyer_question": topic.get("buyer_question"),
                "angle": topic.get("angle"),
                "product_fit_rationale": fit["rationale"],
                "serp_notes": serp["notes"],
                "evidence": valid_evidence,
                "editorial_next_step": "Draft for human review; run the editorial gate before Notion approval.",
            }
            if not all(_nonempty(result["brief"].get(k)) for k in
                       ("reader", "buyer_question", "angle")):
                result["decision"] = "research_needed"
                result["reasons"].append("brief needs reader, buyer_question, and angle")
                del result["brief"]
        elif decision == "update_existing":
            result["existing_url"] = coverage["url"]
        out.append(result)
    out.sort(key=lambda r: ({"draft_brief": 0, "update_existing": 1,
                             "research_needed": 2, "reject": 3}[r["decision"]],
                            -r["score"], r["keyword"].casefold()))
    return {"schema_version": 1, "generated_on": today.isoformat(),
            "synthetic_example": bool(candidates.get("synthetic_example") or
                                      (research or {}).get("synthetic_example")),
            "research_provenance": None if research is None else {
                "country": research.get("country"),
                "language": research.get("language"),
                "collected_on": research.get("collected_on"),
                "providers": research.get("providers"),
                "metric_sources": research.get("metric_sources"),
                "notes": research.get("notes", [])},
            "decisions": out}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--research", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--as-of", type=dt.date.fromisoformat,
                        help="Evaluation date YYYY-MM-DD (use 2026-10-07 with bundled fixture)")
    args = parser.parse_args()
    with args.candidates.open() as f:
        candidates = json.load(f)
    if args.research:
        with args.research.open() as f:
            research = json.load(f)
    else:
        research = None
    result = select(candidates, research, today=args.as_of)
    rendered = json.dumps(result, indent=2 if args.pretty else None) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
