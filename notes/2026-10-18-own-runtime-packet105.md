# Packet105 — exact target head row split

## Scope and admission

CPU only, 3.5-hour box. Copied packet97 sources after the 97e fix; no old packet,
screen, live queue or orchestration edits. GNU and Intel builds serialize through
packet94’s compiler lock, nice 19, CPUs 8–15/24–31, 8 GiB address-space limit,
stdin closed. Build cap 300 MB. Records remain on lane A.

Initial `git pull --rebase` refused active unstaged orchestration files. Fetch
confirmed HEAD and origin/main identical; no stash or active-file mutation.
DO-NOT-REPEAT checks cover 79/87/88/93: do not move the draft trunk, invent
rollback overlap, or treat lane-B head results as lane-A confirmation.

## Implementation and gates

Target range: rank1 [0,202240), rank0 [202240,248320).
Expanded suffix weights require 155750400 bytes plus private scratch and logits.
The transfer request carries only the verified target final.mix (5120 bytes),
with position/sequence ownership; the return is 16 bytes. Tie rule is the lowest
global index after unchanged BF16 rounding. Any nonfinite logit prevents output.
The frozen parent orchestration outputs will not enter dependency seals.

## Implementation milestone

Both runtime binaries compile. The source copy is committed as `1800ef3a6`.
Three choices keep packet97's frozen selected target arithmetic: production,
head-split-compute, and head-split-bcs. Other choices are fixed to hc-wide,
half-cache experts, fast routing, ordered host retirement and rec-both-plus.
No changing parent selection or orchestration receipt will be sealed.

The existing p33 expanded Q6 kernel computes each row with exactly the same
products, adjacent reduction and BF16 rounding. The existing round2 argmax
reduces each partition. A new small kernel packs the 16-byte result; rank1
merges on the host using global IDs. Invalid partitions set sticky error and
publish no token (their internal diagnostic indices are not valid outputs).

Rank1 exports after final.mix's last writer completes. Rank0 services the
position/sequence-bound request only after its local half, immediately before
waiting for rank1. This works with a correct guess, a wrong guess, no guess and
EOS. The suffix never reads speculative streams and never writes target/draft
state. Its allocations are explicitly excluded from rollback, with a no-alias
check. There is no approximate selection or partial-max early exit.

BCS uses a dedicated copy-only Level Zero queue in the same owner/context,
explicit event dependencies and bounded waits. It refuses unavailable BCS
rather than silently relabeling compute-queue copies. Both variants write
per-leg host transfer timings and the backend/queue identity. GPU contention,
residency, outputs and performance remain unmeasured.

GNU and Intel each pass two fresh full-vocabulary byte runs, five input vectors
(three finite, one NaN and one infinity), forced ties, signed zero, boundary IDs,
infinities and NaNs.
Both compiler native-controller mocks pass hit/miss/no-guess/EOS. The actual
Runtime runs against payload-backed CPU mock owners, proving verified hidden
bytes, unchanged speculative state and stale/duplicate/cancel/peer-exit refusal.

The full startup census initially caught a category/lifetime mismatch, fixed
before device work, then exposed 1,572,128 bytes of unwanted private-scratch
snapshotting. The explicit auxiliary-allocation exclusion removes that copy.
All six actual allocation/capture checks now pass. Each split needs exactly
157,322,272 extra rank0 device bytes and saves 155,750,384 rank1 bytes. The
30 GiB arena cap and 1.5 GB reserve remain unchanged. This is allocation
admission only: the coordinator must still check real card residency and refuse
driver paging. No claim that a full card has free usable VRAM follows from this.

Evidence: `stage2/packet105-head-split/evidence/{cpu-byte-identity,full-shape,
runtime-mock,controller}.json`. The final refresh below completes startup and seals.

## Final refresh

Hidden export is now asynchronous: submit the prefix head before waiting to
publish the completed copy. This lets BCS overlap the prefix without exposing
unfinished bytes. `host_dependency_wait_us` includes the target producer wait;
it is not pure DMA latency. The queue identity and per-leg timing stay in the
screen artifacts. The chunked loader also checks the exact Q6 head shape.

The memory-plan base is copied locally, so the new seals depend on no mutable
parent selection or orchestration output. The refreshed six-view/rank census
passes. All 18 unsupported-layout refusals pass. Their harness initially
expected a lifetime-success message on a refusal, which this fixture never
prints; that mistaken assertion was removed. The waiting startup harness was
stopped before compilation and restarted against the corrected source closure.
No device process was involved.

## Completed CPU handoff

The actual loader now compares all 248320 expanded rows, independently rechunked
from their global source offsets, for both transfer choices. Both actual-runtime
mocks pass verified hidden bytes, unchanged state and stale/duplicate/cancel/exit
refusal. Every one of the 11 chain windows passes for all three views (33 total),
including the actual W0p host handshake and KD reference projection. Seven
admission/comparison tests pass and are bound into the seals. Startup took
302.83 seconds including its compiler wait; peak child RSS was 1250892 KiB.

Sealing first refused inherited fixture symlinks that resolved outside the
repository. Byte-identical local fixture copies and a copied small oracle
manifest resolve that containment problem without changing any gate bytes.
Only the needed static oracle links are retained; no parent orchestration
outputs enter the seals. The localization receipt records the file hashes.

All three view seals pass. Both new proposals pass five-job plans on temporary
queues, ten jobs total:

- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p105-B-grid.txt`
- `experiments/own-xpu-runtime/ops/lane-queue/proposed-p105-A-grid.txt`

Each grid is production / compute split / production / BCS split / production.
Each placement needs its own matched bracket; lane A independently confirms
and remains the record lane. No live queue was installed, and no GPU, service,
sudo, host setting or power setting was touched.

The build receipt records 286257140 bytes during the final build; removing
reproducible fixture entry objects leaves 278808437 bytes. All local compilation
used the shared turn lock. The CPU byte gate peaked at 978356 KiB RSS. Real BCS
availability/overlap, card residency, unchanged device output and speed are
still pending. There is no measured gain or device-ready claim.

The packet's [closeout](../experiments/own-xpu-runtime/stage2/packet105-head-split/closeout.md)
links all evidence and the remaining device gates.
