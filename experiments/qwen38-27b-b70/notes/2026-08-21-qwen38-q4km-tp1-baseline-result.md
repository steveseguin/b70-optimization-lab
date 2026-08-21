# Qwen3.8 27B Q4_K_M TP1 baseline result

Date: 2026-08-21

Status: **baseline established under the registered protocol in
[`2026-08-21-qwen38-q4km-tp1-lane-open.md`](2026-08-21-qwen38-q4km-tp1-lane-open.md);
research evidence, not a promoted record.**

## Result

Two complete cold 12-prompt realistic suites, each against a fresh server on
physical GPU 0 (post-recovery, clean journal), one cold pass per prompt,
`cache_prompt=false`, `temperature=0`, 512 tokens, `cached_tokens=0` on all
24 requests, realistic/fresh-response gates passed in both runs:

| Run | Conventional 99-interval median | p10 | Full after-TTFT median | TTFT median |
|---|---|---|---|---|
| A | `26.047863 tok/s` | `26.024304` | `26.066017` | `254.743 ms` |
| B | `26.068073 tok/s` | `26.058895` | `26.086426` | `254.910 ms` |

- **Route determinism: 12/12 complete output SHA-256 hashes identical between
  A and B across fresh server restarts.** The A hashes are this route's
  oracle candidate.
- Run-to-run median spread: `0.078%`.
- TP2-oracle equality is 0/12 (informational): the one-device reduction order
  legitimately differs from the promoted two-device route on every prompt.
  Output previews are coherent and on-task; the full semantic/arithmetic/
  JSON/factual/logic/Python-result battery is still required before any
  promotion or submission.
- Evidence:
  [`../data/2026-08-21-q4km-tp1-gpu0-baseline-a.json`](../data/2026-08-21-q4km-tp1-gpu0-baseline-a.json),
  [`../data/2026-08-21-q4km-tp1-gpu0-baseline-b.json`](../data/2026-08-21-q4km-tp1-gpu0-baseline-b.json).

## Context

Per-GPU, this single-card 26.05 already exceeds the promoted TP2 result's
24.86 tok/s-per-card share (`49.717503 / 2`), consistent with removing
cross-device synchronization. The lane goal is **30+ tok/s** on one B70
without weight, KV-precision, or quality changes: `+15.1%` from here via the
lever ladder. The GPTQ INT4 vLLM single-card comparison point (34.16 tok/s,
quality-rejected checkpoint) suggests most of that gap is weight-bandwidth
class, so the honest route is kernel/launch-overhead reduction at exact
output, then a separately gated look at any output-changing doors (e.g.
`GGML_SYCL_MMVQ_PHASE`, which is explicitly not bit-identical and would
reset the oracle and require the full quality battery).

## Next rungs

1. Per-step time attribution on this exact route (bounded llama-bench probe
   plus door stats already enabled) to size the non-GEMV overhead.
2. Same-binary single-door A/Bs at TP1 for the transferred doors that have
   never been attributed on one device; each lever lands with 12/12 exact
   hash reproduction and cache-zero evidence or dies with a recorded
   negative.
3. Observe (not lock) GPU 0 frequency under decode load; any clock policy
   change is a separate governance question.
