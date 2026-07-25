# Laguna Phase 0 — full-cycle attribution preregistration

Date: 2026-07-25 America/Toronto

Status: **design only. Diagnostic scope. No XPU or model execution is
authorized until an implementation packet is separately committed and receives
independent adversarial review.** This document authorizes no benchmark, no
record claim, and no submission.

## Purpose

The approved record is `94.92003934159611` tok/s, LocalMaxxing
`cmrzrd4tf001ipa013xpx4kid`, at vLLM `ef334233d` and XPU kernels `4772f7275`.
The objective is to exceed `100` tok/s on the same honest contract. That
requires either a `5.08%` cycle-time reduction or a `7.3%` relative acceptance
gain, or a product of the two.

Optimization effort cannot be allocated because **most of the decode cycle is
currently unattributed**. Two independent gaps are established below from
already-recorded evidence.

### Gap 1 — the draft side has never been measured

The completed current-stream event diagnostic
(`data/laguna-s-2.1-m8-current-stream-event-diagnostic-20260725.json`)
decomposes device time on the selected rank as:

| Category | Duration | Share |
| --- | ---: | ---: |
| graph | 80.297 ms | 64.44% |
| collective | 34.931 ms | 28.03% |
| attention | 9.387 ms | 7.53% |

Its contract is `146` graphs, `97` collective boundaries, `48` attention
boundaries, over `48` decoder layers at `6` intervals per layer. That is the
**target** replay in its entirety. The DFlash draft — one context-KV precompute
plus seven sequential proposal forwards per cycle — contributes **zero**
measured intervals.

The record's own submission summary gives `1718` draft cycles, `12026` draft
tokens (`7.000` proposals per cycle), and `4644` accepted draft tokens
(`2.703` accepted per cycle). With the bonus token that is `3.703` emitted per
cycle, so the record cycle is `3.703 / 94.920 = 39.01 ms`. The same diagnostic
records prior whole-replay host totals with a median of `2.097 ms`. Even
allowing generously for host-versus-device and windowing differences, the
target replay cannot plausibly account for the majority of a `39 ms` cycle.

The draft was **deliberately excluded** from the Breakable-graph experiment
that produced the `+171.9%` step change; that preregistration's exclusions
state "capture or otherwise change the DFlash draft in the first experiment".
The largest structurally comparable lever in the campaign has therefore never
been measured, let alone attempted.

### Gap 2 — the record metric is dominated by early-generation cost

From the same submission summary:

| Metric | Value |
| --- | ---: |
| `tok_s_out` (median, tokens 1-100 after TTFT) — **the record metric** | 94.920 |
| `tok_s_full_after_ttft_median` (full 512-token window) | 122.735 |
| `tok_s_out_p10` | 65.964 |
| `tok_s_out_mean` | 103.832 |
| `tok_s_out_stdev` | 46.644 |

The full-generation rate is `29.3%` higher than the scored 1-100 window. The
scored window is therefore carrying a cost that the rest of generation does
not. Under the assumption of constant emission per cycle, that is `39.01` vs
`30.17` ms per cycle — an `8.84 ms` per-cycle penalty concentrated in the
scored window. **That assumption is itself untested and is the first thing this
diagnostic must resolve**, because the two candidate explanations lead to
opposite work:

- **time-per-cycle** — early cycles are genuinely slower (first-touch
  allocation, first replay, lazy initialization, cache growth); attack
  overhead; or
- **tokens-per-cycle** — early acceptance is lower because the draft has less
  context to condition on; attack acceptance and draft conditioning.

If the penalty is real and reducible, halving it moves the scored median to
roughly `107` tok/s on arithmetic alone. This is the single largest identified
opportunity and it is currently unexplained.

**Honesty boundary, stated explicitly.** Reducing genuine first-cycle work is a
real optimization. Pre-warming the model, replaying a throwaway request,
retaining any state across requests, prefix caching, or any warmed continuation
is cheating and is prohibited. Every arm here starts cold, in a fresh process,
with `cached_tokens=0` asserted per request, on the unmodified real prompts of
`realistic-suite-v1.json`. No synthetic prompt is admissible anywhere in this
lane.

## Questions this diagnostic must answer

1. What fraction of the `39.01 ms` record cycle is target replay, DFlash
   context-KV precompute, the seven draft forwards, sampling, and host or
   scheduler residue? Attribution must sum to the measured cycle with a stated
   residual.
2. Is the scored-window penalty time-per-cycle or tokens-per-cycle? Report
   per-cycle wall time and emitted-tokens-per-cycle separately, as functions of
   token index across the full 512-token generation.
3. Within the draft, what is the split between the single context-KV precompute
   and the seven sequential forwards, and how much of each is launch or host
   residue rather than device work?
4. Does per-prompt cost correlate with context length? The scored metric is a
   median across 13 prompts with `p10 = 65.964` against a median of `94.920`;
   identify what distinguishes the slow half.

## Method

Extend the existing, already-audited current-stream event instrumentation
rather than authoring a new harness. The `146/97/48` target contract, its
segment-kind order hash, and its rank-local event mechanism are retained
unchanged. New intervals are added only around the DFlash context-KV precompute
and each of the seven proposal forwards, plus a per-cycle boundary marker and
a per-cycle emitted-token count.

Constraints, all mandatory:

- the instrumentation changes no model operation, tensor, arithmetic, kernel
  argument, graph, collective, or boundary order;
- it is default-off behind its own selector and fails closed;
- both arms remain bitwise exact against the canonical q=1 teacher, and the
  instrumented run must reproduce the frozen `token_ids_sha256` and
  `text_sha256` of its uninstrumented control;
- measurement is rank-local; as with the prior diagnostic, the global critical
  path and cross-stream collective completion are **not** claimed to be
  validated;
- full 512-token generations on the unmodified 13-prompt real cold suite, one
  active generation, fresh process per arm, `cached_tokens=0` per request.

## Committed implementation packet — part 1 of 2

The runtime instrumentation is frozen at vLLM `f5ce85f4c` on branch
`experiment/laguna-runtime-graph-20260724` in
`/home/steve/src/laguna-vllm-runtime-graph-20260724`, parent `fcc2506f7`.

- new `vllm/v1/spec_decode/laguna_cycle_attribution.py`;
- call-site marks only in `vllm/v1/spec_decode/llm_base_proposer.py`
  (cycle begin/end and each of the seven proposal forwards) and
  `vllm/v1/spec_decode/dflash.py` (context-KV precompute);
- `vllm/compilation/breakable_cudagraph.py` is **untouched**, so the frozen
  `146/97/48` contract and its kind-order digest cannot drift.

Selectors, both default-off:
`VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_ROOT` (absolute path) and
`VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_DEVICE_CYCLES` (default 256, bounded to
`[1, 4096]`). With the root unset the recorder is never constructed and every
call site is a single `is None` test.

Eleven marks and ten intervals per cycle: `pre_ctxkv`, `ctxkv`, `proposal_0`
through `proposal_6`, `post_proposals`. Host wall time is recorded for every
cycle; device events only for the bounded prefix, which is what keeps a
~1800-cycle suite run from allocating unbounded events.

Fails closed on mark-order drift, unclosed or double-opened cycles, mid-cycle
finalize, stream-identity drift, event-count drift, incomplete or negative
event timing, a relative root, or an out-of-range device budget. A depth other
than the frozen 7 records nothing rather than guessing. The payload is written
once with `O_EXCL|O_NOFOLLOW` at mode `0400` and fsynced.

Verification at commit: `tests/v1/spec_decode/test_laguna_cycle_attribution.py`
14 passed; `tests/v1/cudagraph/test_breakable_cudagraph.py` 36 passed and 11
skipped, identical to the pre-change baseline; `ruff check` and `ruff format`
clean on all four files, with the untouched baseline confirmed clean first.

### Still outstanding — part 2 of 2

No XPU or model execution is authorized yet. Still required:

1. a lab-side analyzer that joins the four per-rank attribution payloads with
   the existing raw proposal/target/rejection evidence to produce
   accepted-tokens-per-cycle alongside per-cycle time, and validates the
   acceptance conditions below;
2. a one-shot runner and preflight, modelled on
   `run_laguna_m8_current_stream_event_diagnostic.sh`, with hash pinning, idle
   and worker assertions, private NVMe roots, and sealed output;
3. independent adversarial review of the complete packet.

## Frozen identity

- record functionality: vLLM `ef334233deabeaeedb607056a2db1c90edb3887c`;
- XPU kernels `4772f727590c51b72add79350b913d098cf67872`;
- prior diagnostic instrumentation base: vLLM
  `fcc2506f7da3a9fd142928af9275d25b9687342a`;
- models: the hash-frozen internal-NVMe copies under
  `/mnt/fast-ai/llm-models/laguna-s-2.1`;
- suite: `experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json`.

## Acceptance

The diagnostic reports `exact_full_cycle_attribution_stop` only if every arm is
bitwise exact against the canonical q=1 teacher and its uninstrumented control,
every request is cache-zero, all four ranks report the frozen segment-kind
order, attribution sums to measured cycle time with an explicitly stated
residual, and no timing field is derived from a warmed, cached, or continued
request.

## What a pass authorizes

Only the selection and preregistration of the next optimization lever. It
authorizes no candidate, no endpoint campaign, no record claim, and no
submission. Timing recorded here is diagnostic attribution and must never be
cited as a throughput result.

## Exclusions

No change to the record configuration, its selectors, or its promoted
artifacts. No modification of the DFlash draft's arithmetic. No graph capture
of the draft in this diagnostic — that is a candidate for a later, separately
preregistered experiment, and measuring its opportunity is precisely the point
of this one.
