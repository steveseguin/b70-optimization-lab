# Packet79: move the record-line draft to rank0

CPU-only preparation requested on October 17. Device output identity, acceptance
and speed are pending coordinator screens; the roughly 5% gain at 23/25 is a
projection from packet77, not a measurement.

The new `experiments/own-xpu-runtime/stage2/packet79-draft-rank0/` copies
packet75 sources, preserving packet70's wide64/draft-HC/batch rollback choices
and packet73/74 implementations in one binary. Existing packet, screen and ops
trees are frozen except the two requested new queue proposals.

Only the draft loader changes: rank0 gets 91,392 expanded Q6 head rows
(308,904,960 bytes), using the same head/draft kernels. Rank1 keeps the full
target head. Placement `0` explicitly selects target split24; it must never
inherit the old name's 22/26 default. `0-split23` selects 23/25. Control `1`
keeps 24/24 and rank1 draft. The existing asynchronous reverse handoff and
unchanged native verification/rollback remain in use.

Initial pull --rebase refused other workers' dirty files. Fetch confirmed
HEAD and origin/main identical; no other work was stashed or edited. Root free
space was about 24 GB, already below the general 50 GiB repository reserve.
This task uses the owner's explicit 1.2 GB build budget as its scoped storage
instruction; no existing evidence is removed. The first incremental GNU/SYCL
build passed, 110.7 MB logical build size. All unchanged kernel objects are
hash-bound copies from packet75; only entry-main was rebuilt. No GPU binary
was executed. An initial missing copied prototype include was fixed before
compilation; the missing include and its repair are recorded here.

Next: full production-shape post-load allocation mock, census-derived memory
admission, native reverse-handoff state-machine checks, GNU/Intel byte checks,
selection/import/admission tests, seals and temporary queue plans. All CPU
commands use nice 19, CPUs 8-15,24-31, python3 -B, stdin /dev/null and an 8 GiB
address-space limit. Compiles are serial. Device launches remain coordinator work.


## Sealed CPU result

The full post-load mock passes 12 cases: three placements, two ranks, two HC
choices. Private rank0 head allocation is exactly 308,904,960 bytes. Rank0 uses
30,222,908,446 bytes at 23/25 (1,989,346,274 bytes within the arena) and
31,348,663,690 bytes at 24/24 (863,591,030 bytes within the arena). After the
unchanged planning reserves, its separate physical-capacity margins are
3,972,888,862 and 2,847,133,618 bytes. Driver residency remains unmeasured.

Twelve fresh candidate miniature executions match packet75 target tokens,
96 target fixtures per run, draft proposals and final draft states. Both
compilers pass two fresh executions of 90 selected operator cases per HC view.
Both also pass two fresh native-controller mock runs, each covering 20 cases
across both draft ranks: all hits, all misses, mixed, no proposal, rollback and
EOS, with delayed callback publication. All kernels and kernel objects remain
byte-identical to packet75. Only the host prefix loader changed.

All 75 Python checks passed, including the actual native selection consumer,
closed worker imports, all six sealed placements and the real shared lane
admission tests. All 12 real shared-wrapper view/lane plans and the two proposed
queue plans pass. Lane A is 1 / 0-split23 / 0 / 1. Lane B selects only the exact
A winner that beats both controls. Neither proposed job entered the live queue.

The final logical build is181,393,586 bytes; the main build's maximum child RSS
was 709.4 MiB. Generated build files were removed from Git tracking without
removing their local bytes. The 4 MiB rope input is deliberately retained with
restore hashes. Root disk free space was already below the general reserve;
no cleanup or settings change was attempted. No GPU, model weights, services,
sudo, host setting changes, resets or reboot were used.

[Final verification](../experiments/own-xpu-runtime/stage2/packet79-draft-rank0/evidence/final-check.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet79-draft-rank0/CPU-PREPARATION-CLOSEOUT.md),
[coordinator commands](../experiments/own-xpu-runtime/stage2/packet79-draft-rank0/WINDOW.md),
[laneA proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p79-A.txt),
[laneB proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p79-B.txt).

The screens still need GPU execution by the coordinator. Real packet49 output
identity, acceptance and speed remain pending. A screen is not a record:
the 512-token final suite and complete chain remain separate gates.

## Device result and closeout (coordinator, 2026-10-17 22:56–23:09 UTC, lane A; from the hourly review 10 readout)

All screens were exact. Against the rank-1 24/24 production control at 54.11 tok/s:

| Placement | tok/s | Change |
|---|---:|---:|
| Draft on rank 0, 23/25 | 52.86 | −2.3% |
| Draft on rank 0, 24/24 | 53.40 | −1.3% |

Hit cycles barely moved (16.14 and 15.95 ms vs 16.12). Misses got about 2.1 ms worse (29.7 vs 27.6 ms).

**Closed.** The draft needs rank 1's final hidden state, so placing it on rank 0 adds a transfer and serialization to every miss. Packet 45 had already measured placement on rank 0 as a loss (38.16 vs 39.42). The "+5%" projection ignored that dependency and the ledger. DO-NOT-REPEAT.
