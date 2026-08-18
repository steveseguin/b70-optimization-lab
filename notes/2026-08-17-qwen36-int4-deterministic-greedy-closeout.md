# Qwen3.6 27B INT4 deterministic-greedy closeout

Date: 2026-08-17 (America/Toronto)

## Decision

The AutoRound INT4 MTP3 TP2 lane remains **inconclusive and
non-production-ready**. No candidate passed both required gates:

1. all 25 complete token arrays exactly equal to the matched M1 target; and
2. preferred 99-interval median at or above `100 tok/s`.

No LocalMaxxing result was submitted and no runtime was restored. The current
source and every experimental alternative remain preserved on `main` or in a
sealed raw run.

## What the resumed gate established

A shared deterministic greedy rule was added behind
`VLLM_XPU_DETERMINISTIC_GREEDY_MARGIN`. It chooses the lower token ID only when
the processed top-two logit gap is within the configured bound. With margin
`0.03125`, two fresh graph-free target starts produced the same 435-token
structured response, including the former unstable branch at token index 364.

That stabilized one target trajectory but did not make packed M4 verifier
arithmetic equal to ordinary M1 decode. The fastest resumed full candidate was
only `13/25` exact at `93.611164891 tok/s`. Enabling the Qwen Gemma RMS path
improved parity to `16/25` but reduced the preferred median to
`92.559992724 tok/s`; the broad batch-invariant contract produced the same
`16/25` result at `92.558096955 tok/s`.

A bounded packet trace made the distinction concrete:

- before the Qwen RMS correction, incident token 87 was a high-confidence
  packed-row replacement (`220`, margin `0.796875`) while M1 required `12805`,
  which was absent from packed top-4;
- after the RMS correction, Python token 100 was a low-margin replacement:
  packed `6983`, M1 `1848`, gap `0.046875`;
- raising the shared margin to `0.05` fixed that token relative to the old
  target but changed the matching M1 target earlier. Against a fresh matching
  `0.05` target, both fail-fast prompts diverged.

Therefore a global tie threshold is not an exactness repair. It changes the
two trajectories differently because the underlying M1 and M4 logits are not
equivalent.

## Concise control table

All rates below use the preferred conventional 99-interval metric. `Warm` means
the measured suite followed the harness smoke in the same fresh server process;
it does not mean prompt/KV reuse. Every listed measured row reported
`cached_tokens=0`.

| Control | Correctness | Execution mode | Warmup status | tok/s |
| --- | --- | --- | --- | ---: |
| deterministic target structured A/B, margin `.03125` | A/B exact, 435/435 | graph-none eager M1 | cold servers; smoke-warmed | `11.779` / `11.646` |
| deterministic 25-target A, margin `.03125` | target oracle, 25 cache-zero rows | graph-none eager M1 | cold server; smoke-warmed | `11.653` |
| layer-0 dependency candidate, margin `.03125` | `13/25` exact | PIECEWISE MTP3; exact GDN eager break | fresh compile; smoke-warmed | `93.611` |
| Qwen RMS candidate, margin `.03125` | `16/25` exact | PIECEWISE MTP3; exact GDN eager break | fresh compile; smoke-warmed | `92.560` |
| global + Qwen RMS candidate, margin `.03125` | `16/25` exact | PIECEWISE MTP3; exact GDN eager break | fresh compile; smoke-warmed | `92.558` |
| serial gated-RMS fail-fast control | `1/2` exact; Python unchanged | PIECEWISE MTP3; four M1 gated-RMS rows | fresh compile; smoke-warmed | `90.456` |
| progressive-FA fail-fast control | `1/2` exact; Python unchanged | PIECEWISE MTP3; progressive M1 FA | fresh compile; smoke-warmed | `78.694` |
| margin `.05` fail-fast candidate vs matching `.05` target | `0/2` exact | PIECEWISE MTP3 vs graph-none M1 | fresh servers; smoke-warmed | `90.327` candidate |

## Contradictions and confounders

- Generic quality gates passed even when complete token parity failed. They are
  task-quality checks, not an exact target comparator.
- `GDN_CAPTURE_NATIVE_SPEC=1` is recorded in several identities, but exact
  recurrent mode intentionally forces that op to an eager graph break. These
  are not fully captured-GDN runs.
- Four-prompt controls overstated generality. Later 25-prompt gates repeatedly
  failed despite apparently exact short canaries.
- The deterministic top-two policy disabled the local-argmax/top-ID shortcuts
  because it required dense logits. Its overhead contributed to the sub-100
  full-suite medians.
- Serial gated RMS and progressive FA changed execution cost but not the
  Python mismatch, ruling them out as sufficient corrections.
- The `0.05` candidate must not be compared to the `.03125` target. The fresh
  matching `.05` target changed trajectory earlier, and the pair was `0/2`.

## Preserved evidence

The structured machine-readable companion is
[`../data/qwen36-27b-autoround-int4-deterministic-greedy-closeout-20260817.json`](../data/qwen36-27b-autoround-int4-deterministic-greedy-closeout-20260817.json).
It records raw roots, final manifest hashes, source commits, rates, and exactness
counts. The experimental serial gated-RMS source remains default-off in vLLM
commit `95a76ff89173ff56e90a2ed384fde2cea3c015e6`; the deterministic policy is in
its parent `c6dc1a3f6d56729d3bde5544420690be9416c5fd`.

## Reopen condition

Do not continue threshold or batch-invariance flag sweeps. Reopen this lane only
with a source design that makes the packed verifier transaction genuinely M1
equivalent while retaining enough accepted-token speed to clear `100 tok/s`,
then require two matched 25-prompt target starts and two speculative starts.
