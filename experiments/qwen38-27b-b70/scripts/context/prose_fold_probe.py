#!/usr/bin/env python3
"""Can the model read a prose-ledger batch at all? A single-call probe, no agent harness.

Works on dense prose-ledger tasks (make_prose_ledger_tasks.py) and sparse ones
(make_sparse_prose_tasks.py). For every batch, one chat request gives the
model the TRUE state before the batch (from tests/reference.json, so errors do not compound) and the
batch text, and asks for the counters the batch changed. The reply is applied to the true previous
state and compared with the reference state after the batch.

Per batch it prints: counters the batch really changed, how many of them the model got exactly
right, wrong extra changes (counters it changed that the batch did not change), all-counter
accuracy, tokens written, seconds. At the end: totals and averages.

  API_BASE=http://127.0.0.1:18124/v1 MODEL_NAME=qwen38-27b-fp8 \\
    prose_fold_probe.py TASK_DIR [TASK_DIR ...] [--thinking on|off|both] [--variant plain|reason|both]
                        [--limit N] [--start K] [--max-tokens N] [--think-cap N] [--sweep] [--dry-run]
  --variant reason   thinking off, but each output line carries a short `# reason` (often helps
                     without unbounded reasoning); plain = values only
  --think-cap N      thinking on with max_tokens N (measured: thinking at 16K hit the cap on every
                     6.4K/2K prose call; kept only for completeness)
  --sweep            one summary line per task dir and setting (for calibrate-reading.sh)
"parseable" = the reply ended normally and every non-empty line is `name value` (optionally with
`# reason`); unparseable lines are ignored for scoring but counted.

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
  nothing; a plan changes the counter only when a later sentence says it went through (or ahead);
- ordinary narrative that does not mention a counter by name or by "it"/"that counter" changes nothing;
- "it", "the former", "the latter", "the second of these", "the counter named before the audit"
  each refer to exactly one counter of the same paragraph; numbers may be written in words.
Output ONLY the counters whose value is different after the report than before it (including
counters that were opened), one per line as `name value`, and `name REMOVED` for a counter removed
from the ledger (and not opened again later in the report). No other text."""

REASON = """
Format: one line per changed counter, `name value  # reason`, where the reason is a few words quoting
or naming the sentence(s) that decide it (for example `# set to 40, corrected from 14`). No other text."""

LINE = re.compile(r"^\s*([a-z]+\d\d)\s*[:=]?\s*(-?\d+|REMOVED|removed|null|None|DELETED)\s*(?:#.*)?$")


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


def parse(text: str) -> tuple[dict, bool]:
    out, ok = {}, True
    for ln in (text or "").splitlines():
        if not ln.strip():
            continue
        m = LINE.match(ln)
        if m:
            v = m.group(2)
            out[m.group(1)] = None if not re.fullmatch(r"-?\d+", v) else int(v)
        else:
            ok = False
    return out, ok


def load_task(task: Path):
    items = [json.loads(l) for l in (task / "environment" / "stream.jsonl").read_text().splitlines()]
    ref = json.loads((task / "tests" / "reference.json").read_text())["after_batch"]
    return items, ref


def changed_set(prev: dict, truth: dict) -> set:
    return {k for k in set(prev) | set(truth) if prev.get(k) != truth.get(k)}


def estimate(task: Path, batches, thinking: bool, variant: str, think_cap: int) -> tuple[float, float, float]:
    items, ref = load_task(task)
    est_in = sum(450 + 6 * len(ref[b - 1]["state"] if b else {}) + len(items[b]["text"]) / 3.9 for b in batches)
    nch = sum(len(changed_set(ref[b - 1]["state"] if b else {}, ref[b]["state"])) for b in batches)
    per = 9 + (12 if variant == "reason" else 0)
    out = per * nch + (think_cap or 6000) * len(batches) * (1 if thinking else 0)
    return est_in, out, est_in / 2500 + out / 85


def run(task: Path, base: str, model: str, batches, thinking: bool, variant: str, max_tokens: int,
        verbose: bool) -> dict:
    items, ref = load_task(task)
    system = SYSTEM + (REASON if variant == "reason" else "")
    tot = {"changed": 0, "right": 0, "extra": 0, "all_right": 0, "all": 0, "written": 0, "sec": 0.0,
           "cut": 0, "parseable": 0, "calls": 0, "batches_perfect": 0}
    if verbose:
        print(f"\n== {task.name} thinking={'on' if thinking else 'off'} variant={variant} max_tokens={max_tokens}")
        print("batch\tchanged\tright\textra_wrong\tall_acc\twritten\tsec\tfinish\tparseable")
    for b in batches:
        prev = ref[b - 1]["state"] if b else {}
        truth = ref[b]["state"]
        state_txt = "\n".join(f"{k} {v}" for k, v in sorted(prev.items())) or "(empty: no counters yet)"
        user = f"Current state ({len(prev)} counters):\n{state_txt}\n\nReport:\n{items[b]['text']}"
        try:
            d = chat(base, model, system, user, thinking, max_tokens)
        except Exception as e:
            print(f"{b + 1}\tERROR {type(e).__name__}: {e}")
            continue
        ch = d["choices"][0]
        got, ok = parse(ch["message"].get("content") or "")
        cut = ch.get("finish_reason") == "length"
        ok = ok and not cut and bool(got or not changed_set(prev, truth))
        new = dict(prev)
        for k, v in got.items():
            if v is None:
                new.pop(k, None)
            else:
                new[k] = v
        changed = changed_set(prev, truth)
        right = sum(1 for k in changed if new.get(k) == truth.get(k))
        extra = sum(1 for k in set(new) | set(truth) if k not in changed and new.get(k) != truth.get(k))
        allk = set(new) | set(truth)
        all_right = sum(1 for k in allk if new.get(k) == truth.get(k))
        w = (d.get("usage") or {}).get("completion_tokens", 0)
        for k, v in (("changed", len(changed)), ("right", right), ("extra", extra), ("all_right", all_right),
                     ("all", len(allk)), ("written", w), ("sec", d["_seconds"]), ("cut", int(cut)),
                     ("parseable", int(ok)), ("calls", 1), ("batches_perfect", int(all_right == len(allk)))):
            tot[k] += v
        if verbose:
            print(f"{b + 1}\t{len(changed)}\t{right}\t{extra}\t{all_right}/{len(allk)}\t{w}\t{d['_seconds']:.0f}\t"
                  f"{ch.get('finish_reason')}\t{'yes' if ok else 'NO'}")
            sys.stdout.flush()
    return tot


def summary(task: Path, thinking: bool, variant: str, t: dict) -> str:
    md = {}
    try:
        import tomllib
        md = tomllib.loads((task / "task.toml").read_text()).get("metadata", {})
    except Exception:
        pass
    ch = t["right"] / t["changed"] if t["changed"] else float("nan")
    full = t["all_right"] / t["all"] if t["all"] else float("nan")
    return (f"{task.parent.name}/{task.name}\tsetting={md.get('setting', '?')}\tdensity={md.get('density', '?')}\t"
            f"thinking={'on' if thinking else 'off'}\tvariant={variant}\tchanged_right={t['right']}/{t['changed']} "
            f"({ch:.1%})\tfull_table={full:.2%}\tperfect_batches={t['batches_perfect']}/{t['calls']}\t"
            f"wrong_extra={t['extra']}\tparseable={t['parseable']}/{t['calls']}\tcut={t['cut']}\t"
            f"written={t['written']}\tmin={t['sec'] / 60:.1f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--thinking", choices=["on", "off", "both"], default="off")
    ap.add_argument("--variant", choices=["plain", "reason", "both"], default="plain")
    ap.add_argument("--limit", type=int, default=0, help="number of batches (0 = all)")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=0, help="default 4096 without thinking, 16384 with")
    ap.add_argument("--think-cap", type=int, default=0, help="thinking on with this max_tokens")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    modes = {"on": [True], "off": [False], "both": [False, True]}[a.thinking]
    if a.think_cap:
        modes = [True]
    variants = {"plain": ["plain"], "reason": ["reason"], "both": ["plain", "reason"]}[a.variant]
    tasks = [Path(t) for t in a.tasks]
    plan = []
    for t in tasks:
        _, ref = load_task(t)
        bs = list(range(a.start, len(ref)))
        if a.limit:
            bs = bs[:a.limit]
        for th in modes:
            for v in variants:
                plan.append((t, bs, th, v))
    tin = tout = tsec = 0.0
    for t, bs, th, v in plan:
        i, o, s_ = estimate(t, bs, th, v, a.think_cap)
        tin, tout, tsec = tin + i, tout + o, tsec + s_
    print(f"# estimate: {sum(len(p[1]) for p in plan)} calls, ~{tin / 1e3:.0f}K prompt tokens, ~{tout / 1e3:.0f}K written, "
          f"~{tsec / 60:.1f} min (reading 2,500 tok/s, writing 85 tok/s; thinking output is a guess)")
    if a.dry_run:
        return
    base = os.environ.get("API_BASE") or sys.exit("set API_BASE")
    model = os.environ.get("MODEL_NAME", "qwen38-27b-fp8")
    lines = []
    for t, bs, th, v in plan:
        mt = a.think_cap or a.max_tokens or (16384 if th else 4096)
        tot = run(t, base, model, bs, th, v, mt, verbose=not a.sweep)
        line = summary(t, th, v, tot)
        lines.append(line)
        print(("# " if not a.sweep else "") + line)
        sys.stdout.flush()
    if a.sweep:
        print("\n# summary")
        for line in lines:
            print(line)


if __name__ == "__main__":
    main()
