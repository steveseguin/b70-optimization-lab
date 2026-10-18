# E3 linked compiler review

The final E3 path retains production's step/chain/j order. It carries two raw
eight-magnitude table words total, reusing the current wide code/high metadata
for the next chain. Only the block boundary needs a separate scalar lookahead.
There is no FP32 decoded bank, changed sum or reduction tree.

Linked offline BMG-G31 compilation includes the required SYCL device libraries,
using the same strict arithmetic flags as the engine. No device is opened.

| Static compiler observation | Production | Final E3 |
| --- | ---: | ---: |
| Configured GRF | 128 | 128 |
| Instructions | 1,993 | 2,055 |
| Load instructions | 51 | 56 |
| Scratch spill/fill instructions | 0 | 0 |
| Flag-to/from-register moves | 0 | 0 |

[Register report](register-report-offline.json) and
[schedule proof](evidence/linked-schedule.json) bind the compressed assembly.
Eight next-tile d32x2 table loads issue before current-tile arithmetic, with the
first destination waits after intervening FP32 multiply/add instructions. For
example, candidate assembly line 2032 issues the next table read with token 14;
its first destination wait is line 2362. The intervening code contains current
scale decode, weight multiplication and chain accumulation. The last tile does
not fetch beyond the row. The initial route read and initial table preload are
not counted as lookahead.

The counts are static code observations, including control-flow alternatives.
They do not measure latency, dynamic instruction counts, occupancy, DRAM traffic
or speed. The final extra five loads and 62 instructions remain a regression
risk to resolve with exact matched screens.

Earlier forms are retained, not screen candidates:

- `evidence/rejected-e3-all-next/`: all next-block words live together; 15,488
  bytes of scratch spills. Source and linked assembly retained.
- `evidence/rejected-e3-next-block/`: one next word at a time but every chain's
  current next-block word resident; 1,152 bytes of scratch spills. The inspector
  initially also saw stale prior dump names; the uniquely named latest assembly
  is retained separately. New censuses clear only this packet's archived dumps.
- `evidence/superseded-e3-scalar-metadata/`: two words total, zero spills, but 69
  loads and an early destination wait. Reusing wide metadata removed that wait
  from the current arithmetic path and reduced static loads to 56.

All refinements respond to CPU compiler evidence. No packet86 verdict, GPU
screen or speed measurement was used to select them.
