#!/usr/bin/env python3
"""Arithmetic model of the two-card guess-and-verify pipeline (CPU only, no device).

Inputs: the per-position hit/miss sequences of the official draft head against the quantized target's own
tokens (packet 31, four prompts, 64 generated tokens each) and measured stage times. It replays each
sequence through a small event model of the two rank processes and reports ms per token and tok/s.
This is a model for choosing what to build next, not a measurement.
"""
import json, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACC = json.loads((HERE.parent / "packet31-mtp-acceptance" / "acceptance.json").read_text())


def sequences(source="mtp_int8_iq3"):
    out = {}
    for row in ACC["positions"]:
        prompt = row["prompt"]
        hit = row["sources"][source]["hit"]
        out.setdefault(prompt, []).append(bool(hit))
    return out


def simulate(hits, A, B, D, h, schedule):
    """hits[i]: whether the guess for generated token i+2 is right (token 1 is produced sequentially).
    A, B: first/second half; D: draft; h: hand-over cost per transfer between ranks.
    Returns emission times of tokens 1..N+1."""
    # token 1: sequential
    t = A + h + B
    emit = [t]
    c0 = None          # completion time of rank 0's speculative half for the next position
    c0_start = None
    for ok in hits:
        tau = emit[-1]  # previous token confirmed
        if schedule in ("rank1", "rank1+cancel"):
            g_ready = tau + D                      # rank 1 computes the next guess first
            if c0 is None:                         # no speculative half yet (first step)
                c0 = tau + h + A; ok_here = True   # token known: confirmed half
            else:
                ok_here = ok
            if ok_here:
                start1 = max(g_ready, c0 + h)
            else:
                redo_start = tau + h if schedule == "rank1+cancel" else max(tau + h, c0)
                c0 = redo_start + A
                start1 = max(g_ready, c0 + h)
            emit.append(start1 + B)
            c0 = max(c0, g_ready + h) + A          # speculative half for the following position
        elif schedule in ("rank0", "rank0+cancel"):
            # the draft runs on rank 0 (it has a copy of the head); rank 1 starts its half at once
            if c0 is None:
                c0 = tau + h + A; ok_here = True
            else:
                ok_here = ok
            if ok_here:
                start1 = max(tau, c0 + h)
                free0 = max(c0, tau + h)
            else:
                redo_start = tau + h if schedule == "rank0+cancel" else max(tau + h, c0)
                c0 = redo_start + A
                start1 = c0 + h
                free0 = c0
            emit.append(start1 + B)
            c0 = free0 + D + A                     # draft, then the speculative half
        else:
            raise ValueError(schedule)
    return emit


def rate(emit):
    return 1000.0 * (len(emit) - 1) / (emit[-1] - emit[0])


def main():
    seqs = sequences()
    cases = [
        # label, T (sum of halves), D, h, schedule, split fraction for rank 0
        ("packet 36 as measured: T=45.9, D=4.2, python controller", 45.9, 4.2, 0.8, "rank1", 0.497),
        ("  + cancel a wrong half at once", 45.9, 4.2, 0.8, "rank1+cancel", 0.497),
        ("packet 38 expected: T=41.4 (packet 37 halves), D=3.7, native controller", 41.4, 3.7, 0.3, "rank1", 0.5),
        ("  + cancel a wrong half at once", 41.4, 3.7, 0.3, "rank1+cancel", 0.5),
        ("  draft on rank 0, layers rebalanced (rank 0 half = rank 1 half - D)", 41.4, 3.7, 0.3, "rank0", None),
        ("  draft on rank 0, rebalanced, + cancel", 41.4, 3.7, 0.3, "rank0+cancel", None),
        ("  the same with a 2.5 ms draft", 41.4, 2.5, 0.3, "rank0+cancel", None),
        ("  the same with T=38 (epilogues, QSA attention) and a 2.5 ms draft", 38.0, 2.5, 0.3, "rank0+cancel", None),
    ]
    rows = []
    for label, T, D, h, schedule, frac in cases:
        if frac is None:
            A = (T - D) / 2; B = T - A      # D + A == B
        else:
            A = T * frac; B = T - A
        per = {p: rate(simulate(s[1:], A, B, D, h, schedule)) for p, s in seqs.items()}
        rows.append((label, A, B, D, per, st.median(per.values())))
    prompts = list(seqs)
    print("guess rate by prompt: " + ", ".join(f"{p} {sum(s)}/{len(s)}" for p, s in seqs.items()))
    print()
    print("| Case | first half / second half / draft (ms) | " + " | ".join(prompts) + " | median |")
    print("| --- | --- | " + " | ".join("---:" for _ in prompts) + " | ---: |")
    for label, A, B, D, per, med in rows:
        print(f"| {label} | {A:.1f} / {B:.1f} / {D:.1f} | " + " | ".join(f"{per[p]:.1f}" for p in prompts) + f" | {med:.1f} |")
    json.dump([dict(case=l, first_half_ms=A, second_half_ms=B, draft_ms=D, tok_s=per, median_tok_s=m) for l, A, B, D, per, m in rows],
              open(HERE / "model.json", "w"), indent=1)


if __name__ == "__main__":
    main()
