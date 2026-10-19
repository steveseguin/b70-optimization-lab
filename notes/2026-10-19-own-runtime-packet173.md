# Packet173: two-card lever table, staged for the packet168 census

This was CPU-only preparation: no GPU, no build, no queue change. Everything
here is a prior or a design; none of it is a measurement. The record stays
bundle 8 at **58.798108759 tok/s**.

## Thresholds

The thresholds come from packet160's 1,188 record intervals. The replay
reproduces 58.798108759 exactly.

| Gain | Saving needed per half, both ranks |
|---|---:|
| +0.5% | 0.070 ms |
| +1% | 0.139 ms |
| +2% | 0.275 ms |
| +3% | 0.409 ms |
| +3.5% | 0.475 ms |

packet168 sums the two ranks, but the halves overlap. A summed census
reduction of 1 ms is therefore worth only about 0.6 ms/token. The owner's
"0.6 ms/token" (+3.5%) equals a **0.95 ms summed** census reduction. Levers
that act on one rank only are capped:

* Rank 1 only: saturates at about +3.85%, because B − A is 0.606 ms.
* Rank 0 only: needs 0.40 ms/half for +0.5%, because it gains only on misses.

## Ranking

The ranking was computed on three prior scenarios, all of them priors and
none of them measurements:

* the packet140 proxy;
* packet141 cold/warm weighting;
* expert-heavy.

The order is the same under all three.

1. **D2: dense-weight L2 warm-ahead** from latency-bound predecessors.
   * Mid +1.45% to +1.80%; range +0.7% to +3.2%.
   * About 4 h to build.
   * It is new relative to p119 (warming during a bandwidth-bound kernel lost
     at 1.079×), p138/p125 (route-predicted experts) and p142/p145 (layout
     was null).
2. **D1: N1 scale multicast**, mid +0.62%.
3. **R1: p164 route election**, mid +0.36%.
4. **N3: producer RMS leaves**, mid +0.28%.
5. **G1: gated norm in the recurrence epilogue**, mid +0.24%. A novelty check
   comes first, because `Kernel<SplitNorm>` already exists.
6. **E1n2: 40-bit IQ2 cell**, mid +0.22%.

There are no levers for attention (QSA) or the residual.

**On priors, no lever reaches +2%.** The census decides. D2 becomes "worth
building" if dense_hc measures at least 13.8 ms summed.

After the census, run:

```bash
python3 -B rank_levers.py --census <census dir>
```

It reruns the replay with the real per-rank split from `census-input.json`.

## Process-wide flag pattern

Each candidate gets one native CLI option that defaults to bundle 8, following
the `--host-path` precedent:

* `main.cpp:133-155` (the Options struct), the parse branch at `main.cpp:183`,
  and the check at `main.cpp:232-262`;
* applied at Engine startup at `main.cpp:716-728`.

It must then be threaded through every window:

* **W0p/W2m/WS*:** `chain_pipeline.py:569-590` and `:310`, plus `window.py`
  at lines 393, 566, 453 and 190.
* **KD:** `draft_window.py:127` and `:171`.
* **K1/K2:** a fixture flag passed at `window.py:299-307`. The fixture parsers
  throw on unknown arguments (`p49d_fixture.cpp:157`,
  `fixture_driver.cpp:161`).
* **Checks:** `arguments136.py:74` and `packet56_submission.py`.

The v5 switch calls the same setter, and a CLI value that conflicts with a
bracket view is refused. The gate is copied from p58asd's
`wait_policy_gate.py`. Full details are in
[LEVER-TABLE.md](../experiments/own-xpu-runtime/stage2/packet173-twocard-lever-table/LEVER-TABLE.md),
with the data in `lever-table.json` and `thresholds.json` and the prior output
in `prior-ranking.txt`.
