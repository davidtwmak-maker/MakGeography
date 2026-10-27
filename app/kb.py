"""
Retrieval over the MakGeography knowledge base.

Pure-python BM25 — no sklearn dependency, and it handles the Hong Kong
geography vocabulary (mixed English terms, place names) better than a
generic vector store would at this corpus size.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

# HK / geography-specific expansions: a student asking "tsunami" should
# also retrieve notes that say "seismic sea wave" and vice versa.
SYNONYMS = {
    "tsunami": ["tsunami", "seismic sea wave", "seiche"],
    "earthquake": ["earthquake", "seismic", "epicentre", "epicenter", "magnitude", "seismograph"],
    "volcano": ["volcano", "volcanism", "eruption", "lava", "magma", "vent", "crater"],
    "plate": ["plate", "tectonic", "boundary", "convergence", "divergence", "subduction"],
    "coast": ["coast", "coastal", "shoreline", "beach", "erosion", "longshore"],
    "river": ["river", "fluvial", "channel", "catchment", "drainage", "flood"],
    "industry": ["industry", "industrial", "manufacturing", "factory", "location factor"],
    "famine": ["famine", "hunger", "food insecurity", "malnutrition", "starvation"],
    "canopy": ["canopy", "forest", "deforestation", "rainforest", "tree cover"],
    "warming": ["warming", "climate", "greenhouse", "temperature", "emission"],
    "sustainable": ["sustainable", "sustainability", "urban", "city", "planning"],
    "hk": ["hong kong", "hk", "kowloon", "new territories", "hkis"],
    "f6": ["f6", "revision", "form 6"],
    "cp3": ["cp3", "industrial location", "silicon valley", "china"],
    "ep1": ["ep1", "dynamic earth", "rock", "weathering", "mass movement"],
    "dbq": ["dbq", "data question", "structured"],
}

# Words that carry no retrieval signal.
STOPWORDS = set(
    """a an the and or but if then than that this these those is are was were be been being
    of in on at to for with by from as it its into over under about what which who whom
    how why when where explain describe discuss account evaluate analyse analyze compare
    difference between give state mention identify list outline define clarify distinguish
    i you we they he she me my your our their it do does did can could should would may
    might must will shall not no nor so such very more most less least much many few some
    any each other another own same too also just only please help thanks thank hi hello
    question answer exam mark marks study revise revision note notes content summary
    """.split()
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, drop stopwords. Keep CJK as individual chars."""
    toks: list[str] = []
    for m in _TOKEN_RE.finditer(text.lower()):
        t = m.group(0).strip("'-")
        if t and t not in STOPWORDS and len(t) > 1:
            toks.append(t)
    # CJK: each character is a token (adequate for short Chinese queries)
    for ch in text:
        if "一" <= ch <= "鿿":
            toks.append(ch)
    return toks


def expand(tokens: list[str]) -> list[str]:
    """Add synonym variants so a query hits notes that use the other term."""
    out = list(tokens)
    joined = " ".join(tokens)
    for key, variants in SYNONYMS.items():
        if any(v in joined for v in variants):
            out.extend(variants)
    return out


class Chunk:
    __slots__ = ("text", "heading", "n", "doc_id", "title", "topic", "path")

    def __init__(self, text, heading, n, doc_id, title, topic, path):
        self.text = text
        self.heading = heading
        self.n = n
        self.doc_id = doc_id
        self.title = title
        self.topic = topic
        self.path = path

    @property
    def cite(self) -> str:
        return f"{self.title}" + (f" — {self.heading}" if self.heading else "")


class KnowledgeBase:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.meta = raw.get("meta", {})
        self.chunks: list[Chunk] = []
        for d in raw.get("docs", []):
            for c in d.get("chunks", []):
                self.chunks.append(
                    Chunk(
                        text=c["text"],
                        heading=c.get("heading", ""),
                        n=c.get("n", 0),
                        doc_id=d["id"],
                        title=d["title"],
                        topic=d.get("topic", "General"),
                        path=d.get("path", ""),
                    )
                )
        self._build_index()

    def _build_index(self):
        self.docs_tokens: list[list[str]] = []
        self.tf: list[Counter] = []
        df: Counter = Counter()
        for ch in self.chunks:
            toks = tokenize(ch.text)
            # Title and heading count toward the document's term frequency:
            # a chunk whose heading is "Silicon Valley" is a better hit for
            # "silicon valley" than a chunk that merely mentions it once.
            weighted = toks + tokenize(ch.heading) * 3 + tokenize(ch.title) * 2
            self.docs_tokens.append(weighted)
            c = Counter(weighted)
            self.tf.append(c)
            df.update(c.keys())
        self.df = df
        self.N = max(1, len(self.chunks))
        self.avgdl = sum(len(t) for t in self.docs_tokens) / self.N
        self.idf = {
            t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()
        }

    def search(self, query: str, k: int = 8, topic: str | None = None) -> list[tuple[Chunk, float]]:
        qtok = expand(tokenize(query))
        if not qtok:
            return []
        qcount = Counter(qtok)
        scores: list[tuple[int, float]] = []
        for i, chunk in enumerate(self.chunks):
            tf = self.tf[i]
            dl = len(self.docs_tokens[i]) or 1
            s = 0.0
            for term, qn in qcount.items():
                f = tf.get(term)
                if not f:
                    continue
                idf = self.idf.get(term, 0.0)
                # BM25 with k1=1.5, b=0.75
                denom = f + 1.5 * (1 - 0.75 + 0.75 * dl / self.avgdl)
                s += idf * (f * 2.2) / denom * min(qn, 3)
            # exact phrase bonus — big signal for geography terminology
            ql = query.lower().strip()
            if len(ql) > 3 and ql in chunk.text.lower():
                s += 4.0
            # topic filter / boost
            if topic and topic.upper() != "ALL":
                if chunk.topic.upper() == topic.upper():
                    s *= 1.6
                elif chunk.topic.upper() != "GENERAL":
                    s *= 0.55
            if s > 0:
                scores.append((i, s))
        scores.sort(key=lambda x: -x[1])
        out = []
        for i, s in scores[: k * 3]:
            out.append((self.chunks[i], s))
            if len(out) >= k:
                break
        return out

    def get_doc(self, doc_id: str) -> list[Chunk]:
        return [c for c in self.chunks if c.doc_id == doc_id]

    @property
    def topics(self) -> list[str]:
        return sorted({c.topic for c in self.chunks if c.topic != "General"})

    def topic_index(self) -> dict:
        """topic -> list of chunks (for the Notes section)."""
        idx: dict[str, list[Chunk]] = {}
        for c in self.chunks:
            idx.setdefault(c.topic, []).append(c)
        return idx
