#!/usr/bin/env python3
"""Deterministic pre-pass for the writing skill, POS-aware via spaCy.

Flags: unapproved STE words (matched by lemma AND part of speech), em dashes,
emojis, and sentences over 25 words. Code fences and inline code are ignored.
Usage: python check.py <file>   or   type text | python check.py
Exit code 1 when anything is flagged, 0 when clean.
"""

import json
import re
import sys
from bisect import bisect
from pathlib import Path

import spacy

HERE = Path(__file__).parent

POS_MAP = {
    "n": {"NOUN", "PROPN"},
    "v": {"VERB", "AUX"},
    "adj": {"ADJ"},
    "adv": {"ADV"},
    "prep": {"ADP"},
    "conj": {"CCONJ", "SCONJ"},
    "art": {"DET"},
    "pron": {"PRON"},
    "num": {"NUM"},
    "interj": {"INTJ"},
}

PARENS = re.compile(r"\(([^()]*)\)")
QUALIFIER = re.compile(r"^[a-z][a-z &,]*$")


def strip_code(text):
    """Blank out fenced blocks and inline code, preserving line structure."""
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), text)
    return text


def load_glossary():
    path = HERE / "technical-nouns.txt"
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def load_entries():
    """Yield (phrase, key, suggestion, pos_classes). phrase of one word = POS-checked."""
    entries = []
    dict_path = HERE / "dictionary.json"
    if dict_path.exists():
        data = json.loads(dict_path.read_text(encoding="utf-8"))
        for key, val in data.get("unapproved", {}).items():
            groups = PARENS.findall(key)
            pos = groups[-1] if groups else ""
            head = PARENS.sub("", key).strip()
            if len(groups) >= 2 and QUALIFIER.match(groups[-1]) and QUALIFIER.match(groups[-2]):
                # little (a little) (adj) -> "a little"; provided (that) (conj) -> "provided that"
                if head.lower() in groups[-2].lower():
                    phrase, pos_classes = groups[-2], None
                else:
                    phrase, pos_classes = f"{head} {groups[-2]}", None
            elif " " in head:
                phrase, pos_classes = head, None
            else:
                phrase = head
                pos_classes = set()
                for p in pos.split("&"):
                    pos_classes |= POS_MAP.get(p.strip(), set())
            use = val.get("use", [])
            suggestion = " | ".join(use) if isinstance(use, list) else str(use)
            entries.append((phrase.lower(), key, suggestion or "see dictionary", pos_classes))

    seen = {e[0] for e in entries}
    ste = (HERE / "ste100.md").read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(ste) if l.startswith("## Substitution table")), -1)
    if start != -1:
        for line in ste[start + 1 :]:
            if line.startswith("## "):
                break
            m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", line)
            if not m or m.group(1).strip("- ") == "" or "unapproved" in m.group(1).lower():
                continue
            bad, good = m.group(1).strip(), m.group(2).strip()
            if bad.lower() not in seen:
                entries.append((bad.lower(), bad, good, None))
    # Longest phrases first so they claim their spans before component words.
    entries.sort(key=lambda e: -len(e[0]))
    return entries


def spans_for(text, phrase):
    return [(m.start(), m.end()) for m in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.I)]


def main():
    unknown_mode = "--unknown" in sys.argv
    path_arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    raw = Path(path_arg).read_text(encoding="utf-8") if path_arg else sys.stdin.read()
    text = strip_code(raw)
    # Headings have no terminator; give them one so sentences do not glue together.
    text = re.sub(r"^(#{1,6}\s.*)$", r"\1.", text, flags=re.M)
    line_starts = [m.start() for m in re.finditer(r"^", text, re.M)] or [0]
    line_of = lambda idx: bisect(line_starts, idx)

    findings = []  # (line, message)
    claimed = []

    def overlaps(start, end):
        return any(start < ce and end > cs for cs, ce in claimed)

    for phrase in load_glossary():
        for start, end in spans_for(text, phrase):
            claimed.append((start, end))  # technical nouns never flag

    entries = load_entries()
    nlp = spacy.load("en_core_web_sm", disable=["ner"])

    # Phrase entries first (regex on text); single words afterwards (POS-checked).
    single = []
    for phrase, key, suggestion, pos_classes in entries:
        if " " in phrase or pos_classes is None:
            for start, end in spans_for(text, phrase):
                if not overlaps(start, end):
                    claimed.append((start, end))
                    findings.append((line_of(start), f'unapproved "{key}" -> use "{suggestion}"'))
        else:
            single.append((phrase, key, suggestion, pos_classes))

    by_word = {}
    for phrase, key, suggestion, pos_classes in single:
        by_word.setdefault(phrase, []).append((key, suggestion, pos_classes))

    doc = nlp(text)
    for token in doc:
        word = token.lemma_.lower()
        for key, suggestion, pos_classes in by_word.get(word, by_word.get(token.lower_, [])):
            if token.pos_ in pos_classes and not overlaps(token.idx, token.idx + len(token.text)):
                claimed.append((token.idx, token.idx + len(token.text)))
                findings.append((line_of(token.idx), f'unapproved "{key}" -> use "{suggestion}"'))
                break  # one flag per occurrence

    for m in re.finditer("—", text):
        findings.append((line_of(m.start()), "em dash (house rule: use a colon, or split the sentence)"))
    for i, ch in enumerate(text):
        o = ord(ch)
        if 0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF or o == 0xFE0F:
            findings.append((line_of(i), "emoji (house rule)"))
    for sent in doc.sents:
        words = [t for t in sent if not t.is_punct]
        if len(words) > 25:
            findings.append(
                (line_of(sent.start_char), f"{len(words)}-word sentence (max 20 for instructions, 25 for descriptions)")
            )

    findings.sort()
    for line, message in findings:
        print(f"line {line}: {message}")

    if unknown_mode:
        known = set()
        dict_path = HERE / "dictionary.json"
        if dict_path.exists():
            data = json.loads(dict_path.read_text(encoding="utf-8"))
            for section in ("approved", "unapproved"):
                for key, val in data.get(section, {}).items():
                    known.add(PARENS.sub("", key).strip().lower())
                    for form in val.get("forms", []):
                        known.add(form.lower())
        for phrase in load_glossary():
            known.update(phrase.lower().split())

        unknown = {}
        for token in doc:
            if not token.is_alpha or token.is_stop or len(token.text) < 3:
                continue
            lemma = token.lemma_.lower()
            if lemma not in known and token.lower_ not in known:
                word = token.lower_
                prev = unknown.get(word)
                unknown[word] = (token.pos_, (prev[1] + 1) if prev else 1, prev[2] if prev else line_of(token.idx))
        if unknown:
            print("\nunknown words (not in dictionary or glossary; declare as technical nouns or rephrase):")
            for word, (pos, count, line) in sorted(unknown.items(), key=lambda kv: -kv[1][1]):
                print(f"  {word} ({pos.lower()}) x{count}, first at line {line}")

    print("clean" if not findings else f"{len(findings)} finding(s)")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
