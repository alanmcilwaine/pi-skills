#!/usr/bin/env python3
"""Extract the ASD-STE100 word list from a registered spec PDF.

ASD-STE100 content is used with permission.
Requires: pip install pdfplumber
Usage:   python extract-dictionary.py "C:/path/to/ASD-STE100_ISSUE9.pdf"

Method: the word list is a ruled table. Entries are bands between horizontal rules;
a band with no headword in column 1 is a continuation of the previous entry
(help rows, page breaks). Verified against rendered pages, not assumptions.
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber

WORD_LIST_PAGE = re.compile(r"Page 2-1-")  # dictionary word list pages only (intro is 2-0-)
SKIP = re.compile(
    r"^(Part 2|Page 2-|ASD-STE100|Simplified Technical|Keyword|Issue |\d{4}-\d{2}-\d{2})",
    re.I,
)
LETTER = re.compile(r"^[A-Z]$")
PAREN = re.compile(r"\(([^()]*)\)")
POS_TEXT = re.compile(r"^[a-z][a-z &,]*$")
CAPS = re.compile(r"^[A-Z0-9 ,()/'-]+$")


def cluster_lines(words, tol=3.5):
    """Group words into (top, text) lines by vertical position."""
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines = []
    for w in words:
        if lines and abs(w["top"] - lines[-1][0]) <= tol:
            lines[-1][1].append(w["text"])
        else:
            lines.append([w["top"], [w["text"]]])
    return [(top, " ".join(texts)) for top, texts in lines]


def rule_coverage(page):
    """Map each horizontal edge's y-position to its merged x-coverage.

    Entry rules span the full table (~490pt). Sub-row rules span only the
    example columns (~259pt). Icons and underlines are small.
    """
    groups = {}
    for e in page.edges:
        if e["orientation"] == "h" and e["x1"] - e["x0"] > 1:
            groups.setdefault(round(e["top"]), []).append((e["x0"], e["x1"]))
    coverage = {}
    for top, segs in groups.items():
        cov = 0
        cur = None
        for x0, x1 in sorted(segs):
            if cur is None:
                cur = [x0, x1]
            elif x0 <= cur[1] + 3:
                cur[1] = max(cur[1], x1)
            else:
                cov += cur[1] - cur[0]
                cur = [x0, x1]
        cov += cur[1] - cur[0]
        coverage[top] = cov
    return coverage


def cluster_items(sub_bands):
    """One item per sub-row band: the joined lines of column 2 within it."""
    return [text for text in sub_bands if text]


def parse_head(s):
    """Parse a column-1 headword string into (key, approved, forms).

    Handles: ACCEPT (v), ACCEPTS, ACCEPTED  |  little (a little) (adj)  |  SMALL (adj) (SMALLER, SMALLEST)
    """
    groups = list(PAREN.finditer(s))
    pos_end = None
    for g in reversed(groups):
        if POS_TEXT.match(g.group(1)):
            pos_end = g.end()
            break
    if pos_end is None:
        return None
    key = s[:pos_end].rstrip(" ,")
    m = re.match(r"^([A-Za-z]+)", key)
    if not m:
        return None
    approved = m.group(1).isupper()

    tail = s[pos_end:]
    forms = []
    for g in PAREN.finditer(tail):  # (SMALLER, SMALLEST)
        forms += [t.strip() for t in g.group(1).split(",") if t.strip()]
    for t in PAREN.sub("", tail).split(","):  # , ACCEPTS, ACCEPTED
        if t.strip() and CAPS.match(t.strip()):
            forms.append(t.strip())
    return key, approved, forms


def dedupe(tops, tol=2.5):
    """Merge rule tops drawn as ~1pt-tall rect pairs into single positions."""
    out = []
    for t in sorted(tops):
        if out and t - out[-1] <= tol:
            continue
        out.append(t)
    return out


def parse_page(page, entries):
    words = page.extract_words()
    approved_hdr = next((w for w in words if w["text"] == "Approved"), None)
    if approved_hdr is None:
        return
    ste_hdr = next(
        (w for w in words if w["text"] == "STE" and abs(w["top"] - approved_hdr["top"]) < 25),
        None,
    )
    col1_max = approved_hdr["x0"] - 4
    col2_max = ste_hdr["x0"] - 4 if ste_hdr else 307.0

    footer = next((w for w in words if w["text"] == "Issue"), None)
    page_bottom = footer["top"] - 5 if footer else page.height

    coverage = rule_coverage(page)
    full = dedupe(t for t, c in coverage.items() if c > 400 and t > approved_hdr["top"] and t < page_bottom)
    partial = dedupe(t for t, c in coverage.items() if 150 < c <= 400 and t > approved_hdr["top"])
    if not full:
        return

    bands = [(full[i], full[i + 1]) for i in range(len(full) - 1)] + [(full[-1], page_bottom)]

    for band_top, band_bottom in bands:
        in_band = lambda w: band_top + 0.5 < w["top"] < band_bottom - 0.5
        col1 = [w for w in words if 50 <= w["x0"] < col1_max and in_band(w)]

        # Column 2, split into one item per sub-row (partial rules mark sub-rows).
        splits = [t for t in partial if band_top + 2 < t < band_bottom - 2]
        edges = [band_top] + splits + [band_bottom]
        col2_items = []
        for st, sb in zip(edges, edges[1:]):
            ws = [w for w in words if col1_max <= w["x0"] < col2_max and st + 0.5 < w["top"] < sb - 0.5]
            text = " ".join(s for _, s in cluster_lines(ws) if not SKIP.match(s)).strip()
            if text and not SKIP.match(text):
                col2_items.append(text)

        col1_lines = [
            (t, s) for t, s in cluster_lines(col1) if not SKIP.match(s) and not LETTER.match(s)
        ]
        if col1_lines:
            head_text = " ".join(s for _, s in col1_lines)
            parsed = parse_head(head_text)
            if parsed is None:
                continue
            key, approved, forms = parsed
            entries.append({"key": key, "approved": approved, "forms": forms, "items": col2_items})
        elif col2_items and entries:
            # Continuation band: help row or page-break spillover.
            entries[-1]["items"] += col2_items


def is_caps(item):
    """True when the item is uppercase once (pos) groups are stripped."""
    core = PAREN.sub("", item)
    return bool(re.search(r"[A-Z]", core)) and not re.search(r"[a-z]", core)


def split_alts(item):
    """Split a multi-alternative item: 'USE (v) CORRECT (adj)' -> two entries."""
    return [p.strip() for p in re.split(r"(?<=\))\s+(?=[A-Z])", item) if p.strip()]


NOTE_PREFIX = re.compile(r"\b(For [^:]*use:)$")  # boilerplate guidance: 'For other meanings, use:'


def classify(entry):
    """Split column-2 items into alternatives (or meaning) and a note."""
    alts, texts, note = [], [], None
    for item in entry["items"]:
        if not is_caps(item):
            m = NOTE_PREFIX.search(item)
            if m:
                head = item[: m.start()].strip()
                if head:
                    texts.append(head)
                note = m.group(1)
            elif item.endswith(":"):
                note = item
            else:
                texts.append(item)
        elif is_caps(item):
            parts = split_alts(item)
            if note and parts:
                note = f"{note} {parts[0]}"
                parts = parts[1:]
            alts.extend(parts)
        else:
            texts.append(item)

    if entry["approved"]:
        val = {"meaning": " | ".join(texts)}
        if alts:
            note = (note + " " if note else "") + " ".join(alts)
    else:
        val = {"use": alts}
        if texts:
            note = (note + " " if note else "") + " ".join(texts)
    if note:
        val["note"] = note
    return val


def main():
    pdf_path = sys.argv[1]
    out_path = Path(__file__).parent / "dictionary.json"

    raw = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if WORD_LIST_PAGE.search(text):
                parse_page(page, raw)

    approved = {}
    unapproved = {}
    violations = []
    for e in raw:
        val = classify(e)
        if e["forms"]:
            val["forms"] = e["forms"]
        store = approved if e["approved"] else unapproved
        if e["key"] in store:
            violations.append(f"duplicate: {e['key']}")
        store.setdefault(e["key"], val)
        if e["approved"] and not val["meaning"]:
            violations.append(f"empty meaning: {e['key']}")
        if not e["approved"] and not val["use"] and not val.get("note"):
            violations.append(f"no alternative: {e['key']}")

    lines = ["{"]
    lines.append('  "source": "ASD-STE100 word list, extracted locally from a registered copy. Do not commit.",')
    for section, data in (("approved", approved), ("unapproved", unapproved)):
        lines.append(f'  "{section}": {{')
        items = list(data.items())
        for i, (key, val) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            lines.append(f"    {json.dumps(key, ensure_ascii=False)}: {json.dumps(val, ensure_ascii=False)}{comma}")
        lines.append("  }" + ("," if section == "approved" else ""))
    lines.append("}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"entries:    {len(raw)} (approved {len(approved)}, unapproved {len(unapproved)})")
    print(f"violations: {len(violations)}")
    for v in violations[:10]:
        print("  " + v)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
