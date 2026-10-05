#!/usr/bin/env python3
"""Generate "ledger" Harbor tasks: a running ledger of named counters (surgical-update test).

Second task of the self-editing comparison (notes/2026-10-05-self-editing-first-comparison.md).
Unlike kvstream (a lookup table where any of thousands of values may be asked), here the
state that matters is SMALL and changes all the time: about 160 integer counters receive
SET / ADD / DEL updates, batch after batch. Each update line also carries a 16-word memo that
never affects any counter (noise that can be dropped without loss). The final item asks for
the current value of 24 counters (a few of them deleted at the end). So an agent that keeps a
current-state table in its context and replaces stale entries (the paper's "surgical update")
can be lossless at a small budget, while one that keeps the raw stream needs the whole stream.

Item format (one update per line, applied in stream order):
  SET <counter> <int>   | memo: <16 words>     set (creates the counter if new / deleted)
  ADD <counter> <int>   | memo: <16 words>     add a non-zero integer (may be negative)
  DEL <counter>         | memo: <16 words>     delete; a later SET creates it again
ADD never targets a counter that does not exist at that point.

Answer: /app/answers.json {counter: current integer, or null if deleted at the end}.
Grading (tests/grade.py, shared with kvstream v2): exact integer match; per counter
correct / blank / stale (an earlier value of that counter) / wrong; the same memory-only
storage rule as kvstream (a file other than answers.json and the harness mirror that names
3 or more counters voids the run) and the same `next` delivery log.

Usage:
  make_ledger_tasks.py OUT_DIR --tokens 60000 120000 180000 --mode memory|notes [--seeds 0 1]
  make_ledger_tasks.py OUT_DIR --smoke [--mode memory]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from make_kvstream_tasks import (DEFAULT_TOKENIZER, STORAGE_MEMORY, STORAGE_NOTES, TokenCounter,
                                 word, write_task)

INSTRUCTION = """\
You are connected to a ledger stream. Run the command `next` to receive the next item of the
stream. There are {total} items: {n_batches} batch(es) of {batch_size} counter updates (one
batch is about {batch_tokens:,} tokens), then one final item that lists {n_get} counters to
report. The whole stream is about {stream_tokens:,} tokens and touches {n_counters} counters.

Update lines, applied in stream order:
  SET <counter> <integer>   sets the counter (creates it if it does not exist)
  ADD <counter> <integer>   adds the integer (it may be negative) to the counter
  DEL <counter>             deletes the counter; a later SET creates it again
Every line ends with `| memo: ...`. Memos never change any counter.

Rules:
- Each item is printed once and then deleted; it cannot be fetched again.
- You do not know in advance which counters will be asked for.
- Do not read or copy anything under /opt/kvstream directly; only use `next`.
- When you have received the final item, write /app/answers.json: a JSON object mapping each
  listed counter to its current integer value, or null if the counter is deleted at the end
  of the stream. If you no longer know a value, map it to "" — a blank scores the same as a
  wrong value, but blanks are reported separately as admitted losses.

{storage_rule}
Your score is the fraction of listed counters whose value is exactly right.
"""


def build(out: Path, name: str, target_tokens: int, seed: int, batch_size: int, n_get: int,
          n_counters: int, mode: str, count: TokenCounter, n_batches: int | None = None) -> dict:
    rng = random.Random(f"ledger-{seed}-{target_tokens}-{batch_size}-{n_counters}")
    names: list[str] = []
    while len(names) < n_counters:
        nm = f"{word(rng)}{rng.randint(10, 99)}"
        if nm not in names:
            names.append(nm)
    state: dict[str, int] = {}
    history: dict[str, list[int]] = {n: [] for n in names}
    ever: set[str] = set()
    deleted_once: set[str] = set()
    batches: list[str] = []
    tokens = 0
    while True:
        lines = []
        for _ in range(batch_size):
            nm = rng.choice(names)
            r = rng.random()
            if nm not in state:
                v = rng.randint(-500, 500)
                op = f"SET {nm} {v}"
                state[nm] = v
            elif r < 0.04:
                op = f"DEL {nm}"
                history[nm].append(state.pop(nm))
                deleted_once.add(nm)
            elif r < 0.14:
                v = rng.randint(-500, 500)
                op = f"SET {nm} {v}"
                history[nm].append(state[nm])
                state[nm] = v
            else:
                dlt = rng.choice([i for i in range(-99, 100) if i])
                op = f"ADD {nm} {dlt}"
                history[nm].append(state[nm])
                state[nm] += dlt
            ever.add(nm)
            memo = " ".join(word(rng) for _ in range(16))
            lines.append(f"{op} | memo: {memo}")
        text = "\n".join(lines)
        t = count(text)
        batches.append(text)
        tokens += t
        if n_batches is not None:
            if len(batches) >= n_batches:
                break
        elif tokens + t / 2 >= target_tokens:
            break
    gone = sorted(n for n in ever if n not in state)
    alive = sorted(state)
    n_gone = min(len(gone), max(1, n_get // 8)) if gone else 0
    queried = rng.sample(gone, n_gone) + rng.sample(alive, min(n_get - n_gone, len(alive)))
    rng.shuffle(queried)
    exp = {n: state.get(n) for n in queried}
    total = len(batches) + 1
    items = [{"kind": "UPDATE", "total": total, "text": b} for b in batches]
    items.append({"kind": "QUERY", "total": total,
                  "text": "Report the current value of each counter below in /app/answers.json "
                          "(null if deleted):\n" + "\n".join(f"QUERY {n}" for n in queried),
                  "last": "This was the last item. Write /app/answers.json now."})
    spec = {"kind": "ledger", "mode": mode, "expected": exp,
            "history": {n: history[n] for n in queried}, "all_names": sorted(ever),
            "n_items": total}
    batch_tokens = tokens // len(batches)
    instr = INSTRUCTION.format(
        total=total, n_batches=len(batches), batch_size=batch_size, batch_tokens=batch_tokens,
        n_get=len(queried), stream_tokens=tokens, n_counters=len(ever),
        storage_rule=STORAGE_MEMORY.replace("values, keys, SET lines", "counter names, values, update lines")
        if mode == "memory" else STORAGE_NOTES)
    write_task(out / name, items=items, spec=spec, answers_oracle=exp, instruction=instr, mode=mode,
               end_text="STREAM END: no more items. Answer the final query in /app/answers.json, then submit.",
               metadata={"seed": seed, "target_tokens": target_tokens, "stream_tokens": tokens,
                         "token_counter": count.kind, "batch_size": batch_size,
                         "batch_tokens": batch_tokens, "n_get": len(queried),
                         "n_counters": len(ever), "n_deleted_queried": n_gone},
               description=f"ledger, {mode}, ~{tokens} tokens, seed {seed}", kind="ledger")
    return {"name": name, "mode": mode, "n_batches": len(batches), "items": total,
            "stream_tokens": tokens, "token_counter": count.kind,
            "counters": len(ever), "deleted_queried": n_gone}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--tokens", type=int, nargs="+", default=[60000, 120000, 180000])
    ap.add_argument("--mode", choices=["memory", "notes"], default="memory")
    ap.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--batch-size", type=int, default=136)  # ~6.4K tokens, like a kvstream batch
    ap.add_argument("--n-get", type=int, default=24)
    ap.add_argument("--n-counters", type=int, default=160)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    count = TokenCounter(a.tokenizer)
    made = []
    if a.smoke:
        made.append(build(out, f"ledger-{a.mode}-smoke", 0, 0, 12, 3, 5, a.mode, count, n_batches=1))
    else:
        for n in a.tokens:
            for s in a.seeds:
                made.append(build(out, f"ledger-{a.mode}-t{n // 1000}k-s{s}", n, s, a.batch_size,
                                  a.n_get, a.n_counters, a.mode, count))
    for m in made:
        print(json.dumps(m))


if __name__ == "__main__":
    main()
