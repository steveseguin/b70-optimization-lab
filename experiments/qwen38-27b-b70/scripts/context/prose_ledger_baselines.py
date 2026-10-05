#!/usr/bin/env python3
"""Difficulty evidence for the prose ledger (CPU only, no model).

Two scripted readers are scored on generated tasks, exactly as the grader scores the model
(fraction of the 24 queried counters exactly right; null for removed counters):

  regex      a keyword/regex parser of honest effort, kept to what a model could plausibly write in
             one turn after seeing the instructions and one batch (about 80 lines, function
             `regex_reader`): sentence split, name and pronoun/ordinal resolution, number words,
             keyword lists per operation, skips hypotheticals/negations/recollections, holds plans
             until a confirming or cancelling sentence.
  lastnum    the trivial heuristic: the last number written in a sentence that names the counter.

The task is meant to require reading: both should stay clearly below 60 % at 120K.

  prose_ledger_baselines.py TASK_DIR [TASK_DIR ...]      (task dirs from make_prose_ledger_tasks.py)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

NAME = re.compile(r"\b[a-z]+\d\d\b")
W = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                 "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
W.update({w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if i > 1})


def numbers(s: str) -> list[int]:
    """Digits and number words, in order of appearance."""
    out, toks = [], re.findall(r"-?\d+|[a-z]+(?:-[a-z]+)?", s.lower())
    i = 0
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"-?\d+", t):
            out.append(int(t)); i += 1; continue
        neg, val, used = False, 0, False
        if t == "minus" and i + 1 < len(toks):
            neg, i = True, i + 1
        while i < len(toks):
            p = toks[i].split("-")
            if all(x in W for x in p):
                val += sum(W[x] for x in p); used = True; i += 1
            elif toks[i] == "hundred" and used:
                val *= 100; i += 1
            elif toks[i] == "thousand" and used:
                val *= 1000; i += 1
            elif toks[i] == "and" and used and i + 1 < len(toks) and toks[i + 1].split("-")[0] in W:
                i += 1
            else:
                break
        if used:
            out.append(-val if neg else val)
        else:
            i += 1
    return out


def regex_reader(text: str, st: dict) -> None:
    for para in text.split("\n\n"):
        intro, last, plan = [], None, None
        for s in re.split(r"(?<=\.)\s+", para):
            names = NAME.findall(s)
            for n in names:
                if n not in intro: intro.append(n)
            low = s.lower()
            if re.search(r"would|\bnot\b|nobody|no one|recalled|remember|supplier list", low):
                continue
            if re.search(r"talk of|plans were made|proposal", low):
                plan = (names[0] if names else last, low); continue
            if plan and re.search(r"went through|carried out|was done", low):
                tgt, low, names = plan[0], plan[1], [plan[0]]
                plan = None
            elif plan and re.search(r"dropped|abandoned|nothing came", low):
                plan = None; continue
            else:
                tgt = names[0] if names else None
            if tgt is None:
                m = re.search(r"\b(former|latter|first|second|third)\b", low)
                if m:
                    k = {"former": 0, "first": 0, "latter": 1, "second": 1, "third": 2}[m.group(1)]
                    tgt = intro[k] if k < len(intro) else None
                elif "before the audit" in low: tgt = intro[0] if intro else None
                elif "after the audit" in low: tgt = intro[1] if len(intro) > 1 else None
                elif re.search(r"\bit\b|same counter", low): tgt = last
            if tgt is None: continue
            nums = numbers(re.sub(NAME, " ", s))
            if re.search(r"typo|correction", low):
                if nums: st[tgt] = nums[0] if "should have read" in low or "it was" in low else nums[-1]
            elif re.search(r"as many as|equal to|exactly what", low):
                other = [n for n in names if n != tgt]
                if other and tgt in st: st[tgt] += st.get(other[0], 0)
            elif re.search(r"set to|reset to|put .* at|recorded .* at|stands at|fixed at|brought to|opened|"
                           r"started for|came back|entered fresh|planned change|plan for|was planned", low) and nums:
                if "talk of setting" in low or "setting" in low or not re.search(r"add|take", low):
                    st[tgt] = nums[-1]
                elif "add" in low: st[tgt] = st.get(tgt, 0) + nums[-1]
                else: st[tgt] = st.get(tgt, 0) - nums[-1]
            elif re.search(r"removed|struck off|no longer|retired|taken off", low): st.pop(tgt, None)
            elif re.search(r"doubled|twice", low): st[tgt] = st.get(tgt, 0) * 2
            elif "third" in low and tgt in st: st[tgt] -= st[tgt] // 3
            elif re.search(r"gained|up by|added|rose|received|picked up|went up", low) and nums:
                st[tgt] = st.get(tgt, 0) + nums[-1]
            elif re.search(r"lost|dropped|taken from|fell|gave up|short|went down", low) and nums:
                st[tgt] = st.get(tgt, 0) - nums[-1]
            last = tgt


def lastnum_reader(text: str, st: dict) -> None:
    for s in re.split(r"(?<=\.)\s+", text):
        nums = numbers(re.sub(NAME, " ", s))
        for n in NAME.findall(s):
            if nums:
                st[n] = nums[-1]


def score(task: Path) -> dict:
    items = [json.loads(l) for l in (task / "environment" / "stream.jsonl").read_text().splitlines()]
    exp = json.loads((task / "tests" / "expected.json").read_text())
    out = {}
    for name, fn in (("regex", regex_reader), ("lastnum", lastnum_reader)):
        st: dict = {}
        for it in items[:-1]:
            fn(it["text"], st)
        out[name] = sum(1 for k, v in exp.items() if st.get(k) == v) / len(exp)
    return out


def main() -> None:
    for t in sys.argv[1:]:
        print(Path(t).name, json.dumps(score(Path(t))))


if __name__ == "__main__":
    main()
