# b300 hunt (static, 2026-11-12 19:15; subagent read of tp104 = git HEAD = src104)

Question: does `OWN_PROMPT_BLOCK=300 OWN_PX=1 OWN_PX_BIG=1` (halves of 150; 3 host resets in 4 runs) touch card-to-card
memory out of range? **No out-of-range access found.** The failing config has the MOST headroom of any PX config.
Line numbers against tp104 (`mt.inc` = backend/backend_sycl_v41_mt.inc, `hpp` = backend/backend_sycl_v41.hpp,
`k` = kernels/sycl_v41.hpp). Formula script: scratchpad xrange.py (session scratchpad, not kept).

## Highest byte touched vs region end, half B

| exchange | 300 BIG (h=150) | 512 BIG (h=256) | 256 no BIG (h=128) |
|---|---|---|---|
| X1 output-a | 10,157,055 / 17,366,016 | 17,103,871 / 17,366,016 | 8,715,263 / 8,977,408 |
| X1 second region | 352,000 B left | 12,800 B left | 12,800 B left |
| pair swap | 217,986,175 / 246,871,168 | 245,773,439 / 246,871,168 | 124,400,767 / 125,498,496 |
| X2 / X4 | 23,510,015 / 28,015,616 | 27,851,775 / 28,015,616 | 14,220,287 / 14,384,128 |
| X3 expert act | 47,369,215 / 61,561,856 | 61,045,759 / 61,561,856 | 30,899,199 / 31,415,296 |
| X3 second region | 352,000 B left | 12,800 B left | 12,800 B left |
| engram pull | 123,001,855 / 168,057,856 | 166,419,455 / 168,057,856 | 83,844,095 / 85,482,496 |

Copy volume per card per pull at h=150: X1 3.8-4.1 MiB, X2/X4 2.44, X3 7.69, engram 48.9 (41.7 at 256, 83.4 at 512).
Flags (word 16*me <= 80) and poison (word 96) at fixed offsets; regions sized by mtba_n() (mt.inc:311-332); the arena
is one malloc_device allocation mapped by every card (hpp:1254, 3833, 3888-3900). No other PX-path kernel reads a
peer at an h-dependent offset (qb-off, xtail, XLL, K7 off in this run).

## What is unique to halves of 150 (all in range)
a. 150 runs the 129-256 class forms (k:3175) in token groups of 16 / 8: the last group computes 10 (or 2) spare
   tokens and stores none (k:2977, 3002). Half A's output-b / shared-down READ half B's slots 150-159 while X1(B) /
   X3(B) may be writing them (mt.inc:2215-2240): a harmless local race. Halves of 128 / 256 never do this.
b. Mix partials split exactly 25 tokens per card (ds_split, mt.inc:233); attention mix 13/12/13/12/50/50.
c. Engram kv pieces of 256 + 44 (mt.inc:1007-1016).
d. Half B's small per-token arrays leave 64-B alignment (still 16-B aligned); exchange regions stay 64-B aligned.
e. (Every config) the engram pull copies the whole block again at layer 14 (mt.inc:2199, 1412-1416): ~49 MiB per card,
   ~293 MiB over six cards at once, twice per block; dropping the second copy changes no value (a traffic lever).

## Untested separators (each risks a host reset)
Blocks of 288 / 312 / 316 (halves 144 / 156 / 158: a without b) or OWN_MT_DSPLIT=0 at 300 (b off).

## Not covered
Driver / runtime behaviour, compiled ISA, decode steps after the prompt, paths off in this run.
