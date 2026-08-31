# Qwen3.8 Flash-Next TP4 MTP0 A31 M1-only preregistration

Date: 2026-08-31
Status: independently reviewed, frozen, and blocked until an attended reboot

## Question

Does the already qualified production-M1 MoE change from four to eight warps
improve the synchronous-PLE eager endpoint by itself? Three real-weight
component brackets retained exact outputs and saved `38.0-41.7 us` per layer,
or a non-promotional projection of `1.825-2.001 ms/token` across 48 layers.
That would move the protected `5.515783 tok/s` result only to roughly
`5.572-5.577 tok/s`; the full endpoint must measure it.

A30 does not answer this question. It combined the M1 map with grouped
HyperConnection, ran 1.82% below the protected result, and failed fresh-start
4K reliability. It rejects that composite, not M1 alone.

## Current-source forward port

A31 preserves historical A29 and derives a new attempt 31 / port 19703 lane.
The model, revision, sealed 18-file kernel stage, synchronous PLE-only
placement, eager mode, MTP0, cache, prompts, authority hashes, and complete
client battery are unchanged. The selected-key receipt must still prove M1,
key 1, eight warps, four stages, and the exact tuned map.

The current vLLM checkout is `797769b34`; its two descendants beyond A29's
source add only the default-off grouped-HC implementation and its qualified
dynamic-M dispatch. A31 requires `VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP` unset and
false. Async PLE and all repeatability traces are also unset. The live native
modules must resolve from the original sealed stage at
`/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`.

The kernel workspace has advanced through five preserved commits to
`e42188999`, but it is not on `PYTHONPATH` and none of those newer binaries are
loaded. A hash-bound rewrite verifies every parent back to sealed source
`ad25aa9f`, the exact clean head immediately before service, and stage-local
module resolution. This preserves the failed event-chain work as source
evidence without importing it into A31.

## Lifecycle and interpretation

The current boot `c36480de-9150-4182-9888-08c85d2d9de4` remains rejected after
the event-chain runtime failure. No reboot is authorized by this packet. On a
later attended fresh boot, the ordinary-XCCL affinity component must complete
first. A31 verifies its same-boot evidence manifest and accepts either a clean
performance pass or a clean performance close; any runtime failure forbids the
model load. Both the outer supervisor and launcher also require the atomic
shared state `cpu-affinity-complete` for the current boot, so an HC-SiLU or
affinity interruption cannot be bypassed by intact but stale evidence.

A31 then remains the boot's only full model load. It must pass recovery, the
inherited semantic boundary, 16 exact repeats, all three protected short
hashes, cache-zero 4K needle, and both exact-4K authority rows. A quality pass
and short median above `5.515783 tok/s` is only a candidate. Causal promotion
still requires a separately booted current-source map-unset control and a
fresh A31 repeat. Any miss preserves every protected result unchanged.

Structured preregistration:
[`20260831-tp4-mtp0-a31-moe-m1-current-prereg.json`](../data/20260831-tp4-mtp0-a31-moe-m1-current-prereg.json).
