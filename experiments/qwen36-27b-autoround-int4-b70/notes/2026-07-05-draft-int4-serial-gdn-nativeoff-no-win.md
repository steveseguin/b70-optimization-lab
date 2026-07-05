# Qwen27 Draft-INT4 Serial GDN Native-Off Screen: No-Win

Date: 2026-07-05

Target lane:

- `webhie/Qwen3.6-27B-int4-AutoRound`
- one Intel Arc Pro B70 per run, TP1
- MTP3, `max_cudagraph_capture_size=8`
- target INT8 LM-head with BF16 scales
- draft INT4 LM-head:
  `VLLM_XPU_DRAFT_LM_HEAD_INT4=1`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16`
- strict fresh Qwen realistic suite, chat mode, token-id timing,
  `cached_tokens=0` required
- repeat quality used `QUALITY_REPEAT_RUNS=64`,
  `QUALITY_SKIP_LONG_CONTEXT=1`

## Why this was tested

The fast draft-INT4 normal path reaches about `70-72 tok/s` but fails the
repeat color/order quality gate, usually alternating:

- `blue, green, red, yellow`
- `blue, green, red`

ReplaySSM fixes quality but falls below the current `65.276 tok/s` record
(`61-62 tok/s`). The hypothesis was that the existing serial GDN speculative
decode flags might provide an exact-enough state transition while preserving
some of the fast draft-INT4 speed.

## First screen: native spec decode still enabled

Stamp: `20260705Tserialgdn01`

This screen did **not** force `VLLM_XPU_GDN_NATIVE_SPEC_DECODE=0`, so it is
not a valid test of the Python serial GDN path. Native spec decode can bypass
the Python serial flags. It is still useful as a record of the metadata mistake
and as a same-window fast draft-INT4 quality failure.

| Label | Median tok/s | p10 | Mean | Strict fresh | Quality |
|---|---:|---:|---:|---|---|
| `qwen27-draftint4-fast-control-serialscreen` | `70.229` | `66.605` | `71.194` | pass, cached0 | fail repeat |
| `qwen27-draftint4-serialspec-basic` | `71.544` | `64.868` | `71.237` | pass, cached0 | fail repeat |
| `qwen27-draftint4-serialspec-packed` | `72.130` | `65.236` | `71.688` | pass, cached0 | fail repeat |
| `qwen27-draftint4-serialspec-conv-packed-promote` | `71.723` | `64.876` | `71.344` | pass, cached0 | fail repeat |

Repeat64 signatures:

- control: `55/64` `blue, green, red, yellow`, `8/64`
  `blue, green, red`, `1/64` repeated-yellow runaway;
- all three serial-flag lanes: `55/64` `blue, green, red, yellow`, `9/64`
  `blue, green, red`.

Decision: no candidate is promotable, and the screen exposed that the harness
needed to record more GDN/native-spec identity fields.

Patch made after this screen:

- `experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh`
  now records draft-INT4, serial GDN, native GDN, ReplaySSM, offset, and
  promotion flags in `identity.env`.

## Corrected screen: native spec decode disabled

Stamp: `20260705Tserialgdn02`

The corrected screen set `VLLM_XPU_GDN_NATIVE_SPEC_DECODE=0` so the Python
fallback/serial paths were actually exercised.

| Label | Key env | Median tok/s | p10 | Mean | Quality / decision |
|---|---|---:|---:|---:|---|
| `qwen27-draftint4-fallback-nonserial-nativeoff` | native spec off, no serial | `12.348` | `10.198` | `12.463` | fail JSON exact; reject |
| `qwen27-draftint4-serialspec-generic-nativeoff` | native off, serial conv, generic recurrent | `10.001` | `7.842` | `10.701` | benchmark pass, quality not completed; reject for speed |
| `qwen27-draftint4-serialspec-packed-nativeoff` | native off, serial conv, packed recurrent | `9.684` | `7.846` | `10.368` | benchmark pass, quality not completed; reject for speed |
| `qwen27-draftint4-serialspec-packed-promote-nativeoff` | native off, serial conv, packed recurrent, promote running after spec | incomplete | incomplete | incomplete | terminated during strict suite; live logs only `~2.3-13.2` gen tok/s; reject for speed |

The three true serial lanes were terminated once it was clear they were
orders of magnitude below the `65.276 tok/s` current record. Server logs before
termination showed sustained engine generation throughput roughly:

- generic serial: `2.6-16.9 tok/s`, last sampled `8.3 tok/s`;
- packed serial: `3.2-14.7 tok/s`, last sampled `9.1 tok/s`;
- packed+promote serial: `2.3-13.2 tok/s`, last sampled `6.3 tok/s`.

## Decision

Close Python serial GDN for Qwen27 draft-INT4 as a no-win:

- With native spec decode still enabled, the lanes are fast but still quality
  invalid and do not actually prove the serial path.
- With native spec decode disabled, the serial path is too slow by an order of
  magnitude and still lacks a complete quality pass.
- Do not spend more endpoint time on `SERIAL_SPEC_*` offset/source tweaks
  unless there is a new source-level implementation that avoids the Python
  fallback cost.

## Next credible implementation path

Move to an exact accepted-prefix GDN/DeltaNet state transaction or tape:

- fixed-shape GPU tape for prefix `0..k` per request/layer;
- prefix `0` = exact base running conv+SSM state before verifier rows;
- prefix `i` = conv rolling window and SSM state after exactly the first `i`
  accepted draft tokens;
- GPU-side masked commit after sampling for full reject, partial accept, and
  full accept;
- no Python per-layer loops or dynamic allocation in the decode hot path;
- validate state parity against sequential/no-spec or ReplaySSM before any
  endpoint speed claim.

This state transaction may recover the fast draft-INT4 lane above the current
record by fixing the `blue, green, red` truncation without ReplaySSM's overhead.
It is not by itself a full `>100 tok/s` plan; that still likely needs a
stronger target-matched drafter, branch/regenerate/token-tree support that
preserves sequential semantics, or target-forward/kernel reduction.

## Artifacts

Tracked compact summary:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-serial-gdn-screen-summary-20260705.json`

Raw run directories:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-fast-control-serialscreen-20260705Tserialgdn01`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-serialspec-basic-20260705Tserialgdn01`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-serialspec-packed-20260705Tserialgdn01`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-serialspec-conv-packed-promote-20260705Tserialgdn01`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-fallback-nonserial-nativeoff-20260705Tserialgdn02`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-serialspec-generic-nativeoff-20260705Tserialgdn02`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-serialspec-packed-nativeoff-20260705Tserialgdn02`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-serialspec-packed-promote-nativeoff-20260705Tserialgdn02`

