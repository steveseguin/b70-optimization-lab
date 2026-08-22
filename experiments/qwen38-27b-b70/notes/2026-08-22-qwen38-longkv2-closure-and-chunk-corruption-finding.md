# longkv2 closure and the chunked-prefill corruption finding

Date: 2026-08-22

## Campaign closure

Arm `longkv2-a1` (incumbent stock control) stopped with runner rc=1. Under
the [longkv prereg](2026-08-22-qwen38-longkv-q64k32-endpoint-prereg.md)
addendum, the single relaunch budget was already consumed by the longkv1
suite-id burn, so **the longkv design is closed**. Root
`qwen38-q64k32-longkv2-a1-20260822` is preserved; no candidate arm ran; no
A-B evidence exists. Two independent causes were exposed, both of which
invalidate the design as preregistered:

1. **`max_model_len=2048` wall.** The sealed serving identity caps
   prompt+output at 2048; with the mandatory 512-token bench window, no
   prompt above ~1535 tokens is servable. Tier 2 row 1 (server-counted
   1537) was refused with HTTP 400 (`total of at least 2049 tokens`), so
   the tier-2/tier-3 windows (KV ~1600/1900) are unreachable under the
   sealed lane identity. Only ~KV<=1585 windows are possible at all, and
   only with a redesigned suite.
2. **Chunked-prefill cross-request corruption (the finding, below).**

## The finding

The eight tier-1 rows (~1244-1250 chat-templated prompt tokens) were the
first requests in this lane's recorded history to exceed
`max_num_batched_tokens=1024`, i.e. the first **multi-chunk prefills**
(every prior suite/smoke/quality request was single-chunk; the historical
25-prompt suite tops out far below 1024). The bench then died at the
tier-2 400 before writing `bench.json`, and the runner proceeded to the
quality battery on the still-running server. On this **stock control**
(policy off, stage `604f1b32…`):

- arithmetic, copy, JSON-schema, and 32x repeat determinism all **passed**;
- the long-context needle probe (987-token single-chunk prompt, needle
  `B70_QWEN36_NEEDLE_20260609`) returned
  `B70_QWEN3!!!!!!!!…` — the correct first characters followed by
  exclamation-mark degeneration, the classic garbage-logits signature —
  and **failed**.

The identical probe on the identical stack passed hours earlier in
`endpoint5-a1`/`b1` (battery green), where the entire request history was
single-chunk. The differential is the eight preceding multi-chunk
prefills. This is therefore evidence of **cross-request state corruption
triggered by multi-chunk prefill** in the incumbent stack — candidate
mechanisms include the GDN conv/recurrent chunked-state path and the
`VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH` reuse path; none is established
yet.

Scope honesty: the 101.9 tok/s record and every quality claim to date
were produced entirely under single-chunk traffic and are untouched. But
the lane as configured is **not safe for prompts above ~1024 tokens**
until this is isolated and fixed, and no long-KV campaign can produce
valid evidence on it. The Q64xK32 long-KV serving value remains
unmeasured (operator qualification stands; endpoint realization is
blocked behind this bug plus the 2048 cap).

## Diagnostic preregistration (chunkdiag, report-only)

Instrument: the sealed runner with record gates OFF
(`VALIDATION_REQUIRE_TP2_SEALED_GATES=0`) but the compile-cache
protections (`REQUIRE_COMPILE_CACHE_UNCHANGED=1`, `NO_WRITES=1`, manifest
preflight) and every stage/model/cache input SHA still verified; stock
stage only; fresh roots; quality battery on; evidence read from
`data/quality.json` and `data/bench.json`, not the runner exit code.

- Driver:
  [`run-20260822-qwen38-chunk-prefill-corruption-diag.sh`](../scripts/run-20260822-qwen38-chunk-prefill-corruption-diag.sh)
- Suite (1 row, `longkv--tier1-row1`, ~1244 tokens => 2 chunks), deployed
  0444 with tracked copy
  [`2026-08-22-qwen38-longkv-chunk-diag-suite.json`](../data/2026-08-22-qwen38-longkv-chunk-diag-suite.json),
  SHA-256 `0b66d5a6711a981480f09ba5956042a391da3082d3eb470d091fc89f2a37c6fc`.

Arms (each independent, fresh root, no same-root retry):

- **d2** — one 2-chunk row, then the battery. Needle FAIL reproduces the
  corruption at dose 1 (single multi-chunk request). Needle PASS pushes
  to a dose arm (d4, 8-row suite, to be built only in that branch). The
  d2 bench row's own `text_preview` also shows whether the multi-chunk
  request's *own* output is degenerate.
- Positive control: `endpoint5-a1` (on record) — same stack, 25
  single-chunk rows, battery green. No new control arm is run.
- Conditional follow-ups (each a new preregistered addendum before
  running): nospec variant (isolates MTP/spec involvement),
  ignore_eos-off variant, single-chunk-1023 variant.

Interpretation boundary: chunkdiag establishes reproduction and dose
only. Mechanism attribution (GDN chunk state vs persistent scratch vs
other) needs its own instrumented preregistration. Nothing here is a
record run; no rate from chunkdiag is comparable to anything.

## d2 result (2026-08-22): dose 1 does NOT corrupt

Arm `qwen38-chunkdiag-d2-20260822` ran fully green (runner rc=0): the
2-chunk row itself produced a coherent plan (512 completions, 0 cached,
prompt 1244, conventional rate **71.59 tok/s** — the first true long-KV
incumbent rate datum, vs ~101.9 short-KV), and the subsequent needle
probe returned the exact needle with `baseline_match_all=true`. One
multi-chunk request is insufficient. The a1-vs-d2 differential is now:
eight rows (dose) and/or the tier-2 HTTP-400 rejection between bench and
battery. Server-config suspects noted for later mechanism work:
`compile_ranges_endpoints=[1024]` places a full prefill chunk exactly on
a compiled-range boundary; GDN attention core runs as a splitting op.

**d4 addendum (preregistered before running):** the exact eight tier-1
rows from a1's exposure, no over-length request, then the battery.
Suite deployed 0444 with tracked copy
[`2026-08-22-qwen38-longkv-chunk-diag-d4-suite.json`](../data/2026-08-22-qwen38-longkv-chunk-diag-d4-suite.json),
SHA-256 `6e51726f56bbb99ce86e2cf95f4e5d22ed4c141ce3a546d508cc03ae6fb37b6a`;
driver gains the `d4` action selecting it. Needle FAIL => dose-dependent
corruption reproduced cleanly. Needle PASS => the delta narrows to the
400-rejection path (or a non-history trigger), and the next
preregistered addendum (d4b) would append a deliberate over-length
request before the battery.

## d4 result (2026-08-22): REPRODUCED — dose-dependent, 400 exonerated

All eight 2-chunk rows were individually healthy (coherent previews, 512
completions, 0 cached; per-row conventional rates 59.33-103.31, row1
72.59 vs d2's 71.59 on the same content), and the subsequent needle
probe degenerated to the byte-identical `B70_QWEN3!!!!…` with
`baseline_match_all=false`. One multi-chunk request is clean (d2); eight
corrupt the engine's cross-request state (d4 = a1 without the 400). The
tier-2 rejection plays no role. Server-log audit: all 96 GDN persistent
scratch allocations occur inside the graph-capture window, none during
serving — no dynamic growth; the pool's *reuse* remains the suspect, not
its allocation.

**d5 addendum (preregistered before running):** identical exposure to
d4 (same 8-row suite, same everything) with
`VALIDATION_GDN_SPEC_PERSISTENT_SCRATCH=0` — a runtime
allocation-strategy door (per-call scratch instead of the capture-time
persistent pool) that leaves compiled graphs and the cache identity
untouched. Needle PASS => the persistent-scratch reuse path is the
mechanism locus. Needle FAIL => the locus moves to the GDN chunked
conv/recurrent state path or KV block recycling, and the next addendum
would titrate dose (2 and 4 rows) to extract the threshold arithmetic.
