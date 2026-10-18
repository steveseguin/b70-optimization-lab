# Packet131 capture census: 24/24, bundle7, context4096

This is a CPU execution of the production constructors and allocation ledger,
with numerical device addresses and no model-payload reads. It establishes
allocation sizes and command bindings, not driver residency or GPU timing.
`evidence/census131.json` retains every source, six position classes, both ranks
and both choices; `capture-extents.csv` lists every source individually.

| Rank0 snapshot component | Extents | Bytes copied per cycle, control | Candidate |
| --- | ---: | ---: | ---: |
| GDN recurrent BF16 matrices | 18 | 28,311,552 | 0 |
| GDN convolution BF16 histories | 18 | 1,105,920 | 0 |
| PLE convolution BF16 history | 1 | 184,320 | 0 |
| QSA current K/V/raw/pooled rows | 24 | 15,360 | 15,360 |
| Other plan outputs and mutable controls | 951 | 6,933,332 | 6,933,332 |
| Standalone runtime buffers | 9 | 12,076,948 | 12,076,948 |
| Total | 1,021 / 984 | 48,627,432 | 19,025,640 |

GDN layers are 0,1,2,4,5,6,8,9,10,12,13,14,16,17,18,20,21,22.
Each `blk.N.gdn.state` is 48 × 128 × 128 × 2 = 1,572,864 bytes.
Each `blk.N.gdn.history` is 10,240 × 3 × 2 = 61,440 bytes.
`blk.1.ple.history` is 10,240 × 9 × 2 = 184,320 bytes.

QSA layers are 3,7,11,15,19,23. Each has keys and values of 4,194,304
bytes each, raw state of 1,048,576 bytes and pooled state of 262,144 bytes.
Only the overwritten row is copied: 1,024 bytes each for K/V, 256 bytes each
for raw/pooled. Offsets are position × row-size, except pooled uses
floor(position/4) × 256. All older committed rows stay untouched. Positions
0,3,4,31,32,4095 have the same capture payload, with checked changing offsets.

The nine standalone captures are parallel controls 12; attention scores
196,896; attention probabilities 196,896; layer outputs 983,040; prepared FP32
input 696,320; GEMV workspace 8,388,608; compact routes 120; ordered mixture
5,120; operator scratch 1,609,936 bytes. Scratch has a 268,435,456-byte
allocation, but only its proven writer extent is captured. Every remaining
plan-buffer name and extent is in the CSV, including small status/control
outputs and intermediate layer outputs. Host history/maps and the 65,536-byte
rank0 shared slot are preserved separately by the unchanged snapshot protocol.

## Why capture costs time

The 1,021 checked copy extents are flattened into **one descriptor upload and
one compute submission**, not 1,021 device copy commands. Both choices retain
two submissions. The flat kernel uses 4-KiB workgroups with 256 lanes;
each lane searches the descriptor ranges and copies up to 16 bytes.
Control launches 12,525 groups (3,206,400 lanes); candidate launches 5,298
groups (1,356,288 lanes). Descriptor uploads are 32,672 and 31,488 bytes.
Of the control payload, 535 extents below 4 KiB hold
240,528 bytes; 466 below 1 MB hold 10,076,808 bytes; 20 large extents hold
38,310,096 bytes. The recurrent banks account for 60.87% of total bytes.

Packet128b measured about 0.523 ms for the capture **compute event** on both
hits and misses (`snapshot.capture.flat`), separately from host scheduling.
Its budget is diagnostic and currently reports an instrumentation-overhead
failure; it is a mechanism lead, not a production speed result. Dividing
48,627,432 bytes by that time gives about 93 GB/s of useful copied payload
(about 186 GB/s counting read plus write). This is accounting, not an isolated
bandwidth measurement. Inside that compute event, existing timing does not
separate descriptor searches, memory transactions and workgroup overhead.
It therefore cannot establish a bandwidth-only explanation. The snapshot
does create 1,021 guarded host copy descriptors, but it submits just one copy
kernel; hundreds of small device launches do not explain the measured event.
The candidate removes 29,601,792 bytes per cycle and 37 extents; it does not
claim a 0.523-ms saving. Only the proposed exact device bracket can measure it.

## Memory and exactness

The new private recurrent bank costs 29,601,792 bytes. Backup capacity falls
from 373,633,560 to 344,031,768 bytes, an exact offset. Descriptor allocation
remains 32,768 bytes. Net additional device allocation is **zero**.

Both choices allocate 28,144,182,388 bytes on rank0 and 31,425,985,242 bytes
on rank1. Headroom inside the 30-GiB arena admission limit is 3.7887 GiB and
0.7323 GiB respectively. Driver/pool headroom is not measured by this CPU test.
The source is the actual 24/24 constructors, not packet120's 25/23 estimate.

Two ordinary banks cannot preserve both the committed input and the previous
observable spare while a speculative step writes. The local packet62 path
therefore rotates a third physical bank: A/B/C → A/C/B before speculation;
a completed half swaps to C/A/B; a hit keeps it; a miss reverses the swap and
rotation to recover A/B/C. Full-overwrite proofs cover only recurrent/conv
destinations. Remaining mutable state retains the guarded flat copy. Request
reset and boundary cleanup include every private bank. Arithmetic is unchanged.
