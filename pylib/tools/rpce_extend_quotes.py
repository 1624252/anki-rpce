# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Extend truncated RONR quotes to complete, concept-covering spans.

Many authored quotes were trimmed just before the sentence ends, or at a colon
that introduces the list which actually states the rule. This tool relocates
each quote inside its cited RONR section and extends the end forward to the next
true sentence terminator — carrying through colon-introduced enumerations
(``a) ... ; and b) ...``) so the quote contains the whole rule — never ending on
a colon, comma, or dangling conjunction. Quotes are re-sliced from the cleaned
section text, so the result is verbatim (matching the app's plain-text display).

Usage:
    python rpce_extend_quotes.py <json_path> <quote_field> <section_field>
e.g. ...rpce_section2_scenarios.json quote section
     ...rpce_authored_questions.json quote cite
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "roberts_rules_of_order_12th_edition.md"

_ABBR = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "mr",
    "mrs",
    "dr",
    "no",
    "cf",
    "pp",
    "art",
    "sec",
    "st",
    "jr",
    "sr",
    "ex",
    "al",
    "viz",
    "op",
    "ibid",
}
MAX_SPAN = 700  # cap so a quote can't run away into the whole section


def clean(t: str) -> str:
    """Markdown-strip + cross-ref-elide to the app's plain-text display form."""
    t = re.sub(r"<a id=[^>]*></a>", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)  # [text](link) -> text
    t = t.replace("*", "")
    t = (
        t.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    t = re.sub(r"\(see [^)]*\)", "", t)  # (see 23:5)
    t = re.sub(r"\(\d[^)]*\)", "", t)  # (22), (10:44-51), (10:8(2)) remnants
    return re.sub(r"\s+", " ", t).strip()


def _section_texts() -> dict[str, str]:
    """Map ``p-<a>-<b>`` anchor id -> cleaned text of that section (up to the
    next section/heading anchor)."""
    raw = CORPUS.read_text(encoding="utf-8")
    # Split points: paragraph anchors and heading anchors.
    anchors = list(re.finditer(r'<a id="(p-\d+-\d+|h-\d+)"></a>', raw))
    out: dict[str, str] = {}
    for idx, m in enumerate(anchors):
        aid = m.group(1)
        if not aid.startswith("p-"):
            continue
        end = anchors[idx + 1].start() if idx + 1 < len(anchors) else len(raw)
        # Only keep the first (i.e. this) paragraph's text for the id.
        if aid not in out:
            out[aid] = clean(raw[m.end() : end])
    return out


def _anchor_for(section: str) -> str | None:
    m = re.match(r"(\d+):(\d+)", section or "")
    return f"p-{m.group(1)}-{m.group(2)}" if m else None


def _is_terminator(s: str, j: int) -> bool:
    """True when s[j] ends a sentence (not an abbreviation / list item / colon
    continuation), and what follows is not a list-item or conjunction."""
    if s[j] not in ".!?":
        return False
    k = j - 1
    while k >= 0 and (s[k].isalpha() or s[k] == "."):
        k -= 1
    word = s[k + 1 : j].lower().strip(".")
    if len(word) == 1 or word in _ABBR:
        return False
    rest = s[j + 1 :]
    if rest and rest[0] not in ' "':
        return False
    # list-item marker or conjunction => the enumeration/sentence continues
    if re.match(r"\s*(\(?[a-z0-9]{1,3}[.)]|and\b|or\b|but\b)", rest):
        return False
    nxt = re.match(r"\s*(\S)", rest)
    if nxt and not (nxt.group(1).isupper() or nxt.group(1) in '"'):
        return False
    return True


def extend_one(quote: str, sectext: str, min_prefix: int = 18) -> str | None:
    """Return the extended verbatim quote, or None if it can't be relocated.

    ``min_prefix`` guards against matching a too-short prefix at the wrong place
    (raise it when searching the whole corpus rather than a single section)."""
    q = clean(quote)
    if not q:
        return None
    start = -1
    for length in (80, 60, 45, 35, 25, min_prefix):
        if min_prefix <= length <= len(q):
            start = sectext.find(q[:length])
            if start >= 0:
                break
    if start < 0:
        return None
    # Where the original quote ended (suffix match), so we never shrink it.
    tail = q[-25:] if len(q) > 25 else q
    tidx = sectext.find(tail, start)
    orig_end = (tidx + len(tail)) if tidx >= 0 else min(start + len(q), len(sectext))
    # Collect all true sentence terminators in [start, cap]. Prefer the first one
    # at/after the original end (complete + never shrinks); if none fits under the
    # cap, fall back to the LAST terminator so the quote still ends cleanly rather
    # than being hard-cut mid-clause.
    limit = min(start + MAX_SPAN, len(sectext))
    terms: list[int] = []
    j = start + 30
    while j < limit:
        if _is_terminator(sectext, j):
            e = j + 1
            if e < len(sectext) and sectext[e] == '"':
                e += 1
            terms.append(e)
        j += 1
    if not terms:
        return None  # no clean boundary reachable -> leave the quote as-is
    end = next((e for e in terms if e >= orig_end), terms[-1])
    return sectext[start:end].strip()


def main(path: str, qfield: str, sfield: str) -> None:
    sect = _section_texts()
    full_corpus = clean(CORPUS.read_text(encoding="utf-8"))
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    items = data["scenarios"] if "scenarios" in data else data["questions"]
    extended = skipped = unchanged = 0
    for it in items:
        quote = (it.get(qfield) or "").strip()
        section = (it.get(sfield) or "").strip()
        if not quote or not section:
            continue
        anchor = _anchor_for(section)
        stext = sect.get(anchor or "")
        new = extend_one(quote, stext) if stext else None
        if not new:
            # The quote's text may actually live in a different section than the
            # declared one; relocate it in the whole corpus (longer prefix so we
            # don't match the wrong place) and extend there.
            new = extend_one(quote, full_corpus, min_prefix=40)
        if not new:
            skipped += 1
            continue
        if new == clean(quote):
            unchanged += 1
            continue
        if len(new) < len(clean(quote)):
            unchanged += 1  # never shrink
            continue
        it[qfield] = new
        extended += 1
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{p.name}: extended {extended}, unchanged {unchanged}, skipped {skipped}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
