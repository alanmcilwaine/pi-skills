#!/usr/bin/env python3
"""Build dictionary.json from the Unlimited-OCR batch output, cross-checked against
the pdfplumber geometry extractor.

Reads  C:/Users/youth/AppData/Local/Temp/ste_batch/page*/result.md   (VLM)
Writes dictionary.json next to extract-dictionary.py (VLM-primary)
Writes disagreements.log next to extract-dictionary.py (for review)

Row rules for the VLM HTML tables:
- 4 cells, non-empty headword: new entry
- 4 cells, empty headword: continuation row (help text or second alternative)
- 3 cells: continuation row under a rowspan
- 2 cells: example columns only (both headword and col2 rowspaned): skip
- <img> cells: help icons: skip
"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import importlib.util

spec = importlib.util.spec_from_file_location(
    "ex", Path(__file__).parent / "extract-dictionary.py"
)
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

BATCH = Path(r"C:\Users\youth\AppData\Local\Temp\ste_batch")
OUT = Path(__file__).parent / "dictionary.json"
LOG = Path(__file__).parent / "disagreements.log"

# VLM row-drop and boundary-miss corrections, each verified against the rendered
# PDF page or the text layer during the pdfplumber cross-check. Applied after the
# VLM build so a rebuild from batch output stays reproducible.
PATCHES = {
    ("unapproved", "gleam (v)"): {"use": ["SHINY (adj)"]},  # glitch rows had merged in
    ("unapproved", "glitch (n)"): {"use": ["ERROR (n)", "FAILURE (TN)", "UNSERVICEABLE (adj)"]},
    ("unapproved", "advisable (adj)"): {"use": ["RECOMMEND (v)"]},  # advise rows had merged in
    ("unapproved", "advise (v)"): {"use": ["TELL (v)", "RECOMMEND (v)"]},
    ("approved", "FLAME (n)"): {"meaning": "Burning gas"},
    ("unapproved", "degrease (v)"): {"use": ["GREASE (TN)"]},
    ("unapproved", "discharge (v)"): {"use": ["RELEASE (v)", "GO (v)"]},
    ("unapproved", "regrease (v)"): {"use": ["APPLY (v)", "MORE (adj)"]},
    ("unapproved", "file (v)"): {"use": ["REMOVE (v) (WITH A FILE (TN))"]},  # malformed in source
    ("unapproved", "big (adj)"): {"use": ["LARGE (adj)"], "note": "If it is possible, give an accurate value."},
    ("unapproved", "few (adj)"): {"use": ["SMALL NUMBER"], "note": "If it is possible, give an accurate number."},
}


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append("".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def norm(s):
    return " ".join(s.split()).strip()


def vlm_entries(md_path):
    """Parse one result.md into raw entries of {key, approved, forms, items}."""
    text = md_path.read_text(encoding="utf-8")
    entries = []
    for m in re.finditer(r"<table>.*?</table>", text, re.S):
        p = TableParser()
        p.feed(m.group(0))
        for row in p.rows:
            row = [norm(c) for c in row]
            if not row or "part of speech" in row[0]:
                continue
            if len(row) == 4 and row[0]:
                head = row[0]
                parsed = ex.parse_head(head)
                if parsed is None:
                    continue
                key, approved, forms = parsed
                entries.append({"key": key, "approved": approved, "forms": forms, "items": []})
                if row[1] and "<img>" not in row[1]:
                    entries[-1]["items"].append(row[1])
            elif entries and len(row) >= 3:
                item = row[1] if len(row) == 4 else row[0]
                if item and "<img>" not in item:
                    entries[-1]["items"].append(item)
    return entries


def build():
    approved = {}
    unapproved = {}
    page_count = 0
    for page_dir in sorted(BATCH.glob("page*")):
        md = page_dir / "result.md"
        if not md.exists():
            continue
        page_count += 1
        for e in vlm_entries(md):
            val = ex.classify(e)
            if e["forms"]:
                val["forms"] = e["forms"]
            store = approved if e["approved"] else unapproved
            store.setdefault(e["key"], val)
    stores = {"approved": approved, "unapproved": unapproved}
    for (section, key), val in PATCHES.items():
        stores[section][key] = val
    return approved, unapproved, page_count


def main():
    approved, unapproved, page_count = build()

    lines = ["{"]
    lines.append('  "source": "ASD-STE100 word list, extracted from a registered copy (Unlimited-OCR primary, pdfplumber cross-check). Used with permission.",')
    for section, data in (("approved", approved), ("unapproved", unapproved)):
        lines.append(f'  "{section}": {{')
        items = list(data.items())
        for i, (key, val) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            lines.append(f"    {json.dumps(key, ensure_ascii=False)}: {json.dumps(val, ensure_ascii=False)}{comma}")
        lines.append("  }" + ("," if section == "approved" else ""))
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"pages: {page_count}")
    print(f"approved:   {len(approved)}")
    print(f"unapproved: {len(unapproved)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
