"""Keyword retrieval (BM25) over the items that were moved out of view, for the RAG arms (2026-10-11).

Why: the owner asked how the keeper differs from "a RAG that we just add all context to". Arm R32 answers that with
a measurement: the plain sliding-window agent, whose cut items go to a store, and at every question the harness
retrieves the best-matching passages from the store and shows them. No notes, no pinned rules, no search tool.

The retriever is plain Okapi BM25 (k1 1.5, b 0.75) over sentences, each indexed together with its item number
("item 21 ..."), so a question that names an item finds that item's sentences. Keyword retrieval is the favourable
retriever for this stream: the things asked about are exact strings (counter names such as `voka16`), which an
embedding model matches worse than an exact-term index does. Stdlib only; used by clm_keeper.KeeperAgent
(auto_retrieve) and by rag_coverage.py (what retrieval can reach, measured without a GPU).
"""
from __future__ import annotations

import math
import re

STOP = frozenset("""a an the of in on at to for by is are was were be been it its this that these those and or as with
from what which who whom when where how do does did has have had now then than so if not no any all each every you your
i we they he she his her their our my me us them there here about into over under after before""".split())
ASK_LINE = re.compile(r"(?m)^(?:ASK (\S+?):\s*(.+)|(?:QUERY|GET) (\S+))\s*$")


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", " ".join(text.split())) if s]


def paragraphs(text: str) -> list[str]:
    return [" ".join(p.split()) for p in text.split("\n\n") if p.strip()]


def terms(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


def questions(tool_text: str) -> list[tuple[str, str]]:
    """(key, question text) for every question line of a delivered item: `ASK key: text`, `QUERY name`, `GET name`."""
    return [(m.group(1) or m.group(3), m.group(2) or m.group(3)) for m in ASK_LINE.finditer(tool_text)]


class Index:
    """BM25 over passages (sentences, or paragraphs with unit='paragraph') of the items added so far."""

    def __init__(self, unit: str = "sentence", k1: float = 1.5, b: float = 0.75) -> None:
        if unit not in ("sentence", "paragraph"):
            raise ValueError(f"unit must be sentence|paragraph, not {unit!r}")
        self.unit, self.k1, self.b = unit, k1, b
        self.docs: list[tuple[int, str]] = []            # (item number, passage)
        self.size: list[int] = []
        self.post: dict[str, dict[int, int]] = {}        # term -> {passage id: count}
        self.total = 0
        self.items: set[int] = set()

    def add(self, num: int, text: str) -> int:
        """Index one item (once); returns the number of passages added."""
        if num in self.items:
            return 0
        self.items.add(num)
        parts = sentences(text) if self.unit == "sentence" else paragraphs(text)
        for p in parts:
            i, tt = len(self.docs), terms(f"item {num} {p}")
            self.docs.append((num, p))
            self.size.append(len(tt))
            self.total += len(tt)
            for t in tt:
                d = self.post.setdefault(t, {})
                d[i] = d.get(i, 0) + 1
        return len(parts)

    def search(self, query: str, k: int = 20, floor: float = 0.0) -> list[tuple[float, int, str, int]]:
        """Up to k passages as (score, item number, passage, position in the store), best first; ties go to the later
        passage. `floor` drops passages scoring under that fraction of the best one."""
        n = len(self.docs)
        if not n:
            return []
        avg, score = self.total / n, {}
        for t in set(terms(query)):
            d = self.post.get(t)
            if not d:
                continue
            idf = math.log(1 + (n - len(d) + 0.5) / (len(d) + 0.5))
            for i, tf in d.items():
                score[i] = score.get(i, 0.0) + idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.size[i] / avg))
        best = sorted(score.items(), key=lambda kv: (-kv[1], -kv[0]))[:k]
        if best and floor:
            best = [kv for kv in best if kv[1] >= floor * best[0][1]]
        return [(s, self.docs[i][0], self.docs[i][1], i) for i, s in best]


RETRIEVED_HEAD = ("[[Retrieved for the questions above from the turns that were moved out of view: the best-matching "
                  "passages, at most {k} per question, in item order. The store may hold more than is shown.]]")


def retrieval_note(index: Index, tool_text: str, k: int = 20, floor: float = 0.0, max_chars: int = 600,
                   budget_chars: int = 0, window: int = 0) -> str:
    """The message shown after a question item ('' if it asks nothing or the store is empty). With budget_chars,
    the weakest match of the question that has the most matches is dropped until the whole rendered message fits
    (a question whose matches were all dropped says so; if even the bare list does not fit, '' is returned). With
    window=N a matching sentence is shown together with the N sentences that follow it in the same item
    ("sentence-window" retrieval, for text that names a thing in one sentence and says what happened in the next)."""
    asked = questions(tool_text)
    if not asked or not index.docs:
        return ""

    def shown(num: int, pos: int) -> str:
        more = [index.docs[j][1] for j in range(pos + 1, min(pos + 1 + window, len(index.docs))) if index.docs[j][0] == num]
        return f"item {num}: " + " ".join(p[:max_chars] for p in [index.docs[pos][1]] + more)

    hits = [index.search(q, k, floor) for _, q in asked]            # best first
    found = [bool(h) for h in hits]

    def render() -> str:
        out = []
        for (key, _), h, any_hit in zip(asked, hits, found):
            out.append(f"{key}:" if h else f"{key}: (matches left out for space)" if any_hit else f"{key}: (nothing in the store matches)")
            out += [shown(num, i) for _, num, _, i in sorted(h, key=lambda x: (x[1], x[3]))]   # reading order
        return RETRIEVED_HEAD.format(k=k) + "\n" + "\n".join(out)

    text = render()
    while budget_chars and len(text) > budget_chars:
        if not any(hits):
            return ""
        max(hits, key=len).pop()
        text = render()
    return text
