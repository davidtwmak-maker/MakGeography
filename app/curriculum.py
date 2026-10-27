"""Curriculum-to-notes matching.

The official curriculum gives every sub-topic a set of source hints: the
titles of the notes that cover it. This module turns those hints into the
actual note content.

Both the Notes section and the Essay Generator draw on this, so a student
sees the same material either way.
"""
from __future__ import annotations

import re

# Words that carry no signal when deciding which section of a note is
# relevant to a curriculum heading.
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "these", "those",
    "into", "their", "there", "when", "what", "which", "while", "where",
    "including", "include", "includes", "such", "other", "others", "than",
    "then", "they", "them", "been", "being", "both", "each", "more", "most",
    "some", "under", "over", "about", "using", "used", "use", "also",
    "environment", "management", "detailed", "notes", "note", "case",
    "cases", "study", "studies", "update", "changes", "change",
}


class CurriculumMatcher:
    """Matches curriculum leaves against the note content in the KB."""

    def __init__(self, kb):
        self.kb = kb
        # Index the KB by note title (lowercased) and by section heading, so a
        # hint can point at either a whole note or one section inside it.
        self.by_title: dict[str, list] = {}
        self.by_heading: dict[str, list] = {}
        for c in kb.chunks:
            self.by_title.setdefault(c.title.lower(), []).append(c)
            h = (c.heading or "").lower().strip()
            if h:
                self.by_heading.setdefault(h, []).append(c)

    def _is_index_note(self, chunks: list) -> bool:
        """True when a note is only a list of links to other notes.

        Some index notes (e.g. "CP1 Opportunities and Risks. Is it rational
        to live.") are four lines of wiki-links and no prose of their own.
        A hint pointing at one of those resolves to nothing usable, so the
        links themselves have to be followed.
        """
        if not chunks:
            return False
        text = "\n".join((c.text or "") for c in chunks).strip()
        if not text:
            return True
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) > 40:
            return False
        # Every line is a bare name, a numbered heading, or a link line.
        for ln in lines:
            s = ln.lstrip("-*").strip()
            if s.startswith("[") and "]" in s:
                s = s.split("]")[-1].strip()
            s = re.sub(r"^\d+(\.\d+)*[.\s]+", "", s).strip()
            if len(s) > 120:
                return False
            if s.endswith(":") or len(s.split()) > 14:
                return False
        return True

    def _linked_titles(self, chunks: list) -> list[str]:
        """The note titles an index note points at."""
        titles = []
        for c in chunks:
            for ln in (c.text or "").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                # "1.2.3 Volcanism" -> "Volcanism"
                s = re.sub(r"^\d+(\.\d+)*[.\s]+", "", ln).strip()
                s = s.lstrip("-*").strip()
                if not s or len(s) > 80:
                    continue
                titles.append(s)
        return titles

    def match_notes(self, hints: list[str]) -> list[dict]:
        """Return every chunk of the notes named by the hints.

        The Notes section uses `match`, which narrows a note down to the
        sections that suit a leaf title. That is right for reading, but
        too narrow for writing: an essay on "Earthquakes" needs the whole
        earthquake note, not the one paragraph whose heading happens to
        share a word with the leaf title.
        """
        found: dict[str, dict] = {}

        def add(c) -> None:
            found[c.doc_id + "#" + str(c.n)] = {
                "title": c.title, "heading": c.heading, "text": c.text,
                "n": c.n, "path": c.path,
            }

        def add_title(hl: str) -> bool:
            """Add the note with this exact (lowercased) title. True if found."""
            chunks = self.by_title.get(hl)
            if not chunks:
                return False
            for c in chunks:
                add(c)
            return True

        def resolve(hl: str, depth: int = 0) -> None:
            if not hl or depth > 3:
                return
            # A hint may name a whole note or a single section.
            if add_title(hl):
                chunks = self.by_title.get(hl, [])
                if self._is_index_note(chunks):
                    # Follow the links: the prose is in the notes they name.
                    for linked in self._linked_titles(chunks):
                        resolve(linked.lower(), depth + 1)
                return
            heading_chunks = self.by_heading.get(hl)
            if heading_chunks:
                for c in heading_chunks:
                    add(c)
                return
            # Fuzzy: the hint may be a shortened form of the note title.
            for title, group in self.by_title.items():
                if hl and (hl in title or title in hl):
                    for c in group:
                        add(c)
                    break
            for head, group in self.by_heading.items():
                if hl and (hl in head or head in hl):
                    for c in group:
                        add(c)

        for hint in hints:
            resolve((hint or "").lower().strip())
        return sorted(found.values(), key=lambda s: (s["title"], s["n"]))

    def match(self, hints: list[str], leaf_title: str = "") -> list[dict]:
        """Find the note content for a leaf.

        A hint is the title of a whole note. Returning every chunk of that
        note for every leaf that mentions it put the same text under dozens
        of headings - 442 distinct chunks were shown 3,450 times.

        So the note is used as the SEARCH POOL, and the leaf title selects
        the relevant sections out of it. A section is kept when it shares a
        meaningful term with the leaf title, or when the leaf title shares
        one with the note's own title. If nothing matches specifically, the
        whole note is returned - broad, but complete, which beats showing
        a student an empty page.
        """
        found: dict[str, dict] = {}

        def add(c) -> None:
            found[c.doc_id + "#" + str(c.n)] = {
                "title": c.title, "heading": c.heading, "text": c.text,
                "n": c.n, "path": c.path,
            }

        leaf_terms = {
            w for w in re.findall(r"[a-z][a-z\-]{3,}", (leaf_title or "").lower())
            if w not in STOPWORDS
        }

        for hint in hints:
            hl = hint.lower().strip()
            if not hl:
                continue
            # A hint may be a note title OR a section heading. Check both:
            # the heading match is more specific, so it wins.
            heading_chunks = self.by_heading.get(hl)
            if heading_chunks:
                for c in heading_chunks:
                    add(c)
                continue

            chunks = self.by_title.get(hl)
            if chunks is None:
                # Neither an exact title nor an exact heading. Try a fuzzy
                # heading match, but only if it resolves to one section.
                fuzzy = {
                    (c.title, c.heading): c
                    for head, group in self.by_heading.items()
                    if hl and (hl in head or head in hl)
                    for c in group
                }
                if len(fuzzy) == 1:
                    add(next(iter(fuzzy.values())))
                continue

            # Pick the sections of this note that are actually about the leaf.
            scored = []
            for c in chunks:
                head_terms = {
                    w for w in re.findall(r"[a-z][a-z\-]{3,}", (c.heading or "").lower())
                    if w not in STOPWORDS
                }
                overlap = leaf_terms & head_terms
                if overlap:
                    scored.append((len(overlap), c))
            if scored:
                best = max(s for s, _ in scored)
                for s, c in scored:
                    if s == best:
                        add(c)
            else:
                # No section heading matched the leaf title. Fall back to the
                # note's own top-level structure: its introduction plus every
                # NUMBERED section (e.g. "2.1 Types of Internal Forces"),
                # because those are the sections a broad leaf like "Plate
                # movement" belongs to. Sub-sections are then skipped, so
                # the leaf shows the note's outline rather than the whole
                # thing.
                numbered = []
                for c in chunks:
                    head = (c.heading or "").strip()
                    if not head:
                        add(c)
                    elif re.match(r"^\d+(\.\d+)*\s+\S", head):
                        depth = head.split()[0].count(".")
                        if depth == 1:
                            numbered.append(c)
                if not numbered:
                    # No numbered structure. Rank the note's sections by how
                    # well they match the leaf title and take the best run of
                    # them, rather than dumping the whole note. If nothing
                    # matches at all, fall back to the note's first few
                    # sections so the page is not empty.
                    note_terms = {
                        w for w in re.findall(r"[a-z][a-z\-]{3,}", hl)
                        if w not in STOPWORDS
                    }
                    best_n = 0
                    for c in chunks:
                        head_terms = {
                            w for w in re.findall(r"[a-z][a-z\-]{3,}", (c.heading or "").lower())
                            if w not in STOPWORDS
                        }
                        s = len(leaf_terms & head_terms) + len(note_terms & head_terms)
                        best_n = max(best_n, s)
                    if best_n:
                        # Take the SECTION that matches - every chunk sharing
                        # that heading - plus the note's untitled intro.
                        # Walking from the match to the end of the note
                        # pulled in 31KB of unrelated material.
                        matched = None
                        for c in chunks:
                            head_terms = {
                                w for w in re.findall(r"[a-z][a-z\-]{3,}", (c.heading or "").lower())
                                if w not in STOPWORDS
                            }
                            s = len(leaf_terms & head_terms) + len(note_terms & head_terms)
                            if s >= best_n:
                                matched = c
                                break
                        if matched is not None:
                            target = (matched.heading or "").strip().lower()
                            for c in chunks:
                                head = (c.heading or "").strip().lower()
                                if not head or head == target:
                                    add(c)
                    else:
                        for c in chunks[:6]:
                            add(c)
                else:
                    # Take every TOP-LEVEL numbered section and everything
                    # under it. A leaf like "Plate movement" may belong to
                    # more than one top-level section, and showing only the
                    # first would misplace it.
                    starts = [c.n for c in numbered]
                    ends = starts[1:] + [None]
                    for start, end in zip(starts, ends):
                        for c in chunks:
                            if start <= c.n and (end is None or c.n < end):
                                add(c)
        return sorted(found.values(), key=lambda s: (s["title"], s["n"]))
