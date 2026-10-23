#!/usr/bin/env python3
"""Exactness and time of clm_baselines' incremental token count against the upstream count.

  count_memo_check.py <context_snapshots/turn-NNNN.json> [--out receipt.json]

Takes the recorded message list (a real 2M hostile history), and checks that the memo returns
the upstream count for: 60 prefixes of the history, the full list, a replaced content string, a
replaced tool-call argument, an inserted message, a removed message, a reordered list, a list
content and an empty list. Then times one simulated run of the harness's per-step counting (four
counts of every prefix in turn) with the memo, against the upstream cost measured on 12 prefixes
and scaled linearly. CPU only.
"""
import argparse, json, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from clm_harness.utils import tokens as tk  # noqa: E402
ORIG = tk.count_tokens
import clm_baselines  # noqa: E402,F401  (installs the memo)
MEMO = tk.count_tokens
assert MEMO is not ORIG, "the memo was not installed (COUNT_MEMO=0?)"


def check(name, msgs, receipt):
    a, b = ORIG(msgs), MEMO(msgs)
    receipt.append({"case": name, "n_messages": len(msgs), "upstream": a, "memo": b, "equal": a == b})
    if a != b:
        print("MISMATCH", name, a, b); sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    msgs = json.loads(a.snapshot.read_text())["messages"]
    print(f"{len(msgs)} messages from {a.snapshot.name}")
    receipt = []
    rng = random.Random(7)
    for k in sorted(rng.sample(range(1, len(msgs)), 60)) + [len(msgs)]:
        check(f"prefix {k}", msgs[:k], receipt)
    m2 = [dict(m) for m in msgs]
    i = next(i for i, m in enumerate(m2) if isinstance(m.get("content"), str) and m["content"])
    m2[i]["content"] = m2[i]["content"] + " x"
    check("replaced content", m2, receipt)
    m3 = [dict(m) for m in msgs]
    j = next(i for i, m in enumerate(m3) if m.get("tool_calls"))
    m3[j]["tool_calls"] = [dict(tc, function=dict(tc["function"], arguments=tc["function"]["arguments"] + " ")) for tc in m3[j]["tool_calls"]]
    check("replaced tool-call arguments", m3, receipt)
    check("inserted message", msgs[:5] + [{"role": "user", "content": "new"}] + msgs[5:], receipt)
    check("removed message", msgs[:5] + msgs[6:], receipt)
    check("reordered", list(reversed(msgs)), receipt)
    check("list content", [{"role": "user", "content": [{"type": "text", "text": "a b c"}, "tail"]}], receipt)
    check("empty", [], receipt)
    check("full again", msgs, receipt)
    print(f"exact on {len(receipt)} cases")
    # timing: the harness counts the whole list four times a step
    t0 = time.monotonic()
    for k in range(1, len(msgs) + 1):
        view = msgs[:k]
        for _ in range(4):
            MEMO(view)
    memo_s = time.monotonic() - t0
    sample = list(range(len(msgs) // 12, len(msgs) + 1, len(msgs) // 12))
    t0 = time.monotonic()
    for k in sample:
        ORIG(msgs[:k])
    per = (time.monotonic() - t0) / len(sample)          # mean over evenly spaced prefixes = mean over all
    orig_s = per * len(msgs) * 4
    print(f"memo: four counts of every prefix, {len(msgs)} steps: {memo_s:.1f} s; upstream estimate {orig_s:.0f} s "
          f"(mean {per:.3f} s a count over {len(sample)} prefixes, x4 x{len(msgs)})")
    if a.out:
        a.out.write_text(json.dumps({"snapshot": str(a.snapshot), "n_messages": len(msgs), "cases": receipt,
                                     "memo_run_s": round(memo_s, 2), "upstream_estimate_s": round(orig_s, 1),
                                     "upstream_mean_count_s": round(per, 4)}, indent=1) + "\n")


if __name__ == "__main__":
    main()
