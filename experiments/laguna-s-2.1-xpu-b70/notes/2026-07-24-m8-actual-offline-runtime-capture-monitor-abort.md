# Laguna M8 actual-model runtime-capture monitor abort

Date: 2026-07-24 America/Toronto

## Result first

The preregistered v8 actual-model gate completed and durably validated arms A
and B, then arm C failed closed on every rank when the intended first live
M=8 Breakable capture encountered vLLM's disabled post-warmup capture monitor.
This is a narrowly scoped runtime-capture authorization bug, not a descriptor,
model-correctness, A/B parity, performance, benchmark, payload, or
LocalMaxxing result.

The immutable sealed root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-872c304f8-20260724T184608Z
```

It must never be reused. The approved record remains
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## What completed

Arm A (`incumbent-eager`) and arm B (`segmented-eager`) each completed their
single fresh offline generation, reported exactly zero cached tokens, wrote
the immutable v8 driver record, and passed v9/raw-V2 aggregation. Their
returned 32-token lists and decoded text hashes are identical:

```text
token IDs  cca03973c1998dfc3255cad724577213ed01cb606cf12eb867358de16f9b9e3f
text       92105d1de6f357cac164f12b76adc090c334135477400010f3e1e810109efd0b
```

Arm A retained 60 manifests, 15 per rank, each with 201 events: 12,060 raw
events total. Arm B retained 60 manifests, 15 per rank, each with 444 events:
26,640 raw events total. This independently confirms that the prior analyzer
ordering repair passed its complete actual-model path.

Arm C initialized and completed the generic configured size-8 graph warmup,
then failed on the first live speculative-verifier forward. It produced only
one three-event pre-forward manifest per rank. Those incomplete manifests
contain logical-key, initial phase, and arm-contract metadata only; they are
not valid C evidence. C has no aggregate evidence or driver record, and no
final A/B/C analysis exists. Timing and PTI did not run.

## Exact failure and root cause

All four workers raised:

```text
RuntimeError: CUDA graph capturing detected at an inappropriate time.
This operation is currently disabled.
```

The driver surfaced `vllm.v1.engine.exceptions.EngineDeadError`.

The failure sequence is exact:

1. Startup graph warmup visits the configured M=8 shape while capture is
   globally enabled.
2. The Laguna target wrapper correctly filters that dummy call because it is
   not a real exact speculative-verifier transaction; therefore it creates no
   Breakable entry.
3. `GPUModelRunner.capture_model()` disables further captures after startup.
4. The first real request reaches the exact intended descriptor:
   `BatchDescriptor(num_tokens=8, num_reqs=None, uniform=False,
   has_lora=False, num_active_loras=0)`.
5. The exact eligibility/filter admits the request, finds no prior entry, and
   calls `BreakableCUDAGraphWrapper._capture`.
6. `_capture` checks the now-disabled global monitor before performing its
   guarded lazy capture, so every rank aborts.

The scheduler dump independently confirms one request, eight scheduled tokens,
and seven DFlash speculative tokens. This is not a descriptor mismatch.

The safe correction is to enable capture only around the live target
`_model_forward` when the already fail-closed
`laguna_m8_breakable_graph_eligible` predicate is true, and restore disabled
state in `finally`. Do not remove `_capture`'s monitor validation and do not
leave runtime capture enabled globally. A CPU regression must prove
false-to-true-to-false ordering, exception cleanup, and no monitor mutation for
noneligible forwards.

## Cleanup and artifact state

The root and arm directories are sealed mode `0500`; regular files are mode
`0400`. All root/arm pre/post idle checks passed across devices 0-3, and all
worker reports are empty. C's four workers logged cleanup completion. Each arm
logged the known single leaked-shared-memory resource-tracker warning, but
the durable post-worker and post-idle proofs show no remaining worker or
device activity.

## Frozen identities and hashes

- main tooling:
  `872c304f8d581025f57aef4abee7f408918cffd8`;
- preregistration:
  `e194b8cc1`;
- vLLM:
  `e25867aa698f82cbf2fb835e26807078674acebc`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- RPC paths: `m8p8-a`, `m8p8-b`, and `m8p8-c`;
- driver schema: `laguna-m8-offline-arm-v8`;
- aggregate schema: `laguna-m8-actual-offline-gate-v9`;
- raw format: `laguna-m8-raw-evidence-v2`.

Key retained hashes:

```text
82f1053a5c18a7f16ef8560e573a2ff6266dc8980134e81993dfa863129339c6  identity.txt
f10368a913fd908a8763c1ca7ec3dba49e6f9b9da3cc5bfba25184e650e2ee57  incumbent-eager/driver.json
f0f21be1aab96bc530ddbd15b36fde35a4da42a93af79907329a4f0ddc2a2045  incumbent-eager/evidence/evidence.json
6af26f826a3814425f4f8dc776defc5764c37a5aca6d0cb5cf553f7c2e7cf2eb  segmented-eager/driver.json
7da989aa198bf2163f6f47b7b6a2269b171531e398f1fef62cdc1f1a33d83cfa  segmented-eager/evidence/evidence.json
74da240313604e5e9d4ded355859369005a01fa842754c5bbe7103a1e420137f  segmented-graph/stderr.log
```

Machine-readable classification:
`data/laguna-m8-actual-offline-runtime-capture-monitor-abort-20260724.json`.
