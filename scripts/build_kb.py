#!/usr/bin/env python3
"""
Build the MakGeography teaching KB from the Obsidian vault.

What goes IN:  concept notes, revision notes, case studies, glossaries,
               fieldwork guides, the 2027 assessment framework, research notes.
What stays OUT: anything that is a live test, a mock, a predicted paper, an
               answer key, a mark scheme, or a student's own work.
               (David's standing rule: never expose his tests or anything
               derived from them.)

Outputs a single JSON file the app loads at startup:
    kb.json  ->  {meta, docs:[{id,title,topic,path,chunks:[{text,heading}]}]}
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

VAULT = Path(
    "/Users/davidhermes/Library/Mobile Documents/iCloud~md~obsidian/Documents/MakGeography"
)

# Source roots, in the order they should be searched / presented.
SOURCE_ROOTS = [
    "DSE Geography",
    "F2 Geography",
    "F3 Geography",
    "F6 Geography",
]

# Hard exclusions. A path matching any of these is NEVER ingested.
# These are tests, mocks, predicted papers, answer keys and mark schemes.
EXCLUDE_DIR_PATTERNS = [
    r"(?i)assessment/(?=.*predicted)",
    r"(?i)assessment/.*first term test",
    r"(?i)assessment/.*combo quiz",
    r"(?i)assessment/.*mock",
    r"(?i)predicted grade test",
    r"(?i)past paper \(dbq\)",
    r"(?i)past paper \(se\)",
    r"(?i)/cp\d+ dbq/.*dbq \(practice\)",
    r"(?i)/cp\d+ dbq/2026 p1 q3",
    r"(?i)cp6 dbq prep",
    r"(?i)dbq angles",
    r"(?i)data question set",
    r"(?i)mc question bank",
    r"(?i)mc quiz",
    r"(?i)past paper analysis",
    r"(?i)ep1 dynamic earth - basic concepts quiz",
    r"(?i)combo quiz",
    # A Kahoot drill file carries a full teacher answer key and a
    # distractor rationale table. It has no markdown headings, so the
    # section drop cannot reach it - exclude the file.
    r"(?i)kahoot drill",
]

# Substrings that mark a file as assessment material even if the path differs.
EXCLUDE_NAME_SUBSTRINGS = [
    "ans.pdf", "answer", "mark scheme", "marking scheme", "predicted grade test",
    "combo quiz", "first term test", "mock", "used-stem", "candidate marks",
]

# Note-level content that is fine to skip even in an included file.
#
# These sections are the teacher's own working material - answer keys, the
# register of stems already used, and the distractor analysis that explains
# why each wrong option is wrong. A student reading a note must not see
# them. Each pattern matches a heading; everything from that heading to the
# next heading of the same or higher level is dropped.
DROP_SECTION_PATTERNS = [
    r"(?im)^#{1,4}\s*.*\b(mark scheme|answer key|marking scheme|suggested answers)\b.*$",
    # The teacher-only working sections.
    r"(?im)^#{1,4}\s*.*\b(distractor rationale|distractor analysis|distractor notes)\b.*$",
    r"(?im)^#{1,4}\s*.*\b(register check|used-stem register|used stem register|stem register)\b.*$",
    r"(?im)^#{1,4}\s*.*\b(coverage check|syllabus coverage check|coverage note)\b.*$",
    r"(?im)^#{1,4}\s*.*\b(teacher only|for the teacher|teacher notes?)\b.*$",
    # The teacher's own key for a practice set, headed at level 1.
    r"(?im)^#{1,4}\s*.*\b(teacher key|teacher'?s key|key and rationale)\b.*$",
]

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
WIKILINK_RE = re.compile(r"!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
IMG_RE = re.compile(r"!\[\[([^\]]+)\]\]")
FENCE_RE = re.compile(r"```.*?```", re.S)
CALLOUT_RE = re.compile(r"^\s*> \[!(\w+)\][+-]?\s*$", re.M)


@dataclass
class Chunk:
    text: str
    heading: str
    n: int


@dataclass
class Doc:
    id: str
    title: str
    topic: str
    path: str
    source: str
    chunks: list


def strip_frontmatter(text: str) -> tuple[str, dict]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text, {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            v = v.strip().strip("'\"")
            if v and not v.startswith("["):
                meta[k.strip()] = v
            elif v.startswith("["):
                meta[k.strip()] = v.strip("[]").replace(",", " ")
    return text[m.end():], meta


def clean_markdown(text: str) -> str:
    """Strip Obsidian-specific syntax so the text reads cleanly to an LLM."""
    # Fenced code blocks -> keep a marker, drop the code (rare in these notes)
    text = FENCE_RE.sub("\n[code block omitted]\n", text)
    # Images entirely
    text = IMG_RE.sub("", text)
    # Wikilinks -> display text
    text = WIKILINK_RE.sub(lambda m: (m.group(2) or m.group(1)).split("|")[0].strip(), text)
    # Callout markers
    text = CALLOUT_RE.sub("", text)
    # Collapse > blockquote markers but keep the text
    text = re.sub(r"^>\s?", "", text, flags=re.M)
    # Markdown emphasis / headings markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # HTML-ish callout labels left behind
    text = re.sub(r"\[!(\w+)\][+-]?\s*", "", text)
    # Tables: keep as pipe rows, it reads fine
    # Horizontal rules
    text = re.sub(r"^\s*---+\s*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_chunks(text: str, max_chars: int = 1400) -> list:
    """Chunk by heading, then split long sections on paragraph boundaries."""
    chunks: list[Chunk] = []
    lines = text.splitlines()
    heading = ""
    buf: list[str] = []
    n = 0

    def flush():
        nonlocal buf, n
        body = "\n".join(buf).strip()
        if len(body) < 40:
            buf = []
            return
        if len(body) <= max_chars:
            chunks.append(Chunk(text=body, heading=heading, n=n))
            n += 1
        else:
            # split on blank lines, then greedily pack
            cur, size = [], 0
            for para in re.split(r"\n\s*\n", body):
                if size + len(para) + 2 > max_chars and cur:
                    chunks.append(Chunk(text="\n\n".join(cur), heading=heading, n=n))
                    n += 1
                    cur, size = [], 0
                cur.append(para)
                size += len(para) + 2
            if cur:
                chunks.append(Chunk(text="\n\n".join(cur), heading=heading, n=n))
                n += 1
        buf = []

    for line in lines:
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            flush()
            heading = h.group(2).strip()
        else:
            buf.append(line)
    flush()
    return chunks


def topic_from_path(rel: str) -> str:
    """Derive a syllabus-ish topic label from the path."""
    p = rel
    # Directory form: .../CP3/... or .../EP1/...
    m = re.search(r"(?i)/(CP[1-7]|EP1|F[1-6])(?:/|\b)", p)
    if m:
        return m.group(1).upper()
    # Filename form: "CP6_Disappearing_Green_Canopy_Detailed_Notes.md"
    m = re.search(r"(?i)(?:^|/)(CP[1-7]|EP1|F[1-6])[ _-]", p)
    if m:
        return m.group(1).upper()
    if "Research" in p:
        return "Research"
    return "General"


def is_excluded(rel: str) -> bool:
    low = rel.lower()
    for pat in EXCLUDE_DIR_PATTERNS:
        if re.search(pat, rel):
            return True
    name = Path(rel).name.lower()
    for s in EXCLUDE_NAME_SUBSTRINGS:
        if s in name:
            return True
    return False


def collect_files(root: Path) -> list:
    files = []
    for sr in SOURCE_ROOTS:
        base = root / sr
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != ".obsidian"]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                full = Path(dirpath) / fn
                rel = str(full.relative_to(root))
                if is_excluded(rel):
                    continue
                files.append(full)
    return sorted(files)


def build(root: Path, out: Path) -> dict:
    files = collect_files(root)
    docs = []
    skipped = []
    for full in files:
        rel = str(full.relative_to(root))
        try:
            raw = full.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        body, meta = strip_frontmatter(raw)
        title = meta.get("title") or full.stem.replace("_", " ")
        # Drop any answer-key sections
        for pat in DROP_SECTION_PATTERNS:
            body = re.sub(pat + r"\n(?:.*\n)*?(?=\n#{1,4}\s|\Z)", "", body)
        # Split on the ORIGINAL markdown so headings are captured, then clean
        # each chunk's text. (Cleaning first strips the '#' markers and every
        # chunk ends up with an empty heading.)
        chunks = []
        for c in split_into_chunks(body):
            text = clean_markdown(c.text)
            if len(text) < 40:
                continue
            chunks.append({"text": text, "heading": c.heading, "n": c.n})
        if not chunks:
            skipped.append(rel)
            continue
        docs.append(
            Doc(
                id=re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-"),
                title=title,
                topic=topic_from_path(rel),
                path=rel,
                source=meta.get("source", "") or meta.get("captured", ""),
                chunks=chunks,
            )
        )

    kb = {
        "meta": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source_root": str(root),
            "n_docs": len(docs),
            "n_chunks": sum(len(d.chunks) for d in docs),
            "excluded": len(skipped),
        },
        "docs": [asdict(d) for d in docs],
    }
    out.write_text(json.dumps(kb, ensure_ascii=False, indent=1), encoding="utf-8")
    return kb, skipped


import os  # noqa: E402  (used by collect_files)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=str(VAULT))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.vault)
    out = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "data" / "kb.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    kb, skipped = build(root, out)
    print(f"docs      : {kb['meta']['n_docs']}")
    print(f"chunks    : {kb['meta']['n_chunks']}")
    print(f"excluded  : {kb['meta']['excluded']}")
    print(f"written   : {out}")
    if skipped:
        print("\nskipped (no usable text):")
        for s in skipped:
            print("  -", s)
