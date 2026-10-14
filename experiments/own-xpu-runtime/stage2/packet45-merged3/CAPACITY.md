# Packet45 context capacity and placement

Arithmetic identity remains `iq3-p17-detmath-v2`. Capacities are 256, 4,096,
and 32,768. Cache capacity and valid positions are distinct: address strides
use capacity; reduction leaves and launch extents use admitted valid length.
Packet44's 32-position launch buckets, incremental pool update, prepared-site
refresh in both banks, and 32,768-position RoPE table remain authoritative.
All target and draft keys, values, raw indices and pooled indices stay BF16.

A QSA layer stores 1024 C key bytes, 1024 C value bytes, 256 C raw-index
bytes, and 256 ceil(C/4) pooled-index bytes: 2368 C bytes for all admitted
capacities. Per-layer totals are 606,208; 9,699,328; and 77,594,624 bytes.
Target plus draft has thirteen QSA caches. Selection stays at 2,051 IDs;
score/probability scratch stays at 2 * 24 * 2,051 * 4 bytes per owner.
The 32,768 * 128-byte RoPE table adds 3,670,016 bytes to each historical rank.

`--draft-rank 0` uses target layers 0–21 on rank0 and 22–47 on rank1.
`--draft-rank 1` retains target layers 0–23 and 24–47. Rank0 holds alternate
recurrent banks in both placements. The selected draft owner holds all draft
weights/cache/workspaces. Rank0 additionally holds an 839,321,600-byte copy of
the unchanged output head; rank1 always retains the target output head.

These are CPU allocation ceilings including explicit reserves, not observed
residency. The current live census must pass before the first model HALF.

| Draft rank | Capacity | Rank0 ceiling bytes | Rank0 free bytes | Rank1 ceiling bytes | Rank1 free bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 256 | 29,580,254,734 | 4,662,043,122 | 30,082,113,652 | 4,160,184,204 |
| 0 | 4,096 | 29,680,279,054 | 4,562,018,802 | 30,145,765,492 | 4,096,532,364 |
| 0 | 32,768 | 30,427,127,310 | 3,815,170,546 | 30,621,032,564 | 3,621,265,292 |
| 1 | 256 | 27,622,744,856 | 6,619,553,000 | 31,204,739,786 | 3,037,558,070 |
| 1 | 4,096 | 27,731,862,296 | 6,510,435,560 | 31,268,391,626 | 2,973,906,230 |
| 1 | 32,768 | 28,546,605,848 | 5,695,692,008 | 31,743,658,698 | 2,498,639,158 |

The lowest free allocation margin is 2,498,639,158 bytes, above the
1,500,000,000-byte floor. `memory_plan.py` generates every row;
`memory_gate.check(..., draft_rank=0|1)` selects capacity and placement.

Packet40's private image supersedes packet44's no-cache-shadow description.
It reserves complete rank0 QSA allocation tails and selected mutable scratch;
capture copies only uncommitted suffixes. At 32,768, its allocation is
701,213,368 bytes for 22 layers or 781,005,336 bytes for 24 layers. This image
is separate from alternate recurrent banks. Construct it before the provider,
so it never absorbs private draft state or pinned publication buffers.

Host memory is separate: each rank retains its 4 MiB pinned slab, the draft
owner adds 20,492 pinned bytes, and three shared IPC slots plus metadata use
200,704 bytes. Final streams transfer into the existing private draft hidden
buffer and add no device allocation. Draft head scratch is already counted.

Measured old target halves are 16.6 and 17.1 ms GPU time, with a 2.85 ms
draft. Using 16.6 / 24 = 0.691667 ms per moved source-rank layer, moving two
layers predicts 18.0667 ms for rank0 plus draft versus 18.4833 ms for rank1.
Moving one predicts a 0.9667 ms imbalance; moving two reduces it to 0.4167 ms;
moving three increases it to 1.8 ms. These are placement estimates, not new
measurements. New half times and driver residency require coordinator windows.
See [independent review](review-memory.md) for the exact allocation derivation.


## Packet45 storage admission, October 14 follow-up 2

The old 3,000,000,000-byte aggregate build limit is retained as the **base
build allowance**, not as the limit for binaries plus every device window.
All existing sealed artifacts and device-produced directories stay in place.
The merged chain needs a larger finite envelope; deletion is not its admission plan.

`storage.py` computes a worst-context nine-window chain at capacity 32,768,
13 requests (warm-up plus twelve prompts), and sixteen retained steps. Its
reservation is **11,486,186,752 bytes**. This deliberately sums each window's
peak reservation without credit for earlier cleanup. The structural build
ceiling is base allowance plus that chain: **14,486,186,752 bytes**.
Every admission rechecks `df -B1 /` and the actual aggregate build-tree size:

```
F = current filesystem free bytes; U = current build bytes; E = next write
R = 11,486,186,752; floor = 8,000,000,000
cap = min(14,486,186,752, U + F - floor - R)
require F - E >= floor + R
require U + projected_build_write < cap
```

An output outside `build/` has zero projected build growth, but reserves its
full filesystem write. Repeats, extra windows, and old retained chains never
raise the ceiling. Another complete chain remains reserved on disk even at
the end of a run. This is deliberately conservative; admission can refuse
when other work consumes space. It never lowers the 8 GB free floor.
At the reported failure, U=1,552,906,002 and F=31,558,537,216: the live cap is
13,625,256,466, and U+2,500,000,000=4,052,906,002 fits. The retained disk
headroom after that write is 29,058,537,216, above floor+R=19,486,186,752.

Model state reservation is `550,000,000 + 13*2368*(context-256)` bytes.
The thirteen full BF16 caches are the target's twelve plus the draft's one.
Strict rollback images are hashed in place by the inventory, not written as
another full cache dump. Per request reserve is 32,000,000 bytes for eight
retained steps, plus `2*48*20480` bytes (rank output and collected checker copy) for each additional retained step.
K0/W0p reserve 32 MB; K1a/K1b 1.1 GB; K2 2.5 GB. KD reserves
`550,000,000 + 3*2368*(context-256)` for the host reference plus two owners.
Suite RESET uses the same full state projection, including during rehearsal.
All three window admission sites use real projections in CPU rehearsal;
there is no 64 MB substitution, including for the filesystem check.

[Admission audit](ADMISSION-AUDIT.md) compares all twenty packet44 window
receipts and enumerates the remaining limits. The current 97 GiB host-memory
threshold exceeds the largest merged combined allocation/table bound by
13,774,577,010 bytes after pinned/IPC allowances. This is conservative planning,
not a measured claim about merged device residency.
