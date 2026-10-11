# MoE boundary diagnostic — CPU preparation, October 11

Sketch A of the [first-forward audit](2026-10-11-attempt8-moe-first-forward-audit.md)
is implemented as a separate, default-off diagnostic. **122 CPU tests pass,
zero failures, errors or skips.** No GPU, server, Docker, systemd, port 8188,
LTX unit, device file, power or host-memory setting was touched. This is not a
native result, runtime repair, output-quality qualification or new admission.

The interrupted untracked `overlay-moe-boundary/` implementation was retained
and reviewed. Its first resumed run passed 113 of 116 tests; three artifact
checks failed because the saved seals were stale. Before resealing we added a
non-contiguous router-ID refusal, preserved the actual K tile in launch
receipts, tested the real expert-apply wrapper, made the controller's exit
marker atomic, and kept the watcher monitoring after a latched fault through
exit plus 305 seconds. Restored journal access cannot erase that failure.

## Frozen variant

[Bundle and runbook](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/README.md),
[patch](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/boundary.patch),
[patch manifest](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/patch-manifest.json),
[CPU validation receipt](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-cpu-20261011/validation.json).

- Frozen lab preimage: `3a6435133de4f2fc5b937e5b48033832d622df3d`.
- vLLM upstream: `ced6857afa0ea7b2e3f0846a62e1394e90f15607`.
- Attempt-8 production manifest remains byte-identical:
  `daf50d2391549a9fb5c03ee2cf3a69e763cc44e621fdaf35e4b06529c7142b69`.
- Diagnostic manifest (52 runtime files): `c786f7380ca0ab0cf8c52d31ad8bd109752917ed1397b9377c734232a176b101`.
- Patch manifest: `f3555f9f03d4f7e8e49fa0c0ef052864a926c1e2596214209e979279bdb2335d`.
- Same image as attempt 8:
  `vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.

The builder follows the separately pinned teardown-variant pattern. It reads
preimages from the frozen Git revision, seals whole-file copies and a patch,
and stages a fresh external directory only with `SCREEN1B_MOE_BOUNDARY=1`.
It never edits the production overlay or installed runtime. Both the staged
controller and entrypoint refuse an implicit/off launch of this diagnostic
package. Runtime hooks themselves default off. This is an intentional
same-base localization experiment, not a rolling-upstream promotion.

## Checks before GEMM

| Check | Receipt and failure behavior |
| --- | --- |
| Raw native alignment, before local remap | Router IDs and the entire raw expert-ID array, including its remapped tail, must be in [0,512). All M × topk route indices occur exactly once; padding, expert membership, histogram, block divisibility and capacities must agree. |
| Rank remap | Map must be the rank's exact 512-global/128-local linear map. Actual remapped IDs must agree, with active IDs either -1 or in [0,128). Producer tensor identity and contents are rechecked immediately before GEMM. |
| Compact weights | Both w13 and w2 require a table when compact, current worker PID/rank/device stamp, int64 table of 128 entries, retained pinned host owner/alias and exact physical partition. Reconstructed addresses for every logical row must reach the expected complete owned row. |
| Workspace | Sizes are computed from M, topk, N, K and activation width; simultaneous regions cannot overlap. Intended sequential aliases are checked. GEMM output cannot overlap its live direct or indirect inputs. |
| Eleven kernel pointers | Records shape, stride, dtype, storage offset, base/end, owner observation, device and source role, including absent bias/route pointers and the unused dense-weight table placeholder. Scales and A/C geometry must cover their actual kernel indices. |

Nonlocal -1 blocks retain the original zero-output branch; when enabled that
branch returns **before table access and dot-product work**. No route is clamped,
replaced or silently discarded, and no new zero fill hides invalid data.
The off kernel's arithmetic AST matches the original after removing only the
compile-time diagnostic branch. Synthetic on/off/baseline output bytes match
through the actual alignment, expert-apply, GEMM-wrapper and workspace Python
functions; native operations are CPU doubles in those tests.

Every check writes a flushed/fsynced JSONL row with rank, PID, device, phase,
values or hashes under `/screen/moe-boundary/rank*-pid*.jsonl` in the run mount.
Failures raise `BoundaryError` and create a shared STOP without overwriting
existing evidence. Readbacks require a clear same-boot watcher receipt no older
than three seconds, explicit queue synchronization, and a second latch check.
Synchronization/readback failures latch and prevent subsequent device work
through the diagnostic. Python's check/submission interval cannot make an
asynchronous kernel fault and filesystem latch atomic.

Torch storage spans are **not native USM registration, queue-context or
residency proof**. Receipts leave these unavailable, rather than manufacturing
an ownership pass. Fresh per-process allocation stamps are checked on compact
weights; other pointer ownership is explicitly recorded as first observation
of retained Torch storage. Even passing all checks clears only the checked
index/span/metadata invariants of hypotheses 1/4 for the observed call, not
hypothesis 3 or a native lifetime failure.

## Next authorized window, not run here

Use the exact [staging and window command](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/README.md#future-authorized-window-command--not-run-by-this-task)
after the coordinator resolves the fourth-incident halt and supplies fresh
admission. Production TP4/EP4 calibrate-load, boundary ON, unchanged official
FP8 weights/placement/MTP1/full 16-bit KV, **zero generation requests**; the
64-token startup profile including its normal MTP profile is the only forward.
No warmup or capture follows. Keep the watcher through one graceful stop and
305 seconds after verified exit; a five-minute shutdown bound never permits
a hard kill, retry, reset or automatic recovery probe.

Identity deltas versus attempt 8 are explicit in that runbook: diagnostic
manifest, checks/receipts and synchronizations; watcher and gap; eager execution,
graph mode NONE and warmup bypass. No topology, model, weight, precision,
placement, memory cap or allocator-policy change is hidden in the variant.
A complete four-rank first-GEMM completion can clear the checked invariants;
a pre-GEMM failed tensor invariant identifies the bad boundary. Watcher refusal,
fault before synchronized completion or missing receipts is inconclusive.
A full clean profile/stop/gap is still only a diagnostic result, not speed or
lossless-output evidence.

Validation used nice 19 and OMP/MKL/OpenBLAS threads 2. CPU tests cover each
invariant class, per-rank receipts, fault-before/during-sync/readback, off-path
output bytes, default-off behavior, exact patch/staging hashes, profile-only
admission, and watcher/stop/gap behavior. Temporary test directories were
removed automatically; no current-task scratch remains. The original incident
receipts, fault markers and sealed runtime files remain unchanged.
