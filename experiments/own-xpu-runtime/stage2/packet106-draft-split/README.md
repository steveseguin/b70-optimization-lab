# Packet106: exact hit-only draft head split

CPU preparation of four views: production, target head split, draft prefix
split, and both splits. Source parent is packet105's committed byte-gated
revision `339d7017a9dae0e65123a7d89803d54c56600d44`, copied in `02654d2cd`.
`copy-lineage.json` retains that provenance. No parent tree is edited.

Rank1 retains the entire unchanged 91,392-row draft prefix. After a verified
hit it evaluates rows [0,46,336), and rank0 evaluates [46,336,91,392) from the
draft's normalized hidden vector. Misses, no-guess paths, prompt processing,
and the bounded KD host reference keep the complete prefix on rank1.
Distinct target/draft mailboxes and private scratch let both splits compose.
Target verification, weights, BF16 KV, per-row arithmetic and lowest-global-ID
argmax ties remain unchanged. Nonfinite rows abort publication.

All views use packet105's frozen baseline: route-fast, rec-both-plus,
wide64+halfcache, HC-wide and ordered retirement, with the production draft.
They do not silently inherit later packet103 selections. The target split
uses the committed compute-queue transfer implementation, not later uncommitted
packet105 changes. The draft exports its hidden vector before submitting the
short prefix and publishes it after that submission.

Both local suffix services restore their private active flag after request
reset. Without this, the shared reset would leave the suffix argmax inactive.
The actual-runtime mock checks that case and separate combined mailboxes.

Rank0 adds 152,289,280 weight bytes for the draft split and 155,750,400 for the
target split. With logits, controls and workspace the combined device delta is
311,148,608 bytes. The existing 30 GiB arena cap and 1.5 GB reserve stay fixed;
real driver residency still needs the device admission checks.

CPU gates and seals are in progress. Device output, deterministic repeat,
acceptance and speed are unmeasured. Packet87t's +0.7749% draft estimate is a
model projection, not a result; host rendezvous may consume the saving.

First device use is the proposed lane-B smoke: one incident prompt, 64 tokens,
combined candidate only, with the normal fault review and graceful drain.
Only a passing smoke permits the B production / target split / combined /
production grid. A then confirms the best exact improving B candidate between
fresh controls; incomplete or changed B evidence refuses execution. Draft
proposal sequences and acceptance counts must match production exactly.
No device work, services or live queue edits belong to this CPU task.

Run CPU preparation with `nice -n 19 taskset -c 8-15,24-31 python3 -B`, closed
stdin, 8 GiB address-space cap, and packet94's serial compiler turn. Keep build
scratch under 300 MB. Tests: `python3 -B -m unittest test_packet106.py`.

[Design](DESIGN.md), [work note](../../../../notes/2026-10-18-own-runtime-packet106.md).
