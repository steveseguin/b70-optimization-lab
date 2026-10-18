# Packet109 — exact fusion of small target kernels

CPU preparation, started 2026-10-18 07:46 UTC, three-hour budget. Main at
638955b93a1d64068a423ba6866bd20276359f36 matched origin/main after fetch;
the requested pull refused because unrelated orchestration files are dirty.
Those files, all existing packet/screen/ops trees, and live queues are preserved.

The [census](../experiments/own-xpu-runtime/stage2/packet109-other-fusion/CENSUS.md)
reconciles all 636 rank0 and 628 rank1 launches with packet108. CPU capture
folds the device-only attention and split4 finish kernels; the source census
adds each explicitly. The raw artifact includes every command's exact bound
allocation sizes, logical dependencies and a labeled useful-byte count for
the small sites. Binding extents are not presented as memory traffic.

Two concrete candidates remove three launches per layer: append shared
activation after the existing single-workgroup route, and fuse shared down,
the ordered ten-expert mixture, and the shared blend. The exact current
packet103 selection is copied locally. The draft, quantization, KV and
target arithmetic stay unchanged. A runtime `other_fusion=production|fused`
choice uses one binary. Empty Sites stay in the capture plan.

Preparation has compiled both host and device programs without executing a
device. Real-shape startup captures production/fused/production/fused/production
on both ranks and preserves arena identities. It shows 72 fewer launches on
each half. This is a count, not a speed result.

The first byte gate caught NaN payload selection in the final shared blend.
The failed source and bytes are retained in `evidence/rejected-v1/`; the
second form is in `rejected-v2/`. Checking final GNU O3/native flags caught
further differences, retained in rejected-v3/v4. The fixture itself had
specialized the production reference at the call site. The final reference
now compiles the actual production NgHost separately with runtime shapes,
matching the engine. GNU's host implementation keeps the original complete
blend loop; Intel checks the fused row body used by the device source. No NaN
is canonicalized. Both compilers now pass 222 cases and 2,320,320 byte checks
per run, twice from fresh processes, including all BF16 encodings at the
activation and tail boundaries.

Both selections passed all eleven chain-window CPU startup paths, including
KD's actual host/device argument paths. Both ranks passed five-view recapture,
fresh-candidate capture equality and VRAM admission. Final seals and the
proposed lane-B bracket remain in progress. No GPU, service, host setting or
live queue changed.
