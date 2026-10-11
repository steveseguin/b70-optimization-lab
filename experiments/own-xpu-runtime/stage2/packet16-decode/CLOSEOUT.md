# Packet16 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can the packet13 full graph retain arithmetic
`iq3-p13-r234-sg32-split4-bf16-v1` while replacing scalar non-GEMV execution,
removing per-site waits, retaining compute weights across a sequential two-card
split, and preparing a whole-span decode measurement? This is the separate
Unsloth UD-IQ3_XXS quantized compressed model, not the FP8 Flash-Next authority.

## Outcome

See [cpu-tests.json](cpu-tests.json) for completed CPU counts and
[build-receipt.json](build-receipt.json) for host/native compilation, source
identities and binary hashes. **No device ran; no native speed or measured fit
is claimed.** The [window runbook](WINDOW.md) prepares W1 (card 3 streaming),
W2 (cards 2+3 resident frozen) and W3 (resident R5). Nothing launches or queues
a device window automatically.

Final-binary gates: 13/13 original integration cases in each non-GEMV mode;
150 arithmetic checks; 4 retirement and 7 deferred-chain checks; 21 window
protocol cases. Both frozen and R5 match 384/384 oracle layer hashes and 8/8
output tokens. All 48 first-step hashes and first token 332 agree. Twelve
additional R5 miniature cases and two wrong-fixture rejections pass. CPU
64-token coverage, native exactness, resident fit and speed remain untested.
The final builder verified unchanged source hashes across compilation and both
full CPU gates, then deleted completed CPU runs and compiler scratch.

## Mechanisms retained

The [main program](main.cpp) uses one owner/event ledger across two native
queues, direct peer copies, device-resident routing and token-boundary status
readback. [Parallel adapter](adapter.cpp), [dispatch](arithmetic.hpp),
[owner](owner.cpp), [window](window.py), [CPU gate](cpu_gate.py) and the bounded
builder are retained in this packet. Source and protected precursor identities
are bound by the build receipt. [Census](census.json) includes exact per-tensor
variant choices and planned per-card bytes; [review](review.md) records three
independent reviews and fixes.

## Failures and uncertainty

One CPU-only attempt was stopped before reaching final prompt fixtures to
switch to two numeric threads; it was not an output mismatch. Its
[receipt](cpu-interrupted.json) is retained. No device fault or recovery occurred
in this work. A second CPU R5 attempt was stopped once, before final
fixtures, to correct the planner-only expanded-split4 launch count and rerun
both gates on the final binary; [receipt](cpu-r5-interrupted.json). A third
just-started CPU attempt was stopped once to make a mismatching layer also
set oracle_exact=false; [receipt](cpu-finalization-interrupted.json). CPU parity uses a shared fixed arithmetic oracle, not independent
proof of the model equations. Device libm parity, cross-queue transport,
resident fit including driver/JIT overhead, 64-token native output and fresh
native repeat remain gates. Detailed timing caveats and launch/wait counts
are in README. R5 preserves measured per-shape reduction choices; a blanket
split4 conversion would change v1 and is not silently adopted.

The completed existing packet13 card 3 baseline admits W1, but its 48 step-1
layer fixtures all differ from the CPU oracle; first token 332 agrees.
[Read-only comparison](baseline-admission.json) localizes the first difference
to layer 0. This is an unresolved native arithmetic gate, not permission to
replace fixture equality with token equality. W1 optional CPU comparison
refuses; W2/W3 remain strict and may fail. No new device ran to investigate it.

## Next and revisit

The coordinator can separately admit W1, then W2/W3 only after W1 succeeds on
the same boot/binary. Preserve every receipt and first-eight step fixture set.
If any exact comparison fails, stop at its first differing layer/token and
localize with core/parallel and checked diagnostics; no tolerance is allowed.
After parity, measure the whole generated span and its fresh-process repeat.
Thousands of submissions, sequential use of the cards, packed-expert bandwidth,
head work and bounded host lookups remain candidates. Within-layer TP remains
packet14's separate work. [Do-not-repeat index](DO-NOT-REPEAT.md).
