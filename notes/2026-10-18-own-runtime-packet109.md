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
fresh-candidate capture equality and VRAM admission. The final native reset
fixture passed both ranks twice, including poisoned mutable bytes and protected
weights. Two miniature five-view IPC repeats matched fresh parent/new-binary
references. The small fixtures explicitly use wide64 expert layout because
packet100 correctly rejects miniature shapes; real selected layouts are covered
by the full-shape and eleven-window checks.

Completed 2026-10-18, within the three-hour box. Native and wrapper seals pass,
including 127 wrapper tests. The [lane B proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p109-v5-B.txt)
passed planning in a temporary queue copy. It requests one loaded A/B/A/B/A
bracket, incident64 plus twelve 128-token prompts per view, with exact tokens
against the unchanged oracle. Expected runtime is at most 15 minutes and the
watchdog is 60 minutes. The build occupies about 94 MiB, below the 300 MB cap.

The next evidence is the actual engine screen. Device quality and speed are
unmeasured; 72 fewer launches per half is not a speed claim. Preparation used
no GPU, service, sudo or host setting changes, and did not change live queues.
See the [CPU closeout](../experiments/own-xpu-runtime/stage2/packet109-other-fusion/CPU-PREPARATION-CLOSEOUT.md)
and [preregistered screen](../experiments/own-xpu-runtime/stage2/packet109-other-fusion/PREREGISTRATION.md).
