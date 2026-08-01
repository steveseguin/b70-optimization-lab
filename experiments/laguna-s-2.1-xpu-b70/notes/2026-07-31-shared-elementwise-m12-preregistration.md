# Laguna exact shared-elementwise M12 preregistration

Date: 2026-07-31 America/Toronto

Status: **component and default-off integration gates passed; exactly one
strict cold endpoint leg authorized**.

## Premise

The confirmed BF16-KV record is `124.64241272122038 tok/s` conventional at
verifier width 12 and DFlash depth 11. Its target event profile leaves the
largest repeated graph class after the output collective, containing
post-attention normalization and local shared/routed MoE work.

An earlier width-8 record proved an exact shared-expert elementwise treatment:

- shared `F.silu(gate) * up`: two BF16 operations to one native operation;
- routed `*= 2.5` followed by shared `+`: two BF16 operations to one native
  operation while preserving the intermediate BF16 rounding boundary;
- exhaustive coverage of all 65,280 finite BF16 values plus changing tensors;
- `0.699138-0.722866 ms` saved per complete 47-layer cycle on four B70s; and
- a later exact endpoint record when stacked with Q/K normalization plus RoPE.

The native operations and vLLM dispatch remain hard-pinned to exactly eight
rows, so this proven operation class is absent from the width-12 record. The
kernel arithmetic is row-independent; M12 changes only the number of identical
workgroups and the guarded tensor shape.

## Frozen design

- start from XPU kernels
  `69e8ad9119a9cc70c3906b82be6254dd0160f00e` and vLLM
  `58608c6361f1a958a7e933bed0be8c88c35aa26e`;
- preserve the existing M8 symbols and implementation byte-for-byte;
- add separately named M12 SiLU/multiply and scale/add `_C` operations accepting
  only contiguous, non-aliasing BF16 `[12,256]` and `[12,3072]` tensors;
- use the same M8 workgroup geometry, explicit BF16 SiLU midpoint correction,
  FP32 multiply/add order, and explicit BF16 routed-scale store;
- add a separate default-off vLLM selector restricted to exact target M12,
  DFlash11, TP4/EP4/PP1/DP1, one sequence, PIECEWISE Breakable graph, BF16,
  E256/K10, shared width 1024, routed scale 2.5, no EPLB/redundancy, and the
  record exact MoE/router/route-interleave contracts;
- draft, prefill, target M1 teacher, tails, M8 execution, projections,
  collectives, routing, KV, model precision, sampling and graph boundaries
  remain unchanged.

## Gates and stop rules

1. Focus-build only `_C.abi3.so` with pinned oneAPI 2025.3.3. Every other
   native module/DSO remains byte-identical to the record.
2. On one B70, require raw-BF16 M12 equality against the literal incumbent for
   all finite BF16 activation inputs under the established paired-up corpora,
   all finite routed inputs under zero/one/reversed shared corpora, at least 32
   changing random tensors per operation, and a post-timing replay.
3. Over all 48 target layers require a structural `192 -> 96` device-operation
   reduction, positive saving for each operation, and at least `0.50 ms`
   combined median saving before vLLM integration is authorized.
4. Focused vLLM tests must prove M12 target dispatch, selector-off inertness,
   and incumbent fallback for M1, M2..M11 tails, M8, draft, prefill, compiled,
   wrong dtype/shape and missing symbols.
5. Only after gates 1-4 pass may one strict cold endpoint leg be authorized.
   It must report its first valid score and preserve 13/13 canonical-q1 token
   and text exactness, cache zero, target `146/145`, draft `14/13`, one
   invocation per prompt, 72-second pre/post idle, and clean teardown.
6. Stop on any raw-bit mismatch, target/draft/graph identity drift, saving below
   the component floor, host instability or teardown failure. No retry,
   reboot, reset, acceptance manipulation, width/depth change, prompt/metric
   change, cache/history reuse, warmup, response reuse or LocalMaxxing
   submission is authorized here.

## One-B70 component result

The M12 native source is committed at XPU-kernel commit
`99886d7` and the focused `_C.abi3.so` SHA256 is
`36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095`.
The exact component artifact is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-shared-elementwise-m12-component-20260801T042945Z
```

The component passed every frozen gate:

- all 65,280 finite BF16 activation inputs under ones, reversed-finite and
  signed-zero up corpora: raw-BF16 exact;
- all 65,280 finite BF16 routed inputs under zero, one, reversed-finite and
  signed-zero shared corpora: raw-BF16 exact;
- 32/32 changing activation and 32/32 changing scale/add epochs exact before
  timing, and 32/32 plus 32/32 exact again after timing;
- activation stack: `0.560984575 -> 0.229509625 ms`, saving
  `0.328323575 ms`, 15/15 paired blocks won;
- scale/add stack: `0.545047825 -> 0.240437050 ms`, saving
  `0.302611075 ms`, 15/15 paired blocks won;
- combined 48-layer stack: `1.216545725 -> 0.479045650 ms`, saving
  **`0.734276300 ms`**, 15/15 paired blocks won;
- structural device operations: `192 -> 96` per target cycle.

The combined saving exceeds the preregistered `0.50 ms` floor. Default-off
vLLM selector integration was committed at
`cf247e55d14ce918c06e89252649b50b9292ba20`. Its focused B70 suite passed
`36/36`, covering M12 dispatch for both operations, record-contract rejection,
missing-symbol failure, compiled-path rejection, and incumbent fallback for
other widths. Ruff and `git diff --check` also passed.

The endpoint runtime is locked by
`tools/runtime-lock-shared-elementwise-m12.json` at SHA256
`96e26345d8567a8e57370f8806cfaa0635207a7ecc9c5909d063fed35bf3e3db`.
The verifier passed against candidate `_C.abi3.so` SHA256
`36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095`
and byte-identical record copies of every other native module and mapped DSO.
The formal launcher records the selector, verifies its service environment,
and requires exactly one rank-local enable marker from each of TP/EP ranks
`0/0` through `3/3`; selector-off marker leakage fails closed.

Gates 1-4 are therefore complete. Per the frozen plan, exactly one strict cold
endpoint leg is now authorized. Its first valid result is final for this
candidate whether it wins or loses; no automatic retry or hardware recovery is
authorized.
