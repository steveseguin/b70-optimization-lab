# Laguna — width 16 and the fusion route are both closed

Date: 2026-07-26 America/Toronto

Best valid measurement this session: **100.524890** tok/s at width 12, 13/13
bitwise exact, 146/145 topology, against the approved record of 94.920039.

## The four measured configurations

| config | emitted/cycle | tok/s | derived cycle | exact |
| --- | ---: | ---: | ---: | --- |
| w8, record kernels, fusions on | 3.7010 | 94.8227 | 39.03 ms | 13/13 |
| **w12, record kernels, fusions off** | 3.9552 | **100.5249** | 39.35 ms | **13/13** |
| w16, widened kernels, fusions off | 3.9637 | 87.8994 | 45.09 ms | 0/13 |
| w16, widened kernels, fusions on | 15.9640 | 489.8884 | 32.59 ms | 0/13 |

## Width 16 is a dead end on cost alone

Against width 12 it buys **+0.21%** emitted per cycle for **+14.61%** cycle
time. Even with its exactness defect repaired it would land near 88 tok/s. The
geometric acceptance tail is spent by depth 11, and the wider verifier is not
free — a point every earlier projection got wrong by assuming flat cycle time.

Width 16 also fails exactness independently of the fusions: with them off,
acceptance decays normally (1156 → 30 across fifteen positions, 19.76%) yet
output is 0/13 against the q=1 teacher. So verification runs but produces the
wrong answer. With the fusions on it degenerates instead — 99.76% acceptance,
exactly 416 of 417 drafts accepted at every one of fifteen depths. Two distinct
defects, and neither is worth chasing given the cost result above.

## The fusion route is closed as a consequence

The exact fusion stack is worth a measured +4.2%, but it cannot reach the width
that matters. Its QKNorm/RoPE launcher maps work-groups onto whole heads, and
the **target** model has 48 attention heads and 8 KV heads, so per TP4 rank
`H = 12 + 2 = 14`:

| rows | rows x H | divisible by HEADS_PER_WG=16 |
| ---: | ---: | --- |
| 8 | 112 | yes |
| **12** | **168** | **no, remainder 8** |
| 16 | 224 | yes |

Width 12 therefore cannot use the fusion without re-indexing the kernel, and
width 16 is not worth reaching. An earlier version of this analysis used the
*draft* model's 72 heads and concluded width 12 divided cleanly; it does not.
The assertion added to the launcher is what surfaced this, rather than a partial
group silently dropping work.

Widening the kernels also cost **2.51%** at width 8 — 94.822732 down to
92.442386, with exactness and acceptance unchanged, so pure cycle time. Since
the widening now buys nothing, it has been reverted and the record binary
restored, hash `126da37b...`, with the leg's pin returned to it.

## What survives

Width 12 at 100.524890 stands. It was measured on the record binaries with the
fusions off, so nothing in this note affects it.

## The remaining route

The tree at width 12: projected 103.78 on the measured width-12 cycle, no kernel
changes, and its logic layer is already complete at 279 passing tests. The
outstanding work is the `write_slot` KV scatter and the drafter top-2 read.

Two candidates were rejected today for producing large numbers with wrong
output — draft graph capture at 198.7 tok/s and 95.91% acceptance, and width 16
with fusions at 489.9 and 99.76%. Both showed a nearly flat per-position
acceptance row, which is now a reliable tell that the check has stopped working.
