# Multi-user preregistration: how many users at once still get exactly their solo answers (2026-10-04)

Written before the run. Runner:
[`../scripts/run-20261004-fp8-multiuser-campaign.py`](../scripts/run-20261004-fp8-multiuser-campaign.py).

## Why this, and why now

The single-user recipes are within a few percent of what the hardware allows
([sizing](2026-10-03-fp8-comm5b-result.md#where-the-27bs-remaining-speed-could-come-from-sized-added-2026-10-04)).
What has never been measured on the 27B FP8 is more than one user at a time; both package READMEs list it as
untested, and the one earlier screen (one card, two users, September 16) found speculation not output-identical at
two users.

Decoding here is limited by reading the weights from memory, not by arithmetic. A step that serves eight users
reads the same weights once. So total tokens per second should rise almost in step with the number of users, as
long as every user's answer stays exactly what they would have got alone. That last condition is the whole point:
a multi-user number counts only where it is lossless.

## What is measured

Two cards, the shipped image, 64 prompts, 128-token answers, each request once per pass, cache off.

| Stage | Server | Users at once |
| --- | --- | --- |
| `tp2-mtp0-s8` | no speculation, accepts 8 sequences | 1 (the oracle), then 2, 4, 8, twice each |
| `tp2-mtp5-s4` | shipped depth-5 speculation, accepts 4 sequences | 1 (the oracle), then 2, 4, twice each |

For every pass: how many of the 64 answers are token-for-token identical to the same request run alone on the same
server, and the total generated tokens divided by the pass's wall time.

## The rule

- A user count is **lossless** only if all 64 answers are identical to their solo answers in **both** passes.
- The result reported is the highest lossless user count and its total speed, per stage. A level with even one
  different answer is reported as not lossless, with the count.
- Speed is recorded, never a gate. Nothing is shipped or published from this run by itself: a multi-user profile
  would need its own acceptance through the package launcher.
- No server before or after, each server started once and stopped gracefully, no retry. A GPU fault line halts the
  run.

## Expectation, stated in advance

Without speculation, exact at 2, 4 and 8 users, with totals well above the single-user 34 tok/s and plausibly
above the single-user speculative 90 tok/s at eight users. With speculation, not exact at 2 users (as on one card in
September). If the no-speculation totals are large, the follow-up question is whether speculation can be made exact
under load; that is a separate campaign.

## Addendum, 01:30 EDT: the first pass was only a screen; the gate is rerun with 64 answers per level

The first run (`/mnt/fast-ai/bench-results/fp8-multiuser-20261004`) sent only as many requests as there were users,
so "exact" there means 2 of 2, 4 of 4 and 8 of 8 answers. That is a look, not a gate. What it showed, both passes:
without speculation 65 / 125 / 234 tok/s together at 2 / 4 / 8 users; with depth-5 speculation 229 tok/s together
at 4 users; every answer in that small sample equal to its solo answer.

The gate run (`MU_MODE=gate`) sends all 64 prompts at once to a server that runs N of them together, twice, and
compares every answer both with the same server's one-at-a-time answers and with the frozen single-user
no-speculation reference (`fp8-comm2-20260917/tp2-ag-mtp0-ladder.json`). Servers: no speculation at 8; depth-5
speculation at 2, 4 and 8. The rule above is unchanged: a level is lossless only if all 64 answers are identical in
both passes.

## Addendum, 02:25 EDT: results so far, and one more preregistered run on the batch-invariant switch set

Results of the gate and scaling runs (64 answers per pass, two passes, shipped arithmetic):

| Server | Users | Equal to solo, pass 1 / 2 | Equal to the frozen single-user reference | Together |
| --- | ---: | --- | --- | ---: |
| no speculation | 8 | 64/64, 64/64 | yes | 237 tok/s |
| no speculation | 16 | 64/64, 64/64 | yes | **423 tok/s** |
| no speculation | 32 | 60/64, 58/64 | no | 656-676 |
| no speculation | 64 | 61/64, 58/64 | no | 876-917 |
| depth-5 speculation | 2 | 60/64, 61/64 | no | 136-140 |
| depth-5 speculation | 4 | 61/64, 61/64 | no | 227-239 |
| depth-5 speculation | 8 | 57/64, 61/64 | no | 335-363 |

So on the shipped arithmetic, **no speculation is lossless through 16 users at 423 tok/s together**, and speculation
is not lossless at any user count above one.

One bounded arm then turned on the batch-invariant switches the image already carries (packed-serial FP8 linear,
serial-exact GDN speculation, serial verify attention, batch-invariant LM head and RMSNorm, FP16 class pad) for
depth-5 speculation at 4 users: **64/64 equal to its own solo answers in both passes, 163-169 tok/s together**, but
59/64 against the frozen reference. The second number is the wrong comparison, by this lab's own rule: those
switches change the rounding order, so that arithmetic has to be judged against its own no-speculation answers
(AGENTS.md, campaign rule 2), not against answers produced by the shipped arithmetic.

**The run that settles it (`MU_MODE=invariant`), written down before it starts:**

1. `inv-mtp0-s64`: switches on, no speculation, 64 users. Its one-at-a-time answers become the reference for this
   arithmetic. Also: are all 64 answers still equal to solo with 64 users at once?
2. `inv-mtp5-s1`: switches on, depth-5 speculation, one user. Strict suite twice and the 64-prompt ladder against the
   reference from step 1: is speculation lossless on this arithmetic, and what does one user get?
3. `inv-mtp5-s8`, `inv-mtp5-s16`: the same with 8 and 16 users.

A level counts as lossless only if all 64 answers equal the step-1 reference in both passes. This is the same
precision as the shipped recipe (FP8 weights, FP16 activations and KV); only the order of rounding differs, which
is why it needs its own reference. No further arms after this: if speculation is not exact against its own
reference, the next step is an operator census, not more switches.

## Addendum, 04:35 EDT: long prompts are not exact at any width; one preregistered fix, the pure-step overlay

Long prompts (2K-8K tokens, 64 requests, two passes), shipped arithmetic, no speculation: 4 users 63 and 62 of 64
equal to solo; 8 users 63 and 58; 16 users 60 and 61; 16 users with the batch-invariant switches 60 and 61 (and
three times slower). The same few tie sites flip (`prose2k` at token 93 or 100, `code6k-c060` at 3, `code2k-c001` at
1, `docs6k-c021` near 100), and which ones flip changes between passes at the same width, so it depends on which
requests happen to share a step.

**Hypothesis:** a lone request's steps are pure (its prompt chunks alone, then its decode rows alone). With several
users the scheduler mixes one user's prompt chunk with other users' decode rows, shortens chunks by the tokens the
decodes use, and can put two prompts in one step. Each of those changes what shares a kernel call with a row, and
on this lane that moves the last bit.

**Test (`MU_MODE=longsweep MU_PURE=1`):** overlay
[`../overlays/b70-exclusive-prefill/`](../overlays/b70-exclusive-prefill/) makes every step either one request's
prompt chunk alone (full token budget) or decode rows only, alternating; no arithmetic changes. One server, no
speculation, 16 sequences: the long-prompt suite, then the short ladder against the frozen reference.

**Rule:** the overlay is a fix only if all 64 long-prompt answers equal their solo answers in both passes **and**
the short ladder is still 64/64 against the frozen reference in both passes. Speed is recorded. If long prompts are
still not exact, the mixing hypothesis is wrong or incomplete and the next step is the operator census at decode
widths with long contexts, not another overlay.

## Addendum, 05:00 EDT: pure steps took long prompts from 60-61 to 63 of 64; the census names the last cause

Pure-step overlay, 16 users: long prompts 63/64 in both passes (was 60 and 61), the short ladder still 64/64 against
the frozen reference, 374 tok/s together on the short ladder (423 without the overlay). The one remaining miss is the
same request both times: `code6k-c060`, token 3. So mixing was most of it, not all of it; by the rule above the next
step was the census.

**Census** (`qwen38-fp8-kernel-batch-invariance-census.py`, shipped R310 image, the recipe's environment, one card;
`../data/2026-10-04-fp8-multiuser/census/census.json`): every body GEMM (attention q/k/v and output, GDN in and
out, MLP gate-up and down) is bitwise row-invariant across all tested row counts from 1 to 512, position-invariant
and repeat-deterministic. **One kernel is not: the LM head.** Row results are identical for 1 to 4 rows and differ
by one ulp (6.1e-5) from 5 rows up, in classes {1-4}, {5-8}, {12-48}, {59-128}, {256}, {512}. A lone user is in the
first class; five or more users decoding together are not.

**Test (`MU_MODE=longsweep MU_PURE=1 MU_HEAD_ROWS=4`):** the pure-step overlay plus
[`../overlays/b70-lm-head-chunk/`](../overlays/b70-lm-head-chunk/), which feeds the head at most four rows per call
so every call is in the single-user class. Same server shape, same two suites, same rule: both passes 64/64 on long
prompts and 64/64 against the frozen reference on the short ladder. Expected cost: three extra head reads per step
at sixteen users, about 3 ms of a 38 ms step.

## Addendum, 05:40 EDT: head chunking alone did not fix the last miss; a long-key census names a third cause

Pure steps plus the head fed four rows at a time: long prompts still 63/64 in both passes, the same request
(`code6k-c060`, token 3) and the same wrong token every time; short ladder 64/64 against the frozen reference at
325 tok/s together. A deterministic miss is not a scheduling race. Censuses on the shipped image, one card
(`../data/2026-10-04-fp8-multiuser/census/`):

- token selection (`argmax` with planted exact ties): the same pick at every batch size from 1 to 64;
- the GDN decode kernel and the attention decode kernel at key lengths of 40 to 229 tokens: batch-invariant (this
  is the September R151 census, rerun);
- **the attention decode kernel at long key lengths (new script
  `../scripts/qwen38-fp8-fa-decode-longkey-batch-census.py`): not batch-invariant.** With keys of 1.6K to 8.2K
  tokens, one sequence of four, seven of eight and thirteen of sixteen get an output that differs by one ulp from
  their single-sequence call; with sixteen sequences all 6,524 long, every one differs from four sequences up. A
  single sequence's output also changes when the call is given a larger `max_seqlen_k` than its own length.

**Test (`MU_PURE=1 MU_HEAD_ROWS=4 MU_FA_PER_SEQ=1`):** a third overlay,
[`../overlays/b70-fa-decode-per-seq/`](../overlays/b70-fa-decode-per-seq/): when the longest key in a multi-sequence
decode call exceeds 229 tokens (the longest length proven invariant), issue one call per sequence with that
sequence's own length. Same server, same suites, same rule. If this is still not 64/64 on long prompts, the lane
stops here and the remaining difference goes to a per-layer trace on the one known request, not to a fourth guess.

## Addendum, 06:30 EDT: three overlays pass through 64 users; next question, speculation under load

Results: with the three overlays, speculation off, long and short suites are 64/64 in both passes at 16 users (two
fresh servers, 325 tok/s together), 32 users (428) and 64 users (488), all exact against the frozen reference.

**Next, written down first:** the shipped depth-5 speculation with the same three overlays, at 4 users, then 8.
The attention overlay was extended so that a verify step for several requests is split per sequence and each
sequence then goes through the verify-rows overlay exactly as a lone user's does (CPU tests updated). The
speculative GDN kernel has no working census on this image (the September script's kernel signature is out of date),
so this is a direct endpoint test, one arm.

**Rule:** speculation under load counts as lossless only if long prompts and the short ladder are both 64/64 in
both passes and the short ladder equals the frozen no-speculation reference. If it is exact, the number to beat is
the speculation-off total at the same user count. If it is not, speculation stays single-user only and the lane
closes here: no further arms without first rebuilding the speculative-kernel census for this image.

## Addendum, 06:30 EDT: the speculation-under-load test did not run

The 4-user server faulted card `0000:e3:00.0` at weight load (06:25:28 EDT), before any request. It was the second
fault on the boot, so GPU work stopped. Nothing was measured; the question is still open and the rule above is
unchanged. [Incident note](2026-10-04-gpu-fault-mtp-start.md). After a reboot, run
`experiments/qwen38-27b-b70/scripts/run-20261004-fp8-mtp-under-load.sh`.

## Addendum, 06:40 EDT (written with the cards off limits): one logits exchange per step

**Observation, from the image's source.** `compute_logits` is the per-rank output-layer product followed by one
card-to-card all-gather of the logits. The output-layer overlay chunks `compute_logits`, so at 64 users it pays
sixteen exchanges a step where a plain server pays one. The census timed the product itself at 1.1 ms per call per
rank; the measured cost of chunking at sixteen users was 6.5 ms a step for three extra calls, about 2.2 ms each. So
roughly half the cost of being exact here looks like the exchange, not the product.

**Change.** `B70_LM_HEAD_CHUNK_AT=head` moves the chunking inside, to the per-rank product
(`LogitsProcessor._apply_head`), only while `compute_logits` is running. The head sees exactly the same calls of at
most four rows; the chunks are joined on the rank; the logits cross the cards once. No arithmetic changes, and the
gather copies bytes. CPU tests pass in the image.

**Test, one arm per width, after the speculation test:** speculation off, three overlays, `MU_HEAD_AT=head`, at 64
users and then 16 (`MU_MODE=longsweep MU_PURE=1 MU_HEAD_ROWS=4 MU_HEAD_AT=head MU_FA_PER_SEQ=1 MU_SEQS=64`).

**Rule.** It must be 64/64 on long prompts and the short ladder in both passes and equal to the frozen reference,
like the mode it replaces. If it is, the number to beat is 488 tok/s together at 64 users and 325 at sixteen;
expected about 540 and 345. A gain under 2 % at 64 users means the exchange was not the cost and the mode is
dropped. If it is not exact, it is dropped without a second arm: the mode it replaces stays.

## Addendum, 11:00 EDT: both tests ran; both answers are no

Run after the owner chose a health check over a reboot (passed 09:40 EDT). No GPU fault during either.

| Test | Result | By the rule written above |
|---|---|---|
| Speculation with 4 users (depth 5, three overlays) | **Not lossless.** Long prompts 12/64 and 19/64 equal to solo; short ladder 6/64 and 4/64; 182 tok/s together. The solo pass is 64/64 against the frozen reference, so one user is unaffected. | Speculation stays single-user only. The lane is closed: no further arms without first rebuilding the speculative-kernel census for this image. The 8-user run was skipped as the rule says. |
| One logits exchange per step (`MU_HEAD_AT=head`), 64 users | Lossless (64/64 long and short, both passes, exact against the frozen reference), **489.3 tok/s** against 488. | A gain under 2 %: the exchange was not the cost. Dropped. |
| Same, 16 users | Lossless, **325.7 tok/s** against 325. | Same. Dropped. |

So the cost of the four-rows-at-a-time output layer is the repeated product itself, not the card-to-card exchange.
The remaining route to a faster wide mode is a row-invariant output-layer kernel, which is a kernel build.
Data: `data/2026-10-04-fp8-multiuser/{three-mtp5-s4,headlocal-s64,headlocal-s16}/`.


## Addendum, 14:40 EDT: the wide mode on the image's batch-invariant arithmetic

**Why.** With the shipped arithmetic, staying exact at 64 users costs the output layer sixteen calls a step (488
tok/s together). Last night's screen of the image's own batch-invariant switches (output layer padded to one row
class, so one call for any number of rows) ran 64 users at **857 to 865 tok/s** with speculation off, but only 54 of
64 answers matched solo. That screen had neither the pure-step overlay nor the per-sequence attention overlay,
which are the two fixes found later for exactly that kind of miss.

**What this arithmetic is.** Same weights, same 16-bit precision, nothing quantized further. It rounds the output
layer in a different (fixed) order, so a lone user's answers differ from the shipped recipe's at exact ties (9 of 12
on the strict suite). It is therefore its own reference: the claim to test is "every user gets exactly what a lone
user of this same server gets", not equality with the published single-user recipe.

**Test.** `MU_MODE=longsweep MU_PURE=1 MU_FA_PER_SEQ=1 MU_INVARIANT=1 MU_SEQS=64` (no output-layer chunking), long
suite and short ladder, two passes each. First the ceiling run already started at 14:34 (shipped arithmetic, same
overlays, no chunking) to know what the scheduling overlays alone cost at 64 users.

**Rule.** Lossless means 64/64 equal to solo on long and short prompts in both passes. If it is, the number to beat
is 488 tok/s; a second fresh server confirms before anything is claimed. If it is not 64/64, the misses go to the
kernel census (which switch is not row-invariant at 64), not to more arms.

## Addendum, 15:30 EDT: results of the two 64-user runs, and the next test (class-padded output layer only)

Owner's rule, restated today in capitals: a result counts only if it is exactly lossless and deterministic **by
construction**, not because a suite passed.

| Run at 64 users (speculation off, pure steps, per-sequence attention) | Equal to solo, long / short | Speed, short / long | Counts as a result? |
|---|---|---|---|
| Shipped arithmetic, output layer in 4-row calls (this morning) | 64/64 x2 / 64/64 x2, exact vs frozen | 488 / 64 tok/s | **Yes**: every call has a lone user's shape |
| Shipped arithmetic, output layer not chunked (14:36) | 64/64 x2 / 64/64 x2, exact vs frozen | 630 / 66 tok/s | **No.** The output layer runs as 32-row pieces, a different rounding class from one row (census). It passed; it is not exact by construction. A ceiling measurement only |
| All of the image's serial-exact switches (15:00) | 64/64 x2 / 64/64 x2; 59/64 vs frozen (its own arithmetic) | 593 / 20 tok/s | Deterministic, but three times slower on long prompts and a different reference. Not adopted |

Reading the image (CPU): `VLLM_XPU_LM_HEAD_BATCH_INVARIANT` is not referenced anywhere in R310; it does nothing.
What exists is `VLLM_XPU_FP16_LINEAR_CLASSPAD=1` (`vllm/model_executor/layers/utils.py`): at load it takes a census of
the FP16 linear at each weight shape, picks one row class that is position- and pad-invariant, and pads **every**
call, a lone user's included, into that class. With it the output layer is row-invariant by construction, in one
call, for any number of users. The default without it is 32-row pieces, which for this head is not the one-row class.

**Next test: class-pad only, everything else shipped.**
1. `MU_MODE=longsweep MU_PURE=1 MU_FA_PER_SEQ=1 MU_CLASSPAD=1 MU_SEQS=64`: long and short, two passes.
2. `MU_MODE=classpad`: one user with the same switch: its no-speculation answers, then depth-5 speculation
   against them, strict twice.

**Rule.** (1) must be 64/64 equal to solo on long and short in both passes; expected about 620 and 65 tok/s.
(2) must be 12/12 and 64/64 against its own no-speculation answers, at the shipped speed within 1 % (90 tok/s).
The answers will differ from today's frozen reference at exact ties, because the output layer rounds in another
fixed order: same weights, same precision. If both pass, the choice is the owner's: adopt the class-padded output
layer as the one arithmetic for one user and many (new frozen reference, packages re-accepted), or keep today's
reference and stay at 488 until a kernel that reproduces the one-row rounding for any row count is built.
