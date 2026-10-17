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
compilation; its failed attempt is retained in Git history/source provenance.

Next: full production-shape post-load allocation mock, census-derived memory
admission, native reverse-handoff state-machine checks, GNU/Intel byte checks,
selection/import/admission tests, seals and temporary queue plans. All CPU
commands use nice19, CPUs8-15,24-31, python3 -B, stdin /dev/null and an8 GiB
address-space limit. Compiles are serial. Device launches remain coordinator work.
