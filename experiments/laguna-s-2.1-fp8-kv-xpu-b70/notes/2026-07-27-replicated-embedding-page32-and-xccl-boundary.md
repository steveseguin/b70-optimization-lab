# Laguna FP8 KV — replicated embedding win, page-32 build, and host boundary

Date: 2026-07-27 America/Toronto

Status: **replicated target embedding is a verified decode win; native page-32
attention is built and component-tested but has not reached an endpoint
measurement because the current host entered a real XCCL collective-stage
failure.**

## Decode result

The target embedding can be replicated on every TP rank without changing the
FP8 teacher output. This removes one fixed-order embedding reduction from each
verifier cycle and changes the audited graph topology from 146/145 to 145/144.
The target-only prefill path is also replicated. The DFlash embedding path is
unchanged.

Source:

- vLLM worktree: `/home/steve/src/laguna-vllm-fp8-kv-20260727`;
- vLLM commit: `8268dcca3` (`Audit Laguna replicated-embedding graph topology`);
- validation: Python compilation and 60 focused tests passed;
- the complete vLLM and page-32 kernel mail-patch series under `../patches/`
  both applied cleanly to detached base worktrees and reproduced the source
  diffs;
- the deterministic nine-precursor corruption reproducer passed at
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/fp8-kv/pseq9-prefill-graph-repl2-8268dcca3-20260727T205912Z`.

Two fresh 13-prompt endpoint starts passed 13/13 within-FP8 exactness,
`cached_tokens=0`, the full-512-then-next boundary, the rollover row, all four
calibrated-scale audits, and 145/144 topology on all four ranks:

| run | conventional 99-interval median | historical 100-event median |
| --- | ---: | ---: |
| `decode-repl-8268dcca3-20260727T210433Z` | 95.019301665 tok/s | 95.979092591 tok/s |
| `decode-repl-confirm-8268dcca3-20260727T211004Z` | 95.818681878 tok/s | 96.786547352 tok/s |

This is a real improvement over the preceding roughly 94.245 tok/s FP8 result,
but it is not a LocalMaxxing record and is not faster than the sealed BF16 lane.

## Page-32 attention experiment

The first page-32 screen was invalid because the installed attention library
did not contain `16,128,32,false,false,false`; it fell back to PyTorch and ran
at roughly 12 tok/s. Its speed must not be compared:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/fp8-kv/decode-bs32-screen-8268dcca3-20260727T211604Z`

The kernel tree now contains focused Laguna presets instead of rebuilding the
full default policy matrix:

- kernel worktree:
  `/home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726`;
- `1857f0098`: add the page-32 decode shape;
- `4e624337e`: add focused Laguna prefill/decode presets;
- compiler: oneAPI DPC++ 2025.3, matching the installed PyTorch XPU stack;
- build directory: `build/attn-laguna-p32`;
- `libattn_kernels_xe_2.so` SHA-256:
  `28b612c5495c007a80d312fdc2a4be035d37c6fa582013c376be4a8f2b627669`;
- `_vllm_fa2_C.abi3.so` SHA-256:
  `beb82bd676779984b6133f897b9f1d9f526558827be277d9114fa51548c8bac4`.

A direct B70 component test passed for FP8 K/V with page 32, head size 128,
q=18, kv=2, both global `(-1,-1)` and sliding `(64,0)` attention, with no
fallback. The old page-64 binaries were backed up under:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/kernel-backups/fp8-page32-pre-4e624337e-20260727T213700Z`

The first endpoint start with the new binaries never reached model loading. It
stalled during four-rank XCCL initialization:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/fp8-kv/decode-bs32-native-4e624337e-r2-20260727T213931Z`

The old known-good page-64 binaries were then restored and their expected
hashes reverified. A page-64 health control stalled at the identical XCCL
topology boundary for more than six minutes:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/fp8-kv/decode-bs64-health-4e624337e-20260727T214929Z`

This means the current endpoint startup failure is not usable as evidence
about page-32 performance. The page-32 endpoint A/B remains unmeasured.

## Corrected collective classification

After both model starts were stopped cleanly, the tracked corrected probe was
inspected on disk, its 11 regression tests passed, and exactly one fresh probe
was run using the same `eno1`, OFI, and topology environment as the model
harness.

Artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/xccl-fp8-20260727-PmESMo/probe-fp8-post-identical-init-boundary`

Result:

```text
PROBE_RESULT=COLLECTIVE_STAGE_FAILURE clean_teardowns=0/4
```

All four ranks emitted `import-done`, `device-set`, `pg-initialised`,
`tensor-allocated`, and `all_reduce-start`. All four timed out with exit 124;
none emitted `all_reduce-done`. This is a real executed probe, unlike the
historical missing-source non-results.

No FLR, driver reload, PCIe reset, shared-memory deletion, or repeat probe was
performed. The conservative next action is one clean reboot, followed by
strict idle/device checks and exactly one corrected collective gate before
resuming model work.

Pre-reboot boot ID: `1e2c1032-5f4c-4ed5-9bc8-373de56dbebb`.

## Transferable learnings

- Smaller KV storage does not guarantee faster short-context decode. At these
  shapes, collectives, launch latency, dequantization, and partially occupied
  attention tiles can dominate memory traffic.
- Remove collective boundaries when exactness allows it. Replicating a small
  deterministic embedding eliminated one boundary and produced a measurable
  endpoint gain.
- Build only the exact attention policies required by the experiment. A
  focused configuration reduced build work and made the resulting binary
  identity auditable.
- Match the oneAPI compiler generation to the PyTorch XPU build. The first
  attempt accidentally selected oneAPI 2026.0 and failed; explicit 2025.3
  selection built and tested successfully.
- A fallback warning invalidates a kernel throughput screen. Stop early rather
  than interpreting fallback speed.
- When model startup stalls, restore the control binary and reproduce the
  boundary before blaming the candidate. Classify collective health with one
  inspected, bounded probe and read every rank log.
- Never escalate recovery from counters or a probe summary alone. Require
  stage markers proving the probe source executed.

## Resume order

1. Clean reboot; record boot identity and verify all four B70s are strictly
   idle and individually usable.
2. Run exactly one corrected four-rank probe. Require
   `PROBE_RESULT=PASS clean_teardowns=4/4`.
3. Run a fresh 128-token page-64 control using the old known-good binaries.
4. Install the already-built page-32 pair, verify hashes/runtime lock, and run
   the matching 128-token screen.
5. Only if page 32 is faster and exact, run the full 512-token suite twice.
6. Finish decode profiling before starting prefill tuning.
