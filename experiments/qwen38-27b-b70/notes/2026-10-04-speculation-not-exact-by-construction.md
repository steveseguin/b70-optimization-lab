# Speculation matches on every test, but its recurrent kernel is not bit-identical to plain decoding (2026-10-04)

## In plain words

The owner's rule is exact and deterministic **by construction**. Checked against that rule today, the single-user
recipe's drafting does not meet it yet:

- When the model checks drafted words, the recurrent layers use a "speculative" kernel. A direct census on the R310
  image shows that kernel is **not bit-identical to plain one-word-at-a-time decoding**: the first checked row
  matches, every later row differs in the last bit (at most 1.5e-5 on outputs, up to 4.9e-4 on the carried state).
- On every suite we have, the shipped depth-5 recipe still gives the same answers as no drafting (12 of 12, 64 of
  64, 8 of 8 long prompts, and the acceptance suites). So nothing published is known to be wrong. But it is exact
  **by test, not by construction**, and a tie could in principle fall the other way.
- The proof that it matters: checking nine copied words in one step (longer copy drafts) changed answers
  (11 of 12, 5 of 8, 55 of 64), while the same server without long drafts was exact. The longer the accepted run,
  the further the carried state drifts from plain decoding.

What **is** exact by construction today: everything with drafting off. That is the many-users mode (374 / 536 /
630 tok/s at 16 / 32 / 64 users) and one user without drafting (33.9 tok/s on two cards).

## The census

`scripts/qwen38-fp8-gdn-spec-batch-census.py` (repaired for R310 today), two-card shapes, one card.
Data: `data/2026-10-04-kernel-census/`.

| Question | Result |
|---|---|
| Do the first rows change with the number of rows in the verify (2 to 33)? | No: bit-identical to the 6-row call, outputs, states and conv line |
| Do requests in one call affect each other (1 to 64 requests of 6 rows)? | No: each equals itself alone, in any order |
| Is each verify row equal to the same token decoded alone, one token at a time? | **Row 0 yes; rows 1 and later no** (max 1.5e-5); prefix states differ from prefix 2 (max 2.4e-4 to 4.9e-4) |
| Is it deterministic? | Yes, every repeat identical |

The image has no switch for this: `VLLM_XPU_GDN_NATIVE_SPEC_*_SERIAL_EXACT` are not referenced anywhere in R310.

Also settled by census today (same data folder): the normalisation layers as the server compiles them are
row-invariant for 1 to 128 rows; paged attention decode is batch-invariant for contexts up to 1,645 tokens at up to
64 sequences (it is not at 6,524, which is what the per-sequence overlay handles).

## Longer copy drafts (K = 9), the run that exposed it

`MU_MODE=copydraft MU_COPY_K=9`, data `data/2026-10-04-copy-draft/fp8-copydeep-k9-20261004/`.

| Arm (same launch: synchronous, 9 verify slots, head at 5) | Strict | Long prompts | Short ladder | Long-prompt decode (median) |
|---|---|---|---|---:|
| Control, no long drafts | 12/12, 87.95 tok/s | 8/8 | 64/64 | 87.1 tok/s |
| Long copy drafts (249 placed, 4.02 of 9 accepted on average) | **11/12** | **5/8** | **55/64** | 110.0 tok/s (+26 %) |

The speed is real and matches the sizing. The answers are not exact, so it is not a result.

## What is being done

A kernel patch so the speculative path rounds its carried state exactly where plain decoding does, making every
verify row and every stored prefix state bit-identical to decoding one token at a time. With that:

1. the shipped single-user drafting becomes exact by construction (census: `rows_equal_decode` true for every row);
2. longer copy drafts become exact too, and the +26 % on long prompts can count;
3. drafting with several users can be tested again on a sound footing.

It needs a new image (R313, built from R310 plus the patch), the census, then the full gates and a speed check.
Until then the published single-user numbers stand as "identical on every test", which is what the packages say.

## R313: the patch works (19:45 EDT)

Patch `patches/vllm-xpu-kernels-gdn-spec-decode-exact-r313-20261004.patch`: in the speculative kernel, the state
carried into the next verify row is the same fp16-rounded value that is stored in the slot (eight lines). Image
R313 is R310 with only `_xpu_C` replaced (`data/2026-10-04-r313/`).

| Check on R313 | Result |
|---|---|
| Census, two-card and one-card shapes, 2 to 33 verify rows, three previous-accepted counts | **Every row and every prefix state bit-identical to one-token decode** (74 of 74 cases; on R310: 0). Row-count and batch invariance kept |
| Shipped recipe, strict suite twice | 12/12 and 12/12, 90.31 and 90.25 tok/s (R310 the same hour: 90.40 and 90.27). No cost |
| Synchronous pipeline, strict twice | 12/12 and 12/12, 88.00 and 88.11 tok/s |

So on R313 the recurrent layers' part of speculation is exact by construction. What still has no census for the
verify shape (6 rows against one row at a time): the attention kernel for verify rows at short contexts and the
recurrent layers' small FP16 projection. Those are next.

**Longer copy drafts are still not exact on R313** (same counts as on R310: 11/12, 5/8, 55/64, +25.8 % on long
prompts), so the kernel rounding was not their problem. The pattern in the answers is sharp: after a step that
accepts six or more drafted tokens, the second row of the following step is wrong. That points at something in the
engine or another kernel that mishandles more than five accepted tokens; it is being traced.


## Verify-path census and R314 (22:00 EDT)

**The two kernels that had no census** (`scripts/qwen38-fp8-verify-path-census.py`, 570 cases, on R313;
`data/2026-10-04-kernel-census/verify-path-*`):

| Kernel | Result |
|---|---|
| Attention, q verify rows against one row at a time, as the server runs it (verify-rows overlay, limit 8) | q up to 6 (the shipped verify): **identical at every tested context up to 6,524 tokens**, two-card and one-card shapes. q up to 10 needs the overlay limit raised to 10 (then identical on two cards; on one card there is a gap at 1,281 to 1,536 tokens). 17 rows is a different kernel and never identical |
| The recurrent layers' small FP16 projection, M rows against one | **Identical for 1 to 16 rows**; from 17 rows the server switches path and the rows differ from the one-row result |

So for one user the shipped six-row verify is now covered end to end on R313/R314: main layers, normalisation,
output layer, recurrent kernel (R313 patch), attention, and this projection.

**R314** = R313 plus three kernel lines (`patches/vllm-xpu-kernels-gdn-spec-state-row-stride-r314-20261004.patch`)
that let the engine hand the recurrent kernel a wider view of its state-slot table, used by the overlay
`b70-gdn-state-width`. That removes the out-of-range state read when a step is narrower than the tokens just
accepted (long copy drafts; the end of the context window in the stock recipe). On R314 with the overlay: recurrent
census 74 of 74 identical to decode; shipped recipe 12/12 twice at 90.30 and 90.34 tok/s; long copy drafts (K = 9)
12/12, 8/8, 64/64 and 98.6 / 105.8 tok/s on long prompts. Data: `data/2026-10-04-r314/`.

**A consequence for the many-users mode, found by the same census.** A decode step with 17 or more users puts 17
or more rows through that small projection, which then takes the other path, and its rows are not bit-identical to
a lone user's. So the many-users table is exact by construction only up to 16 users (419 tok/s); at 32 and 64
users (657 and 874) every answer has matched on every suite, but that is by test. The row-chunked path of that
projection is identical to one row for every row count up to 512 on two cards, so the fix is to keep decode steps
on that path whatever their size. It is being built.

**Drafting with several users is still wrong** (R314 with the state-width fix, 4 users: 7 and 5 of 64 short answers,
12 and 17 of 64 long ones). Last night without the scheduling overlay it was 60 or 61 of 64 at 2 and 4 users, so
the large failure comes from the pure-step scheduling overlay combined with drafting. Being traced.

## Correction, 22:40 EDT: the many-users mode is exact by construction at 32 and 64 users after all

The section above said the small FP16 projection breaks row-invariance from 17 rows. That was wrong for the server
as it runs. The census's "server" column had assumed the Python branch at 17 tokens is taken per step. The compiled
server evaluates that branch once, while tracing at the warm-up size of 4,096 tokens, and drops the guard, so **every
step uses the padded 256-row path, a lone user's one-row decode included**. Evidence: the compiled backbone graphs
saved by the servers (`cache/torch_compile_cache/*/rank_*/backbone/computation_graph.py`) contain 48 calls of
`qwen_gdn_ba_prefill_xpu` and no row-chunked call for this projection, in the many-users runs and in the
speculation runs alike (checked directly on three of today's servers; the helper agent checked 146 graphs, 145
the same and one with no such call). And the census itself shows the padded path bit-identical to the same row
alone for 1 to 512 rows, deterministic, on two-card and one-card shapes.

So this projection is covered for up to 512 rows a step, and the 32- and 64-user rows (657 and 874 tok/s) stand as
exact by construction. The "at least 17 tokens" limit on prompts sharing a step was justified by the same wrong
assumption; it is harmless and stays. The census script now defaults to the compiled path
(`--ba-server-path compiled`). An `--enforce-eager` launch would be different and is not covered.

## Drafting with several users: cause found (22:40 EDT)

A stock-engine bug that the pure-step overlay triggers on every prompt-only step. Under asynchronous scheduling
the worker resets each request's accepted-token count to 1 and restores the real count only for requests that were
in the immediately previous step. A request that sat out a step comes back with a count of 1, so the recurrent
layers start from state slot 0, a state missing the tokens it had just accepted. All 215 wrong answers in the saved
4-user run fit: each has, at or before its first wrong token, a skipped step right after a step that accepted two
or more tokens. Fix: overlay `b70-spec-resume-accepted` (keeps the count across a skipped step, on the device,
no extra sync; 11 CPU tests). A returning request still loses its drafts for one step, which costs speed but not
correctness. GPU test next.


## Drafting with several users is exact with the fixes (23:25 EDT)

Image R314, two cards, depth-5 drafting, 4 users, overlays: pure steps, per-sequence attention, state-width,
`b70-spec-resume-accepted` 0.2.0 (the first version saved the accepted count too late and never acted; this one
saves it before the worker drops the hidden request from its batch).

| Suite | Equal to solo | Together |
|---|---|---:|
| Long prompts | 64/64, 64/64 | 55.0 / 55.4 tok/s |
| Short ladder | 64/64, 64/64, exact vs frozen | 226 / 228 tok/s (about 57 each) |

Before the fix the same test gave 4 to 8 of 64. One fresh server so far. Still owed: a second server, other user
counts, and the comparison with drafting off at the same counts (a request that sits out a step still loses its
drafts for one step, which costs speed, not correctness). Data: `data/2026-10-04-r314/fp8-r314-mtp5-s4-resume2-20261004/`.
