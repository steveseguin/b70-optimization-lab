#!/usr/bin/env python3
"""Can the model read a prose-ledger batch at all? A single-call probe, no agent harness.

For every batch of a prose-ledger task (make_prose_ledger_tasks.py), one chat request gives the
model the TRUE state before the batch (from tests/reference.json, so errors do not compound) and the
batch text, and asks for the counters the batch changed. The reply is applied to the true previous
state and compared with the reference state after the batch.

Per batch it prints: counters the batch really changed, how many of them the model got exactly
right, wrong extra changes (counters it changed that the batch did not change), all-counter
accuracy, tokens written, seconds. At the end: totals and averages.

  API_BASE=http://127.0.0.1:18124/v1 MODEL_NAME=qwen38-27b-fp8 \\
    prose_fold_probe.py TASK_DIR [--thinking on|off|both] [--limit N] [--start K] [--max-tokens N]

TASK_DIR is a generated prose task, e.g. .../tasks/prose-memory/prose-memory-t120k-s0 (6.4K-token
batches). For 2K-token batches generate a small variant first (CPU, seconds):
  make_prose_ledger_tasks.py /tmp/prose2k --tokens 40000 --batch-tokens 2000 --seeds 0 --mode memory
and probe /tmp/prose2k/prose-memory-t40k-s0. --dry-run prints the cost estimate only.
Standard library only (urllib); no tokenizer.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

SYSTEM = """You keep a ledger of named integer counters. You are given the current state of the ledger
and a narrative report. Apply the report exactly:
- a counter can be set to a value, opened (new or removed counter) at a value, increased, decreased,
  doubled, reduced by a third, increased by as much as another counter holds at that moment, or
  removed from the ledger;
- a correction of a figure stated earlier ("the figure given for X above was a typo: it should have
  read 40, not 14") replaces that figure;
- statements about what would have happened, what did not happen, rumours or forecasts, plans that
  were abandoned, values recalled from the past, and names said not to be part of the ledger change
  nothing; a plan changes the counter only when a later sentence says it went through;
- "it", "the former", "the latter", "the second of these", "the counter named before the audit"
  each refer to exactly one counter of the same paragraph; numbers may be written in words.
Output ONLY the counters whose value is different after the report than before it (including
counters that were opened), one per line as `name value`, and `name REMOVED` for a counter removed
from the ledger (and not opened again later in the report). No other text."""

LINE = re.compile(r"^\s*([a-z]+\d\d)\s*[:=]?\s*(-?\d+|REMOVED|removed|null|None|DELETED)\s*$")


def chat(base: str, model: str, system: str, user: str, thinking: bool, max_tokens: int) -> dict:
    body = {"model": model, "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}],
            "temperature": 0, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking}}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.load(r)
    d["_seconds"] = time.time() - t0
    return d


def parse(text: str) -> dict:
    out = {}
    for ln in (text or "").splitlines():
        m = LINE.match(ln)
        if m:
            v = m.group(2)
            out[m.group(1)] = None if not re.fullmatch(r"-?\d+", v) else int(v)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task")
    ap.add_argument("--thinking", choices=["on", "off", "both"], default="both")
    ap.add_argument("--limit", type=int, default=0, help="number of batches (0 = all)")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=0, help="default 16384 with thinking, 4096 without")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    task = Path(a.task)
    items = [json.loads(l) for l in (task / "environment" / "stream.jsonl").read_text().splitlines()]
    ref = json.loads((task / "tests" / "reference.json").read_text())["after_batch"]
    batches = list(range(a.start, len(ref)))
    if a.limit:
        batches = batches[:a.limit]
    modes = {"on": [True], "off": [False], "both": [False, True]}[a.thinking]
    # cost estimate: prompt = system + state (~6 tokens/counter) + batch (chars/3.9)
    est_in = sum(400 + 6 * len(ref[b - 1]["state"] if b else {}) + len(items[b]["text"]) / 3.9 for b in batches)
    n_changed = sum(len({k for k in set(ref[b - 1]["state"] if b else {}) | set(ref[b]["state"])
                         if (ref[b - 1]["state"] if b else {}).get(k) != ref[b]["state"].get(k)}) for b in batches)
    est_out = {False: 9 * n_changed, True: 9 * n_changed + 6000 * len(batches)}   # ~9 tokens per "name value" line
    for th in modes:
        sec = est_in / 2000 + est_out[th] / (85 if not th else 80)
        print(f"# estimate thinking={'on' if th else 'off'}: {len(batches)} calls, ~{est_in/1e3:.0f}K prompt tokens, "
              f"~{est_out[th]/1e3:.0f}K written, ~{sec/60:.1f} min (written tokens with thinking are a guess)")
    if a.dry_run:
        return
    base = os.environ.get("API_BASE") or sys.exit("set API_BASE")
    model = os.environ.get("MODEL_NAME", "qwen38-27b-fp8")
    for th in modes:
        mt = a.max_tokens or (16384 if th else 4096)
        tot = {"changed": 0, "right": 0, "extra": 0, "all_right": 0, "all": 0, "written": 0, "sec": 0.0, "cut": 0}
        print(f"\n== thinking={'on' if th else 'off'} max_tokens={mt}")
        print("batch\tchanged\tright\textra_wrong\tall_acc\twritten\tsec\tfinish")
        for b in batches:
            prev = ref[b - 1]["state"] if b else {}
            truth = ref[b]["state"]
            state_txt = "\n".join(f"{k} {v}" for k, v in sorted(prev.items())) or "(empty: no counters yet)"
            user = f"Current state ({len(prev)} counters):\n{state_txt}\n\nReport:\n{items[b]['text']}"
            try:
                d = chat(base, model, SYSTEM, user, th, mt)
            except Exception as e:
                print(f"{b + 1}\tERROR {type(e).__name__}: {e}")
                continue
            ch = d["choices"][0]
            got = parse(ch["message"].get("content") or "")
            new = dict(prev)
            for k, v in got.items():
                if v is None:
                    new.pop(k, None)
                else:
                    new[k] = v
            changed = {k for k in set(prev) | set(truth) if prev.get(k) != truth.get(k)}
            right = sum(1 for k in changed if new.get(k) == truth.get(k))
            extra = sum(1 for k in set(new) | set(truth) if k not in changed and new.get(k) != truth.get(k))
            allk = set(new) | set(truth)
            all_right = sum(1 for k in allk if new.get(k) == truth.get(k))
            w = (d.get("usage") or {}).get("completion_tokens", 0)
            cut = ch.get("finish_reason") == "length"
            for k, v in (("changed", len(changed)), ("right", right), ("extra", extra), ("all_right", all_right),
                         ("all", len(allk)), ("written", w), ("sec", d["_seconds"]), ("cut", int(cut))):
                tot[k] += v
            print(f"{b + 1}\t{len(changed)}\t{right}\t{extra}\t{all_right}/{len(allk)}\t{w}\t{d['_seconds']:.0f}\t"
                  f"{ch.get('finish_reason')}")
            sys.stdout.flush()
        if tot["changed"]:
            print(f"# thinking={'on' if th else 'off'}: changed counters right {tot['right']}/{tot['changed']} "
                  f"({tot['right']/tot['changed']:.1%}), wrong extra changes {tot['extra']}, all-counter accuracy "
                  f"{tot['all_right']/max(tot['all'],1):.1%}, written {tot['written']:,} tokens, "
                  f"{tot['sec']/60:.1f} min, cut at max_tokens {tot['cut']}")


if __name__ == "__main__":
    main()
