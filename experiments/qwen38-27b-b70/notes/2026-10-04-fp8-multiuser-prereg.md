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

## Addendum, 17:10 EDT: the output layer is row-invariant up to 32 rows; the 4-row overlay was not needed

**Correction of this morning's reading.** The kernel census named the output layer as the one kernel that is not
row-invariant (classes 1-4, 5-8, ...). That entry ran the FP8 W8A16 kernel at the output layer's shape. The lane's
real output layer is an FP16 `F.linear`, a different kernel. Measured directly today:

- `scripts/qwen38-fp8-output-layer-row-census.py`, both cards, three random weight/input sets each: **every row of a
  1 to 32-row call is bit-identical to the same row computed alone**, in any position; 33 rows is the first size that
  differs. 64 rows as two 32-row pieces equals 64 solo rows bit for bit
  (`data/2026-10-04-fp8-multiuser/head-census/`).
- The image already runs FP16 linears in pieces of at most 32 rows by default (`VLLM_XPU_FP16_LINEAR_ROWCHUNK=32`).
- The class-pad switch's own load-time census on the real weights says the same: `1-32:c0 33-128:c1 129-320:c2`.

So with the default path every output-layer call is in the lone user's row class, for any number of users, by
construction. The `b70-lm-head-chunk` overlay (4 rows per call) bought nothing and cost 22 % at 64 users. This
morning's "necessary, not sufficient" was wrong: the miss it was blamed for was the attention kernel's.

| Run at 64 users (speculation off, pure steps, per-sequence attention) | Equal to solo | Speed, short / long | Status |
|---|---|---|---|
| Default output layer (32-row pieces), 14:36 | 64/64 x4, exact vs frozen | **630** / 66 tok/s | **Exact by construction.** The result; confirmation runs at 64, 32 and 16 users started 17:05 |
| Class-padded output layer (15:44) | 64/64 x4, exact vs frozen | 640 / 67 tok/s | Also exact by construction (its own census), but it moves a lone user to another row class; not needed |
| One user with class-pad (16:00) | 12/12 and 64/64 vs its own no-speculation answers; 12/12 vs frozen | 89.6 / 89.2 tok/s | Recorded; not adopted |
| 4-row output-layer overlay (morning) | 64/64 x4, exact vs frozen | 488 / 64 tok/s | Superseded |

## Addendum, 17:45 EDT: confirmation runs of the two-overlay mode

One fresh server each (64 users now has two), long suite and short ladder, two passes each, speculation off, pure
steps and per-sequence attention, default output layer. All exact against solo and against the frozen reference.

| Users | Long prompts equal to solo | Short ladder equal to solo | Equal to the frozen reference | Together (short / long) |
| ---: | --- | --- | --- | ---: |
| 16 | 64/64, 64/64 | 64/64, 64/64 | yes | 374 / 62.5 tok/s |
| 32 | 64/64, 64/64 | 64/64, 64/64 | yes | 536 / 66.1 tok/s |
| 64 (14:36) | 64/64, 64/64 | 64/64, 64/64 | yes | 630 / 66.4 tok/s |
| 64 (17:00) | 64/64, 64/64 | 64/64, 64/64 | yes | 629 / 66.4 tok/s |

Data: `data/2026-10-04-fp8-multiuser/two-overlays-s{16,32,64}/` and `ceiling-s64/`.


## Addendum, 18:15 EDT: several short prompts per prompt-only step

**Why.** In the two-overlay mode every new request gets a step to itself for its prompt. With 64 users and
128-token answers that is one prompt-only step for every two decode steps a request needs, an estimated 10 to 17 %
of the time on short prompts.

**Change.** `B70_EXCLUSIVE_PREFILL_BATCH=N`: a prompt-only step may take up to N new requests together when each
prompt fits whole and they fit the step's budget together. Each still has the single chunk it would have alone.
The prompt kernels then see several sequences in one call.

**Test.** `MU_MODE=longsweep MU_PURE=1 MU_FA_PER_SEQ=1 MU_PREFILL_BATCH=8 MU_SEQS=64`, long suite and short ladder.

**Rule.** This is a screen, not a result. The body GEMMs are row-invariant (census), but the attention and
recurrent prompt kernels have no census across sequences on this image. If any answer differs from solo, the
option is closed. If all are equal and the gain is 5 % or more, the prompt kernels get a census across sequences
before anything is claimed; under 5 %, it is dropped.

## Addendum, 18:35 EDT: screen of several prompts per prompt-only step (up to 8), 64 users

| Suite | Equal to solo | Together |
|---|---|---:|
| Long prompts (two prompts of 1,645 and 2,434 tokens can share a step) | **63/64**, 64/64 | 66.2 / 66.5 tok/s |
| Short ladder (31-token prompts, up to 8 per step) | 64/64, 64/64, exact vs frozen | **874 tok/s** (630 one at a time) |

**By the rule: not a result, and closed in this form**, because one long answer differed. But it splits cleanly:
the short prompts were all exact and 39 % faster; the miss is with long prompts sharing a step. So some
prompt-reading kernel is not batch-invariant across sequences for long sequences.

**Next, before any claim:** a census of the prompt-reading kernels across sequences (attention prefill and the
recurrent kernel's prefill path), by sequence length and count, in `scripts/qwen38-fp8-prefill-multiseq-census.py`
(being written). If it proves multi-sequence prefill bit-identical to solo up to some length, the overlay gets that
length as its limit for sharing a step (longer prompts keep a step to themselves), and the short-prompt speed
becomes a result by construction. If it shows no safe length, the option stays closed.
Data: `data/2026-10-04-fp8-multiuser/prefill-batch8-s64/`.

## Addendum, 19:45 EDT: several short prompts per prompt-only step, inside census limits: 874 tok/s at 64 users

**Census of the prompt-reading kernels across sequences** (`scripts/qwen38-fp8-prefill-multiseq-census.py`, 231
cases, `data/2026-10-04-kernel-census/prefill-multiseq-*`): attention prefill and the recurrent kernel's prefill
are bit-identical to reading each prompt alone in every case, up to 2,434 tokens and 16 sequences. The recurrent
layers' small FP16 projection is not, when a prompt has 16 tokens or fewer (it takes another code path once the step
holds 17 rows or more). The GEMM and normalisation censuses cover up to 512 rows in a call (normalisation extended
to 512 today, all invariant).

**Limits now built into the overlay:** prompts share a prompt-only step only if each has at least 17 tokens and the
step holds at most 512 tokens. Everything else is read alone, as before.

| 64 users, `B70_EXCLUSIVE_PREFILL_BATCH=8` with those limits | Equal to solo | Together |
|---|---|---:|
| Long prompts (read alone, as before) | 64/64, 64/64 | 66.4 / 66.6 tok/s |
| Short ladder (31-token prompts, eight per step) | 64/64, 64/64, exact vs frozen | **874 tok/s** (630 one prompt per step) |

Inside those limits every kernel on the path has a census, so this counts as exact by construction. One fresh
server so far; a second, and 16 and 32 users, are owed before it replaces the table.
Data: `data/2026-10-04-fp8-multiuser/prefill-batch8-limits-s64/`.

## Addendum, 20:40 EDT: prompt sharing inside census limits, confirmed at 16, 32 and 64 users

One fresh server each (64 users has two), long suite and short ladder, two passes each. All exact against solo and
against the frozen reference.

| Users | Long prompts equal to solo | Short ladder equal to solo | Together (short / long) | One prompt per step |
| ---: | --- | --- | ---: | ---: |
| 16 | 64/64, 64/64 | 64/64, 64/64 | 419 / 62.6 tok/s | 374 |
| 32 | 64/64, 64/64 | 64/64, 64/64 | 657 / 66.1 tok/s | 536 |
| 64 (19:38) | 64/64, 64/64 | 64/64, 64/64 | 874 / 66.5 tok/s | 630 |
| 64 (19:56) | 64/64, 64/64 | 64/64, 64/64 | 874 / 66.5 tok/s | 630 |

Data: `data/2026-10-04-fp8-multiuser/prefill-batch8-limits-{s64,confirm-s16,confirm-s32,confirm-s64}/`.


## Addendum, 23:30 EDT: user-count sweep with drafting on and off (written before it runs)

Drafting with several users is exact at 4 users with tonight's fixes (R314 kernel, state-width, resume-accepted;
see `2026-10-04-speculation-not-exact-by-construction.md`). Next: which is faster at each user count.

**Runs** (R314, pure steps, per-sequence attention, up to 8 short prompts per prompt-only step, both fixes on
everywhere so only drafting differs): drafting on at 2, 8 and 16 users (4 is done; repeated with prompt sharing);
drafting off at 2, 4 and 8 users (16, 32, 64 are done on R310).

**Rule.** Each run must be 64/64 on long and short prompts in both passes and exact against the frozen reference,
or it is reported as not exact and not used. The table then says, per user count, the faster exact mode.

## Addendum, 2026-10-15 14:40 EDT: second fresh server for every sweep arm (written before it runs)

The 23:30 sweep ran one fresh server per arm; the state-of-optimization pin
(`2026-10-05-state-of-optimization-pin.md`, item 4) owes a second. Same image (R314 state-stride,
`sha256:8b78916004ca...`), runner (`run-20261004-fp8-multiuser-campaign.py`, `MU_MODE=longsweep`), settings
(pure steps, per-sequence attention, prompt batch 8, state-width and resume-accepted fixes on) and clients as the first
sweep. Two changes, both stated in advance: the host-memory guard floor is the owner-approved 1.6 GiB (the first sweep
ran at the 2.0 default), and two arms are added: drafting on at 4 users with prompt batching (the first 4-user
drafting run had no prompt batch), and drafting off at 16 users on R314 (the first was on R310).

**Arms, in order:** drafting on at 2, 8, 16 and 4 users; drafting off at 2, 4, 8 and 16 users. About 2 h 20 min.
Gemma's LAN service is stopped first and put back on its throughput recipe at the end if the kernel log has no GPU
fault line. Wrapper: `scripts/run-20261015-fp8-r314-sweep-repeat.sh`.

**Rule.** An arm passes if it is 64/64 equal to solo on long and short prompts in both passes and exact against the
frozen reference. Its speed is reported next to the first server's. A failing arm is reported as not exact, the sweep
stops there, and the first-server table is marked unconfirmed for that arm.

### Result (14:35-16:56 EDT): every arm exact on the second server

Each arm on its own fresh server, long suite and short ladder, two passes each, all exact against solo and against
the frozen single-user reference (sequential, batch r1, batch r2: 64/64 each). Kernel log clean; Gemma restored.

| Users | Drafting | Short ladder, second server (pass 1 / 2) | First server | Long prompts together |
| ---: | --- | ---: | ---: | ---: |
| 2 | on | 137.10 / 137.05 | 138.10 / 137.29 | 49.4 / 49.8 |
| 4 | on (prompt batch 8) | 227.04 / 232.51 | 225.78 / 227.89 (no prompt batch) | 54.5 / 55.4 |
| 8 | on | 334.88 / 338.35 | 333.65 / 338.91 | 57.5 / 58.1 |
| 16 | on | 427.50 / 428.64 | 434.36 / 413.62 | 56.4 / 56.7 |
| 2 | off | 65.11 / 65.27 | 65.20 / 65.26 | 34.5 / 34.4 |
| 4 | off | 125.33 / 125.22 | 125.10 / 125.08 | 46.4 / 46.3 |
| 8 | off | 235.91 / 235.56 | 235.68 / 235.90 | 55.7 / 55.8 |
| 16 | off (R314) | 418.85 / 418.84 | 419.36 / 419.01 (R310) | 62.5 / 62.4 |

So the table stands: drafting is faster up to 8 users, the two tie at 16 (428 vs 419), and drafting off
wins from 32 up. Data: `data/2026-10-15-r314-sweep-repeat/` (campaign log and results per arm, the wrapper log, the
image id).

## Addendum, 2026-10-16 16:28 EDT: the same sweep with prefix caching on (written before it runs)

Campaign 24b/24c (`2026-10-10-context-16k-baseline.md`) found and fixed the bug that broke drafting with two users
once prefix caching was on (the accepted-token count lives on the CPU side in align mode; `b70-spec-resume-accepted`
0.3.0). The context lane's check was two users and agent-style prompts. This asks whether the multi-user recipe stays
exact with prefix caching at 2-16 users with drafting, and at 64 without, which is the practical profile for chat and
agents (repeated system prompts and earlier turns are not read again).

**Settings.** As the 2026-10-15 sweep (R314 state-stride image, pure steps, per-sequence attention, prompt batch 8,
state-width and resume-accepted fixes, 1.6 GiB guard), plus `MU_PREFIX_CACHE=1`: `--enable-prefix-caching
--mamba-cache-mode align`, `b70-prefix-cache-exact`, retention interval 6,656 tokens, and prompt steps of one cache
block (832 tokens instead of 4,096; hit == cold needs it). Long suite: the solo pass reads each prompt cold, the
batched passes hit the cache, so "equal to solo" here also means "cache hit equal to cold read under load". The short
prompts are under one block and never hit. `compare-ladder-oracles.py --allow-cached` lets cache hits through the
frozen-reference compare (tokens must still match); without the flag nothing changes.

**Arms, in order:** drafting on at 2, 4, 8, 16 users; drafting off at 64. One fresh server each. About 1 h 45 min.
Gemma stopped first, restored at the end if the kernel log is clean. Command:
`MU_PREFIX_CACHE=1 ARMS="1 2;1 4;1 8;1 16;0 64" TAG=20261016-pc scripts/run-20261015-fp8-r314-sweep-repeat.sh`.

**Rule.** As before: an arm passes if 64/64 equal to solo on long and short prompts in both passes and exact against the
frozen reference; a failing arm is reported as not exact and the sweep stops there. Speed is reported next to the
2026-10-15 numbers; the short ladder is expected slower at 64 users (832-token prompt steps), and the long-prompt
passes faster (cache hits).

### Result (16:29-16:45 EDT): NOT exact at 2 users; sweep stopped after the first arm

2 users, drafting on, prefix caching: short ladder 64/64 equal to solo in both passes (137.51 / 137.59 tok/s, the
same as without caching) and exact against the frozen reference. Long suite: pass 1 64/64 (87.5 tok/s together,
was 49.4 without caching: the repeats are read from the cache), **pass 2 63/64** (89.7 tok/s). The differing answer,
prose4k-c043, diverges at its second token ("#" instead of "["), and from there is token for token the answer of
prose4k-c003, a prompt that differs from it only in the runner's end marker ("case 003; variant 00" against
"case 043; variant 05"). Both had 1,664 tokens from the cache; the client sent the right prompt (hashes match). Every
other prose4k copy answers "[" alone and in both passes; c003 answers "#" cold and from the cache. So this prompt sits
near a tie between two openings and a small arithmetic difference flipped it: something in this setup is not the same
arithmetic as the solo answer. Prompt batching is not involved (it only groups prompts under 512 tokens).
By the rule the sweep stopped there (the 4-user arm was made to refuse to start); kernel log clean; Gemma restored.
Data: `data/2026-10-16-r314-sweep-pc/` (wrapper log), `/mnt/fast-ai/bench-results/fp8-r314-sweep-mtp1-s2-20261016-pc/`.

## Addendum, 2026-10-16 16:47 EDT: near-tie diagnostic for the prefix-cache flip (written before it runs)

A 1-in-128 flip is too rare to bisect with the normal suite, and logprobs are not an option on a drafting two-card
server here (over 1 GiB of host memory). Instead a near-tie detector: the long suite's prose4k prompt eight times
(`data/2026-10-16-r314-sweep-pc/near-tie-prose4k-x8-suite.json`), which the runner expands to 64 requests that differ
only in the end marker, so many sit near the "[" / "#" tie. Three fresh servers, 2 users, same image and fixes as the
sweep, long suite only (`MU_SKIP_SHORT=1`), three passes (`MU_LONG_REPEATS=3`):

| Arm | Drafting | Prefix caching | Prompt step |
| --- | --- | --- | --- |
| D1 | on | on (align, exact overlay, 6,656) | 832 |
| D2 | off | on | 832 |
| D3 | on | off | 4,096 (the 2026-10-15 recipe) |

**Reading.** Each arm reports answers different from its own solo answers out of 192. D3 is the control (the
2026-10-15 recipe was exact on 128 long answers twice); D1 repeats the failing setup with a more sensitive suite;
D2 says whether drafting is needed for the flip. No arm is a release gate. About 35 minutes. Wrapper:
`scripts/run-20261016-fp8-pc-multiuser-diagnostic.sh`.

### Result (16:48-17:22 EDT): no flip in 576 answers

| Arm | Drafting | Prefix caching | Passes equal to solo | Long tok/s together | From the cache per pass |
| --- | --- | --- | --- | ---: | ---: |
| D1 | on | on | 64/64, 64/64, 64/64 | 109.9 / 112.2 / 114.0 | 106,496 (1,664 each) |
| D2 | off | on | 64/64, 64/64, 64/64 | 56.0 / 55.9 / 55.9 | 159,744 (2,496 each) |
| D3 | on | off | 64/64, 64/64, 64/64 | 81.2 / 82.4 / 81.8 | 0 |

The detector was sensitive: the 64 solo answers start four different ways and 56 are distinct. Nothing was evicted
(258,236 tokens of cache). So the 16:36 flip did not come back with one prompt family; it is rare or needs the mixed
suite. Kernel log clean; Gemma restored. Data: `/mnt/fast-ai/bench-results/fp8-r314-D{1,2,3}-20261016-pcdiag/`,
wrapper log `data/2026-10-16-r314-pcdiag/diag.log`.

## Addendum, 2026-10-16 17:23 EDT: keeping a returning user's drafts, and the flip rate (written before it runs)

**Why.** With pure steps, every prompt step is a step the writing users sit out, and a user that sat out comes back
with placeholder drafts, so its first step back makes one token. The 2026-10-15 sweep's server logs show it: on the
long suite one user at a time averaged 4.1 tokens per verify step, 16 users 1.5-2.9, with ten-second windows at 1.00.
`b70-spec-resume-accepted` 0.4.0 adds `B70_SPEC_RESUME_DRAFTS=1` (off by default; off = 0.3.0): the drafts the drafter
made for a user at the end of its last step are stored when it sits out and written back, in the model's input and in
the rejection sampler's draft ids, when it returns. They are the drafts it would have been given had it not waited;
every output token is still the target's own choice (32 CPU tests).

**Arms** (one fresh server each, R314, the 2026-10-15 recipe: pure steps, per-sequence attention, prompt batch 8,
state-width and resume-accepted fixes, drafting on, no prefix caching, normal long suite and short ladder, two passes):

| Arm | Users | Drafts kept |
| --- | ---: | --- |
| R16 | 16 | on |
| R4 | 4 | on |
| P1 | 2 | off, prefix caching on: the 16:29 failing configuration again, normal long suite, three passes, long only |

**Rule.** R16 and R4 must be 64/64 equal to solo on long and short prompts in both passes and exact against the frozen
reference; otherwise draft keeping is not used and the reason is found first. Speed is reported next to the 2026-10-15
second-server numbers (16 users: long 56.4 / 56.7, short 427.5 / 428.6; 4 users: long 54.5 / 55.4, short 227.0 / 232.5)
with the mean acceptance length from the server log. P1 counts flips out of 192 to estimate the rate of the 16:29 flip;
it is not a gate. About 50 minutes.

### Result (17:26-18:07 EDT): draft keeping is exact and faster; the prefix-cache flip repeats

| Arm | Long prompts together, pass 1 / 2 | 2026-10-15 | Short ladder together, pass 1 / 2 | 2026-10-15 | Frozen reference |
| --- | ---: | ---: | ---: | ---: | --- |
| R16 (16 users) | 61.69 / 62.30 | 56.4 / 56.7 | **465.33 / 467.65** | 427.50 / 428.64 | exact (64/64 x3) |
| R4 (4 users) | 56.42 / 57.09 | 54.5 / 55.4 | 236.24 / 233.89 | 227.04 / 232.51 | exact (64/64 x3) |

Every pass 64/64 equal to solo on long and short prompts. The servers' speculation counters show why: both R16 and R4
drafted exactly 69,150 tokens and accepted exactly 33,498 over the whole run (oracle + passes, long + short), so each
request went through the same verify steps it goes through alone, whoever shares the server. Without draft keeping the
same work took 71,745 drafted at 4 users and 83,195 at 16 (mean acceptance length 3.26 and 2.84, now 3.42). On the
long suite at 16 users the ten-second acceptance windows are 3.3-5.5 (were 1.0-2.9). At 16 users drafting is now
ahead of drafting off (465 against 419 on R314, 2026-10-15), where the two used to tie.

**P1** (the 16:29 setup again, normal long suite, three passes): **62/64, 63/64, 63/64** (88.5 / 89.6 / 89.8 tok/s).
Four flips, on other requests than at 16:29: docs6k-c013 (pass 1) and docs4k-c026 (pass 3) differ at their first
token, i.e. in the prompt read itself; code2k-c041 (pass 1) and prose8k-c062 (pass 2) at their second. The solo
answers of the two prefix-cache servers are identical (0 of 64 differ), as are those of two cache-off servers. So:
deterministic alone, a timing-dependent difference with two users, only with the mixed suite (the one-family
detector never flipped in 576 answers). Not from the 0.3.0 count restore: a request between two prompt pieces sits
out the other user's decode step, but its stored count is 1 (the align postprocess writes 1 for prompt rows).
Kernel log clean; Gemma restored. Data: `/mnt/fast-ai/bench-results/fp8-r314-{R16,R4,P1}-20261016-drafts/`.

## Addendum, 2026-10-16 18:05 EDT: what the prefix-cache flip needs (written before it runs)

P1 differs from the exact 2026-10-15 recipe in two things at once: prefix caching and 832-token prompt steps. Three
fresh servers, normal long suite, three passes, long only, draft keeping off:

| Arm | Users | Drafting | Prefix caching | Prompt step | Question |
| --- | ---: | --- | --- | ---: | --- |
| Q1 | 2 | off | on | 832 | is drafting needed? |
| Q2 | 2 | on | off | 832 | is it caching or the step size? |
| Q3 | 1 | on | on | 832 | does it need a second user at all (repeats after the solo pass, blocks reused)? |

Q2 needs `MU_BATCHED=832` (new, only sets `--batched`). Reading: flips out of 192 per arm, against P1's 4 of 192. Not a
gate. About 45 minutes. Same wrapper, `TAG=20261016-pcwhy`.
