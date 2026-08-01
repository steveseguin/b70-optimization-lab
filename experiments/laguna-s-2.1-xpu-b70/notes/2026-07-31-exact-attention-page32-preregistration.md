# Laguna exact-verifier attention page-32 screen

Date: 2026-07-31 America/Toronto

Status: **preregistered before device execution.**

## Premise

The promoted exact BF16-KV record serves with a 64-token KV-cache block.  Its
M=12 verifier is represented as twelve independent one-token sequences with
the same block-table row and staircase KV lengths, so all 48 target layers use
the Xe2 paged-decode kernel.  The record's attention binary already contains
Laguna's non-causal local and non-local qgroup-16/head-128 policies for both
32- and 64-token pages.

The fixed 13-prompt score window covers contexts from roughly 89 to 962 tokens.
At these short lengths, a 32-token policy uses two subgroups per workgroup
instead of four and exposes twice as many KV workgroups.  This may improve
occupancy.  It may also change attention reduction grouping, so raw BF16
identity is a mandatory gate rather than an assumption.

## Frozen component screen

Use the promoted `_vllm_fa2_C` and `libattn_kernels_xe_2.so` bytes for both
arms.  Generate identical logical BF16 Q, K, and V tensors for the physical
Laguna TP4 shape: 12 verifier rows, 12 local Q heads, 2 local KV heads, and
head dimension 128.  Pack the same logical K/V sequence into either 64-token
or 32-token physical pages with sequential block tables.  Use the exact
verifier metadata (`cu_seqlens_q=0..12`, staircase `seqused_k`) for both full
and 512-token sliding attention.

Sample the actual prompt lengths from the promoted suite at output offsets
0, 33, 66, and 99.  Alternate arm order during timing.  Record the loaded
native module origins and SHA-256 values.

## Gates

1. Require raw BF16 equality for every full/sliding, context, and seed case.
2. Require no runtime, device, or teardown error and preserve the one-card
   idle boundary.
3. Weight each sampled context equally, then project 12 full plus 36 sliding
   layers.  Endpoint integration requires at least 1.13 ms projected saving
   per target forward, enough to cover the current 130-tok/s cycle gap before
   graph/integration overhead.
4. A component pass authorizes only a default-off launcher treatment and a
   bounded exact smoke.  A cold scored endpoint still requires a separate
   preregistration and the unchanged 13/13 token/text, cache-zero, one-start,
   146/145 target, 14/13 draft, and clean-idle gates.

No model, weight, BF16 KV semantic, verifier width, draft depth, target
verification, sampler, acceptance rule, prompt, output length, or score metric
may change.  No reset, driver reload, FLR, reboot, or privileged recovery is
authorized by this screen.

## Result

Status: **rejected at raw exactness; no smoke or endpoint run.**

The first invocation at
`laguna-exact-attn-page32-20260801T084404Z` combined a physical selector and
an affinity mask in a way that exposed zero devices.  It stopped during
`torch.xpu.set_device(0)` and is classified as a pre-device harness error, not
candidate evidence.  The corrected visibility syntax exposed exactly rank 1.

The substantive artifact is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/components/
laguna-exact-attn-page32-20260801T084437Z
```

Page 32 differed from page 64 in **208/208** raw-BF16 comparisons: two seeds
at every one of 52 real-window contexts for both full and sliding attention.
The route therefore fails gate 1 decisively.  No model service, smoke, score,
reset, or reboot followed.

The harness's synchronized Python-call timings are retained in the artifact,
but are not used as a target-cycle estimate: metadata construction and
allocation are not amortized as they are under the record's graph replay, and
the resulting projected totals exceed the measured target cycle.  Exactness
alone closes the treatment.

The FA2 extension was the promoted byte (`3390a306...aedc9dd4`).  The loader
mapped the previously audited external attention-library origin with the
promoted byte-identical SHA-256 (`ad0eb26f...333b65ca`), so this result does
not introduce a new binary identity.
