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

In progress. Target range: rank1 [0,202240), rank0 [202240,248320).
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

GNU and Intel each pass two fresh full-vocabulary byte runs, three consecutive
input vectors, forced ties, signed zero, boundary IDs, infinities and NaNs.
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
runtime-mock,controller}.json`. Every-window startup and seals are next.
