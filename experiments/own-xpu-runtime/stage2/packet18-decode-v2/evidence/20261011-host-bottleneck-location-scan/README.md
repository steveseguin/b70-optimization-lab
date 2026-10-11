# Why two-card decode ran at 3 tok/s: a linear scan in the two-card backend (2026-10-11, 16:48–17:11 UTC)

Coordinator scratch builds of packet 18's sources (`stage2/scratch-p18-notiming`, not
sealed; patches here), run with packet 18's W3 command line on cards 2+3, R5 GEMV
variants, 64 tokens. Every run stayed bit-exact against the v2 oracle (the native program
compares 384 layer fixtures and all tokens itself) and left a clean kernel log.

| Scratch variant | ms per token | tok/s | host submit loop | waiting on GPU |
| --- | ---: | ---: | ---: | ---: |
| packet 18 as sealed (W3) | 315.2 | 3.15 | not separated | not separated |
| a: per-launch profiling queries removed | 300.2 | 3.32 | — | — |
| b: plus phase timers | 322.7 | 3.08 | 319.7 | 3.4 |
| d: plus ordered lookup in `tp2::Context::location` | **83.1** | **11.89** | 82.4 (incl. waits) | 40.8 |

1. Removing the per-launch timing queries changed almost nothing (315 → 300 ms). My
   earlier claim that they were two thirds of each token was wrong; I had inferred it
   from a count of queries instead of testing it.
2. Phase timers showed the host spent the whole token in its own submission loop and
   only 3.4 ms waiting for the cards: the GPUs were idle most of the time.
3. A sampling profile of the host thread ([perf-report-before-fix.txt](perf-report-before-fix.txt))
   put 83% of the time in `tp2::Context::location` and the tree iteration under it. For
   every pointer of every kernel submission the two-card backend checked which card
   owns it by walking the list of all allocations from the start (thousands of
   entries, ~17 pointers per launch, 2,181 launches per token).
4. Looking the pointer up in the ordered map instead ([patch](scratch-backend.hpp.patch))
   took the token from 300 ms to 83 ms: **11.89 tok/s**, exact.

After the fix the host loop and the cards each account for roughly half of the token
(about 41 ms waiting on the cards, about 41 ms issuing 2,181 launches at ~19 µs each).
The reference is 28.49 tok/s.
