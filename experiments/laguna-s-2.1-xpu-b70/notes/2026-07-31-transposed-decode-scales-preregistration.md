# Laguna transposed decode-scale layout preregistration

Date: 2026-07-31 America/Toronto

Status: **confirmed exact BF16-KV record at 122.828558 tok/s conventional;
all component, integration, endpoint, topology, and operational gates passed**.

## Premise

The exact width-12 INT4 grouped GEMM reads packed weights in contiguous K32
tiles, but the checkpoint scale layout is `[expert,N,K/32]`. At each K group,
the 64 output columns owned by a workgroup therefore read BF16 scales with a
stride of `K/32`: 96 elements (192 bytes) for W13 and 32 elements (64 bytes)
for W2. The kernel already issues a separate scale prefetch, so this scattered
layout can waste transactions and cache lines in the bandwidth-dominant MoE
path.

Transpose only the immutable per-expert scale table to `[expert,K/32,N]` once
before decode. Add a separately named default-off exact-decode kernel that
uses the transposed addresses while retaining the confirmed GRF128 geometry,
group-32 vectorized dequantization, K/N/M tiles, packed weight bytes, BF16
scale values, BF16 multiplies, DPAS operations, accumulator order, stores, and
persistent expert scheduler unchanged.

## Gates

1. The new selector must require the exact width-12 target identity and must
   not reach draft, prefill, another group size, another dtype, or selector-off
   calls.
2. A production BMG static build must show the intended contiguous scale
   addressing, 128 GRFs, no scratch/spill metadata, and the same live 32 BF16
   multiplies, 16 shifts, 16 bitfield operations, and two DPAS instructions as
   the confirmed exact mainloop.
3. Only after static pass, build the ABI-matched oneAPI-2025.3 DSO. A
   changed-input component compares ordinary `[N,G]` control scales with the
   logically identical `[G,N]` candidate scales for real W13 and W2 shapes.
   Require every raw BF16 output to match.
4. Stop before vLLM integration unless the candidate improves the summed W13
   plus W2 component median by at least `2.0%`. This higher threshold reflects
   the added model-load storage/layout plumbing and the endpoint's noise.
5. A component pass authorizes a separate integration design and smoke, not a
   score-bearing endpoint.

No target/draft/KV precision, model, prompt, acceptance policy, benchmark
metric, teacher, or quality contract may change. No reboot, reset, driver
action, endpoint, or submission is authorized here.

## Component outcome and integration design

The first device run of source `fdbe3b633` was invalid and is retained as a
negative result.  Its transposed prefetch reused the old two-dimensional
`[N,1]` descriptor with a one-element dynamic pitch.  The candidate failed
with `UR_RESULT_ERROR_DEVICE_LOST` and wedged physical GPU 0's compute queue.
No reset or reboot was taken; GPU 0 remains quarantined.  Artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-component-fdbe3b6-20260731T152243Z`

Source `2f0b0611b3999a76592c79a314d69f4b7ab8f285` fixes the descriptor by
representing a scale line as a real `[1,SG_N]` surface with physical strides
`[N,1]`.  The production static probe passed on healthy GPU 1: 128 GRFs, no
spill-memory accesses, 32 BF16 multiplies, two DPAS instructions, and the same
shift/bitfield instruction counts as control.  The ABI-matched DSO is SHA-256
`c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`.

The changed-input component gate then passed all six raw-BF16 comparisons:

| shape | control median | candidate median | speedup |
|---|---:|---:|---:|
| W13, `N=2048 K=3072 M=120` | 0.324687 ms | 0.320999 ms | 1.011489x |
| W2, `N=3072 K=1024 M=120` | 0.191079 ms | 0.182581 ms | 1.046546x |
| summed | 0.515766 ms | 0.503580 ms | **1.024200x** |

Artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-component-2f0b061-20260731T154509Z`

This clears the preregistered 2.0% component threshold.  The integration is
therefore separately authorized with these boundaries:

1. `VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES` is strict literal `0/1` in
   both Python and C++ and requires the established Laguna INT4/BF16-scale,
   top-10, 64-local/256-global-expert EP4 exact-MoE contract.
2. Each of the 48 target MoE layers retains its checkpoint `[E,N,K/32]`
   scales for prefill and creates immutable `[E,K/32,N]` clones before graph
   capture.  The total added persistent storage is 1,811,939,328 bytes per
   rank.  vLLM profiles this model memory before sizing KV cache.
3. Only a 12-row target call selects the clones.  With top-10 routing this is
   the exact `M=120` generic grouped-GEMM route screened above.  The dense
   six-layer DFlash draft has no MoE scales and is untouched.  Every other row
   count retains the checkpoint layout.
4. Source commit `8dd94f2` implements that model-side integration and includes
   selector/row-routing unit tests (15 targeted tests passed).  A real
   `XpuFusedMoe.apply` control/candidate smoke on healthy GPU 1 must raw-match
   before any TP4 endpoint is considered.
5. Even an integration-smoke pass does not authorize a score claim.  GPU 0
   must first be recovered at a user-visible reboot boundary, then the fixed
   cold 13-prompt exactness/topology/cache gate must pass.

## Integration-smoke outcome

The first gate launch stopped before a kernel call because the standalone
worker had not explicitly loaded `_moe_C`; this was a harness failure, not a
candidate result.  Commit `3d53af816` repaired the import and the fresh run
passed:

- real `XpuFusedMoe.apply`, not a direct grouped-GEMM call;
- healthy physical GPU 1 only;
- three independently seeded 12-row BF16 hidden-state inputs;
- identical input and logical-scale hashes between control and candidate;
- raw BF16 output exactness `3/3`;
- control created no transposed tables;
- candidate created exact physical shapes `[64,96,2048]` and
  `[64,32,3072]` while retaining the ordinary tables;
- mapped grouped-GEMM DSO and source identities matched the pins above.

Result: `INTEGRATION_RESULT=PASS exact=3/3 layout_correct=True`.

Artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-integration-8dd94f2-20260731T155418Z`

This authorizes the unchanged TP4 endpoint gate after a clean reboot restores
GPU 0.  It does not predict or claim endpoint throughput; the component gain
is only 2.42% in the two MoE GEMMs and must survive 48 layers, graph capture,
collectives, attention, draft work, and fixed-window metric noise.

## First post-reboot control: harness-only failure

The first same-DSO selector-off control completed the entire frozen suite with
13/13 token/text exactness, all cached-token counts zero, one invocation, and
the required target 146/145 plus draft 14/13 topology.  Its conventional
median was `120.796931473 tok/s`, but it is **not a valid control leg** and is
not used for a performance claim: after the service parent exited, the runner
checked for multiprocessing children before their ordinary shutdown completed
and aborted before the required post-stop idle interval.

Artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-control-20260801T004218Z`

`cleanup-status.txt` records `original_status=2`, and no `status.txt` exists.
The children disappeared without reset or intervention and all devices were
idle afterward.  The harness now waits up to 30 seconds for ordinary child
reaping after stopping the parent; this boundary is after the scored request
window.  A fresh control remains required before the candidate.

## Valid endpoint control and two candidate starts

After the bounded worker-reaping fix, the selector-off control and both
selector-on starts completed the entire frozen gate:

| Leg | Conventional 99 intervals | Historical compatibility | Exact | Idle |
| --- | ---: | ---: | ---: | ---: |
| selector-off control | 118.802183680 | 120.002205737 | 13/13 | 72/72 s |
| first candidate | 121.383776672 | 122.609875426 | 13/13 | 73/73 s |
| independent confirmation | **122.828558121** | **124.069250627** | 13/13 | 73/72 s |

Artifacts:

- control: `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-control-20260801T005044Z`;
- first candidate: `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-candidate-20260801T005945Z`;
- confirmation: `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-confirm-20260801T010855Z`.

The first candidate improved its same-DSO adjacent control by
`2.581592992 tok/s` (`+2.1730%`).  Both candidate starts independently beat
the preceding `121.290560973 tok/s` GRF128 record.  The lower candidate margin
was only `0.093215699 tok/s` (`+0.0769%`), so it was not promoted alone.  The
predeclared independent cold confirmation then measured `122.828558121 tok/s`,
beating the preceding record by `1.537997149 tok/s` (`+1.2680%`).

All 39 endpoint responses were token-and-text exact against canonical q1 and
reported `cached_tokens=0`.  Each service used one suite invocation, no warmup
generation, no retry, target 146/145 and draft 14/13 graph topology on all four
ranks, and clean process, port, device, and idle teardown.  The candidate did
not change weights, BF16 scale values, arithmetic, accumulation, routing,
sampling, target verification, KV precision, prompts, or metric accounting.

The confirmation is therefore promoted as a new exact BF16-KV record.  The
record packet is
[`2026-07-31-transposed-decode-scales-confirmed-record.md`](2026-07-31-transposed-decode-scales-confirmed-record.md),
and its structured summary is
[`data/laguna-transposed-scales-confirmed-record-20260731.json`](../../../data/laguna-transposed-scales-confirmed-record-20260731.json).
