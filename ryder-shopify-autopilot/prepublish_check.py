"""Editorial gate for Ryder content.

Encodes the MANDATORY PRE-PUBLISH CHECKLIST from
CLAUDE OUTPUTS/Ryder One/RYDER_CONTENT_SYSTEM_PROMPT.md (2026-08-10 revision).
Every draft must pass before it goes to Notion; before a Shopify push the
gate runs again in mode="shopify", where even red-wrapped [VERIFY] markers
block (nothing unverified may go live).

Usage:
    python3 prepublish_check.py draft.md [--shopify]
    from prepublish_check import check_article
    result = check_article(text)          # {'passed': bool, 'errors': [...], 'warnings': [...]}
"""

import datetime
import re
import sys

BANNED_WORDS = [
    "actually", "genuinely", "genuine", "honestly", "straightforward",
    "serious", "seriously", "truly", "really", "simply", "basically",
    "essentially", "in fact", "indeed", "crucial", "crucially", "vital",
    "vitally", "pivotal", "delve", "delves", "delving", "leverage",
    "utilize", "utilizes", "utilizing", "robust", "seamless", "seamlessly",
    "best-in-class", "world-class", "world's first", "game-changer",
    "game-changing", "revolutionary", "cutting-edge", "state-of-the-art",
    "unparalleled", "comprehensive",
]

# Product phrasings that contradict canonical specs (never allowed).
BANNED_PRODUCT_PHRASES = [
    "card-sized", "card-shaped", "size of a credit card", "battery-free",
    "battery free", "no battery to charge", "tap and go", "no charging needed",
    "usb-c", "usb c", "lightning port", "passive device",
]

# $149 Starter / $179 Super Safe verified on ryder.id 2026-08-10.
WRONG_PRICES = ["$119", "$169", "$189", "$199", "$229",
                "119 USD", "169 USD", "189 USD", "199 USD", "229 USD"]

REPEATED_ADJECTIVES = ["fragile", "permanent", "physical", "meaningful",
                       "real", "honest", "catastrophic"]


def _strip_html(text):
    return re.sub(r"<[^>]+>", " ", text)


def _paragraphs(text):
    """Prose paragraphs only: skips headings, list items, tables, code."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped or stripped.startswith(("#", "-", "*", ">", "|", "```", "1.")):
            continue
        out.append(re.sub(r"\s+", " ", stripped))
    return out


def _sentences(paragraph):
    parts = re.split(r"(?<=[.!?])\s+", paragraph)
    return [p.strip() for p in parts if p.strip()]


def check_article(text, mode="notion", today=None):
    errors, warnings = [], []
    today = today or datetime.date.today()
    plain = _strip_html(text)
    lower = plain.lower()

    # 1. Banned word scan
    for word in BANNED_WORDS:
        pattern = r"\b" + re.escape(word).replace(r"\ ", r"\s+") + r"\b"
        hits = len(re.findall(pattern, lower))
        if hits:
            errors.append(f"banned word '{word}' x{hits}")

    # 2. Em dash scan (en dash flagged too, per checklist)
    if "—" in text:
        errors.append(f"em dash x{text.count('—')} (zero allowed)")
    if "–" in text:
        errors.append(f"en dash x{text.count('–')} (replace: colon/comma/parens/break)")

    # 3. Choppy rhythm scan
    for i, para in enumerate(_paragraphs(plain), 1):
        sents = _sentences(para)
        if len(sents) < 3:
            continue
        firsts = [re.sub(r"[^\w']", "", s.split()[0]).lower() for s in sents if s.split()]
        run = 1
        for a, b in zip(firsts, firsts[1:]):
            run = run + 1 if a == b and a else 1
            if run >= 3:
                errors.append(f"para {i}: 3+ consecutive sentences open with '{b}'")
                break
        run = 0
        for s in sents:
            run = run + 1 if len(s.split()) < 8 else 0
            if run >= 3:
                errors.append(f"para {i}: 3+ short declaratives (<8 words) in a row")
                break
        if all(len(s.split()) < 15 for s in sents):
            errors.append(f"para {i}: every sentence under 15 words; add one 20+ word sentence")
        fragments = sum(1 for s in sents if len(s.split()) <= 3)
        if fragments >= 2:
            warnings.append(f"para {i}: {fragments} possible fragments (limit one)")

    # 4. Rhetorical-contrast scan
    contrasts = len(re.findall(r",\s+not\s+[^,.;]{2,40}[.!?]", plain))
    contrasts += len(re.findall(r"\bnot just\b[^.!?]*\bbut\b", lower))
    contrasts += len(re.findall(r"(?<=[.!?]\s)Not\s+[^.!?]{2,30}\.\s+[A-Z][^.!?]{2,30}\.", plain))
    if contrasts > 1:
        errors.append(f"rhetorical contrast ('X, not Y' family) x{contrasts}; limit 1, default 0")
    elif contrasts == 1:
        warnings.append("one rhetorical contrast present; keep only if it carries the section's central point")

    # 5. Repeated-word scan
    for adj in REPEATED_ADJECTIVES:
        hits = len(re.findall(r"\b" + adj + r"\b", lower))
        if hits > 1:
            errors.append(f"adjective '{adj}' x{hits}; swap one for a synonym")

    # 6. [VERIFY] marker scan
    bare = len(re.findall(r"\[VERIFY(?![^\]]*\])?", _strip_html(
        re.sub(r'<span[^>]*color=.red.[^>]*>.*?</span>', "", text, flags=re.S))))
    wrapped = len(re.findall(r'<span[^>]*color=.red.[^>]*>\s*\[VERIFY', text))
    if bare:
        errors.append(f"bare [VERIFY] marker x{bare}: resolve external claims with cited sources")
    if wrapped:
        if mode == "shopify":
            errors.append(f"red-wrapped [VERIFY] marker x{wrapped}: product team must resolve before going live")
        else:
            warnings.append(f"red-wrapped internal [VERIFY] marker x{wrapped} awaiting product team")

    # 7. Year-and-date scan
    for year in sorted({int(y) for y in re.findall(r"\b(20\d{2})\b", plain)}):
        if year > today.year:
            warnings.append(f"future year {year} referenced; confirm tense and intent")
    if re.search(r"\bthis year\b|\blast year\b|\bnext year\b", lower):
        warnings.append("relative year phrase ('this/last/next year'); use the explicit year")

    # Product accuracy (spec section of the system prompt)
    for phrase in BANNED_PRODUCT_PHRASES:
        if phrase in lower:
            errors.append(f"banned product phrasing '{phrase}' (contradicts canonical specs)")
    for price in WRONG_PRICES:
        if price.lower() in lower:
            errors.append(f"wrong price '{price}' (current: $149 Starter / $179 Super Safe)")

    # Backup/recovery sections must name TapSafe
    for m in re.finditer(r"^##\s+(.*)$", text, re.M):
        heading = m.group(1)
        if re.search(r"backup|recover|seed phrase|storage", heading, re.I):
            section = text[m.end():]
            nxt = re.search(r"^##\s+", section, re.M)
            if nxt:
                section = section[:nxt.start()]
            if "tapsafe" not in section.lower():
                errors.append(f"H2 '{heading}' covers backup/recovery but never names TapSafe")

    return {"passed": not errors, "errors": errors, "warnings": warnings}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = "shopify" if "--shopify" in sys.argv else "notion"
    if not args:
        raise SystemExit("usage: python3 prepublish_check.py draft.md [--shopify]")
    with open(args[0]) as f:
        result = check_article(f.read(), mode=mode)
    for e in result["errors"]:
        print(f"FAIL  {e}")
    for w in result["warnings"]:
        print(f"warn  {w}")
    print("PASSED" if result["passed"] else f"FAILED ({len(result['errors'])} errors)")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
