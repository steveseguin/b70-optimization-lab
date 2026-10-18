# Packet106: exact hit-only draft prefix split

Frozen source parent: packet105 commit
`339d7017a9dae0e65123a7d89803d54c56600d44`, after its GNU/Intel byte gates.
`copy-lineage.json` records the copied bytes. No parent source is edited.
Packet97e supplies every-window startup and the bounded host draft reference.

Keep the draft trunk and all 91,392 prefix rows resident on rank1. On a prior
verified hit only, rank1 computes [0,46336), rank0 computes [46336,91392).
No-guess, prompt, miss, terminal and ordinary host-reference paths keep the
complete production prefix. The controller passes an explicit confirmed-hit
flag; asynchronous/speculative command flags do not establish a hit.

Reuse packet105's pinned staging, release/acquire mailbox, 16-byte payload,
unchanged p33 expanded-Q6 row arithmetic and round2 BF16 argmax. Draft suffix
weights are a separate 152,289,280-byte allocation, with private hidden,
logits and scratch excluded from rollback. Combined target and draft splits
use distinct mailboxes and allocations. Each carries sequence and position.
Lowest global index wins ties, including signed zero. Any nonfinite row
prevents proposal publication; target verification remains unchanged.

For hits, export the draft's normalized final.mix after its last writer,
submit the short prefix, publish the completed export, and merge the suffix
before publishing the asynchronous draft reply. Rank0 services this request
while waiting for that DRAFT reply, after accepting its completed half. Misses
retain the original asynchronous command stream. Never wait for draft
publication while neglecting its suffix request.

Views: production, head-split, draft-split, head-split+draft-split. Use the
compute-queue transfer path first. Packet87t's +0.7749% is modeled, not measured;
the new host rendezvous can consume that gain. GNU/Intel row/proposal bytes,
ties/nonfinite cases, hit/miss controller mocks, actual transfer mocks, all
eleven startup windows and exact allocation admission precede seals.

First device proposal is one prompt / 64 tokens / combined candidate only on
lane B with fault review. Then B production / head-split / combined /
production, followed by a lane-A confirmation. These are proposals only;
CPU preparation starts no device, service or live queue.
