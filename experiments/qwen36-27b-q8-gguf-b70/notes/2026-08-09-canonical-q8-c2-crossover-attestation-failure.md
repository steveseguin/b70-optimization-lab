# Canonical Q8 Phase-2 crossover attestation failure

Date: 2026-08-09

## Classification

The first live Phase-2 crossover attempt failed closed during GPU 2 lane
attestation while the other Wave 1 requests were still in flight. This is a
harness-attestation failure and a diagnostic-only partial Wave 1 packet.
Wave 2 never started, so the packet supports no crossover outcome, causal
claim, performance claim, or promotion decision.

Failed packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c2-crossover-four-gpu-20260810T033914.082005385Z`

The detached root failure packet is hash-sealed and its complete manifest
verifies successfully.

- root artifact-manifest SHA-256:
  `5d2c0d0efedb7bce3657b075bab32ecab5edb800712748d6f77585cb51bd9132`
- detached root failure-marker SHA-256:
  `de4949dc88cc65d3a8080ecf7592ddb17c0c2b57aa1c7e2af485fd9713a1e07b`
- root cleanup-status SHA-256:
  `57b863f8ecccca60ee17d5a80a0500848f199b6f5d53c68806689511c566071d`
- frozen wave-input manifest SHA-256:
  `79acddc662f510734fe3f238e921aad8d46a29a23968559a85673102bf9554d3`
- runner/analyzer recorded by that input manifest:
  `22863f08d545b675a18aa90ebf0097ffdbfcf792247c997aa25e521803cf176a` /
  `ed5cf8a9d3e3f5c87aa19bf96f1ce49cc5880b5c1296f84fb298c2e49fab4e09`

The four sealed Wave 1 lane artifact-manifest SHA-256 values are:

- GPU 0 forward selector-off:
  `1d477461053c1064fe4feed7d0cf9f5f31ae471d41aa97f106ea1c7691587302`
- GPU 1 forward selector-on:
  `b09c26c303e6e0af7c03164efb24bfc1a791fa46ca0ce6ba183c8d88a7332348`
- GPU 2 reverse selector-off:
  `a6215181a675fc1256a5e511c017f7cae207585f75fc455d79e0190e1d7cd011`
- GPU 3 reverse selector-on:
  `a4ad60640cb4f8883c68e82dd1029f29a974bbf5ec40407975301c13db52f7df`

## Exact failure and root cause

GPU 2 produced an `EVIDENCE_VALID` capture at port 19722, SHA-256
`da8682832fe62fa6b90a0d3d32d9de437ed3206bb04b0ab60956c7316b7d47cb`.
Its lane attestation, SHA-256
`ed989948fd1ca2fd61bcfa7698854ebd6c7456fac76700b731f49289a6635b61`,
failed exactly these reported fields:

- `fields.capture=false`;
- `capture_fields.live_binding_before_recomputed=false`;
- `capture_fields.live_binding_after_recomputed=false`.

Independent recomputation localized both failures to only
`canonical_argv_exact`; every other retained live-binding field passed. The
actual before/after argv used `--port 19722 -dev SYCL0`. The analyzer had
incorrectly inferred `-dev SYCL2` from `port - 19720`.

The launcher intentionally exports `ZE_AFFINITY_MASK=2` before starting GPU
2's process. The isolated process therefore sees its selected physical card as
the affinity-local device `SYCL0`. The retained identity binds `gpu_index=2`
and `ZE_AFFINITY_MASK=2`, while raw XPU evidence binds physical Device ID 2
from 43 MiB before launch to 30570 MiB loaded. Physical-card identity and the
process-local SYCL device namespace are distinct; deriving the latter from the
host port/card ordinal was the attester defect.

GPU 2's attestation exit published the Wave 1 post-release failure. GPU 0 had
already completed a passing lane packet. The already-in-flight GPU 1 and GPU
3 captures completed about 20 seconds later, then observed the peer abort
while taking their postcapture boundaries;
their `postcapture log did not stabilize` messages are secondary abort-path
labels, not evidence of local log instability. Each retained 60-second passive
drain kept the server log at exactly 29162 bytes. Wave 1 did not receive a
success wave seal, and Wave 2 was not launched.

## Partial Wave 1 diagnostic observation

All four Wave 1 forced-512 captures completed, although GPU 1 and GPU 3
finished after GPU 2 had published the attestation failure. Within each
cross-card scenario pair, selector-off and selector-on produced identical
token streams:

- forward GPU 0 selector-off and GPU 1 selector-on reproduced A/slot 0 for all
  512 tokens; B/slot 1 first differed from its oracle at generated ordinal 71
  (`332` observed versus `71093` in the oracle);
- reverse GPU 2 selector-off and GPU 3 selector-on reproduced B/slot 0 for all
  512 tokens; A/slot 1 first differed from its oracle at generated ordinal 96
  (`90` observed versus `71093` in the oracle).

Those first differences are one generated token after the separately measured
B and A natural-answer boundaries at ordinals 70 and 95, respectively. No
pre-boundary regression was observed. The selector-on raw logs contain the
exact flat prerelease and recurrent first-hit markers; selector-off logs
contain no canonical route markers.

This is partial diagnostic evidence only. Wave 2 never ran, so there are no
same-card selector flips and these observations do not classify `NO_EFFECT`,
establish a causal result, or support any performance claim.

## Cleanup and evidence scope

The root cleanup record reports exit status 2, current wave 1, no forced kill,
no cleanup survivor, and an incomplete body. Both failure passive scans
completed with no query failure or device fault. The postcleanup scan also
found no quiet-state failure; no active XPU probe was performed after failure.
The detached root failure marker consequently remains
`diagnostic-only-failure`, `evidence_valid=false`, and
`performance_promotable=false`.

The partial forced-512 captures may be used only as the explicitly scoped
partial Wave 1 diagnostic evidence above. They are not a balanced two-wave
crossover and must not be used to classify `PASS_CAUSAL_CONTROL`, treatment
effect, correctness promotion, or performance.

## Minimal fix and next rerun

The analyzer now retains the exact registered port range 19720 through 19723
but requires affinity-local `-dev SYCL0` on every lane. Offline regression
coverage accepts SYCL0 on all four ports, rejects SYCL1/SYCL2/SYCL3 on every
port, and rejects ports outside the frozen range. Revalidation of the sealed
GPU 2 before/after bindings passes every recomputed field with this correction.

After the corrected analyzer, runner pin, and activated runner bytes receive
independent exact-byte review, the next attempt must start in a new run root
and rerun both waves from the beginning. It must not resume or promote any lane
from this failed packet. The normal fail-closed lifecycle and cleanup policy
remain unchanged.
