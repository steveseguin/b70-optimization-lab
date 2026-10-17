# 2026-10-17 The writing-step floor: 38.5 ms on the context lane against 33.0 ms quoted for the package

Registered 07:00 EDT, before any run. The cards are down (second fault on the boot, owner asked to reboot); this runs
after the reboot, after campaign 28f.

## Why

Writing is about 63 % of the model's time in an agent run (c27a K32: 232 of 367 s by the fit
0.190 s/call + 0.274 ms/uncached token + 7.66 ms/written token; K64 228 of 393 s). At the context lengths of those
calls (16-34K) a step costs about 40-43 ms, of which about 38.5 ms is the floor measured at 1K
(`notes/2026-10-17-fp8-writing-attention.md`, W832o: 38.49 / 38.22 ms per step at 1K copy / story). Every 1 ms off
the floor is about 2.5 % of writing, about 6 s per run.

The TP2 package is quoted at 33.0 ms per step (`notes/2026-10-03-fp8-comm5b-result.md`), but that figure comes from
a class-balanced median rate divided by mean acceptance, on R310, with no prefix cache, a 33,024 window and steps of
4,096; it was never timed the way W832o was. The one two-card per-kernel trace (09-17, R310) puts the GEMMs at about
28 ms per step and everything else on the device at about 4-5 ms, which adds up to about 33. So either the lane
spends 5 ms per step on something the package does not (the prefix cache family, the 262,144 window, 832-token
steps), or the two numbers were measured differently and the floor is about 38 ms everywhere.

Not the cause, already known: the INT4 draft head and shortlist (both run them), the environment (the lane's container
environment equals the package's apart from the overlay switches, checked 06:57 from `launch.json`), one-launch verify
(off below 1,536 keys), the image (R314 with one user runs the package's benchmark at about 90 tok/s, the package's
own figure).

## Run

`scripts/run-20261017-step-floor.sh`: four R314 servers in turn, each probed with
`probe-write-rate-vs-context.py` (copy and story, 512 tokens, end of text ignored) at 1K, 8K, 16K and 30K; ms per
step = client writing time / the server's draft count.

| Arm | Window | Steps of | Prefix cache | Extra overlays |
| --- | ---: | ---: | --- | --- |
| L | 262,144 | 832 | align, exact + tail, retention 13,312 | spec-resume-accepted, exclusive-prefill |
| N | 262,144 | 832 | off | exclusive-prefill |
| M | 262,144 | 4,096 | off | none |
| P | 33,024 | 4,096 | off | none |

All four: TP2, MTP5, INT4 draft head + shortlist, allgather, chunked-upload and GDN state-width overlays, verify rows
in one launch, memory 0.95, one sequence. L uses 832-token attention pages (align mode sets them); N, M and P keep 64.
At 1K that makes no measurable difference to attention (about 2 ms in all); at 30K it can, so the 1K row decides.
No profiler: a guard kill in the middle of a step reset an engine this morning, and a profile needs host memory the
two-card server does not leave.

## Predictions

- L at 1K: 38.5 ms per step again (within 1 ms of W832o).
- P at 1K: 33-36 ms per step. If the package figure was only measured differently, P is within 1 ms of L.
- Tokens per step at each length about the same in every arm (5.3 copy, 2.7 story at 1K); answers may differ between
  arms in the step-of-832 and step-of-4,096 groups (prompt pieces differ), so they are recorded, not required equal.

## Decision

- **L − P under 2 ms at 1K:** the floor is the same everywhere; the 33.0 was a measuring difference. The step is
  device time (GEMMs about 28 ms at about 480 GB/s per card, against 550-600 GB/s per shape alone); next lever: the
  GEMM gap in the server (why the same shapes run slower inside the step), registered separately.
- **L − P 2 ms or more:** the arms split it. L − N is the prefix-cache family; N − M is 832-token steps (plus
  exclusive-prefill, which does nothing with one sequence); M − P is the window. The group carrying 2 ms or more gets
  a code read of its per-step work (host side first: with asynchronous scheduling a step only slows if the host's
  work per step outgrows the device's), and a fix is tested for equal answers before any timing claim.
- Any fault line: stop, rule 3.

## Amendment 07:03 EDT (before any run): two arms without the drafter

From this morning's agent runs (per-call fit of model seconds on uncached and written tokens, K32 rules stream):

| Run | Drafting | ms per written token | Tokens per step | ms per step |
| --- | --- | ---: | ---: | ---: |
| c28c | none | 28.8 + 0.168 per 1K of context | 1 | about 31.7 at the calls' mean 17K |
| c27a | depth 5 | 7.66 | 5.27 (c28a note) | about 40.4 |

So on the lane, speculation (five drafter passes plus five more checked rows) adds about 8.7 ms per step at 17K and
about 9.5 ms at 1K (38.5 against about 29.0). The package's derived figures give it 3.5 ms (33.0 against 29.5). The
device work it should take: five passes of one layer plus a 65K-row INT4 head (about 0.6 ms each) and five more rows
in GEMMs that are weight-bound at six rows: about 3-4 ms. The step without drafting is the same on both (29 against
29.5), so the gap, if real, sits in speculation.

Added arms (same runner, same probe; ms per token = 1 / writing rate): **P0** = P and **L0** = L with `--mtp 0`.

- **Predictions:** P0 and L0 at 1K within 1 ms of each other and of 29 ms.
- **Decision, added:** speculation cost = (L − L0) and (P − P0) at 1K.
  - L's 2 ms or more above P's: the lane's extra is in speculation; N and M say which flag group it follows.
  - Both within 2 ms of each other and 6 ms or more: speculation costs about twice its device work everywhere.
    Next: read the drafter loop on the host side (the five passes run one after another; any wait for the host in
    between leaves the cards idle), then register a fix with equal answers as its gate.
  - Both under 5 ms: the 33.0 / 38.5 difference was the measuring, the drafter is near its device work, and the floor
    is the GEMMs (lever: the in-server GEMM rate, about 480 against 550-600 GB/s alone).

## Amendment 07:32 EDT (before any run): the host step clock, and what the code read found

A read of R314's drafting path (vLLM 0.29 as installed in the image, and the overlays in use) found no wait for the
cards inside the five drafter passes or in the hand-off from checking to drafting: the drafted ids stay on the card.
What it found is host work: each drafter pass is issued from Python, op by op, about 25-35 launches (five of them
collectives, each of the allgather overlay's all-reduces being an empty tensor + all-gather + add; each FP8 linear a
quantise launch + a GEMM), and the INT4 shortlist head fills a 124,160-column row with -inf, scatters into it,
gathers 248,320 logits across the cards and takes the argmax over all of them. Estimated host time 0.8-1.5 ms per
pass against about 0.6-0.7 ms of card work. Smaller items: the verify-row tensors rebuilt in each of the 16 attention
layers (1-2.5 ms per step), a CPU-mask index into a card tensor in the GDN metadata (a blocking copy, three times per
step), rejection sampling in fp32 over 5 x 248,320 logits, environment reads inside per-layer calls. All unmeasured.

So every arm also runs `overlays/b70-host-step-clock` (0.1.0, `B70_HOST_STEP_CLOCK=1`): for each decode step it
records, on each card's worker, the time from one step's start to the next (period), the host time inside
execute_model, sample_tokens and propose_draft_token_ids, and the time the host spends in the runner's event waits.
It adds no synchronisation and touches no tensor (CPU tests `tests/test_b70_host_step_clock.py`; installs on R314's
runner class, checked in the image on CPU). One line per answer per card, saved as `clock-<arm>.txt`.

- **Prediction:** on the drafting arms the host waits under 2 ms per step at 1K (period about 38 ms): the host is the
  slower side, and the period is roughly the host's issue time.
- **Decision, added:**
  - Waits under 2 ms with a drafting period of 35 ms or more: launch count is the lever. In order: argmax on the
    shortlist output with a cross-card (value, index) exchange in place of fill + scatter + gather + full argmax
    (first-max tie order checked on CPU before any run), verify-row tensors built once per step, the GDN index
    copy made non-blocking; each change gated on answers equal to the arm's own answers, then timed. Then graphs for
    the drafter passes (one token each), with the one-card graph exactness failure (9/12) re-checked first.
  - Waits of 5 ms or more: the cards are the slower side; host fixes cannot pay; the next look is device-side (a
    one-rank profile on a server with more host room).
  - In between: both, sized by the arms.

## Amendment 07:34 EDT (before any run): the verify pass is cheaper than a one-row pass, so the drafter costs more

The 10-04 GEMM census (`data/2026-10-04-fp8-multiuser/census/census.json`, one card, TP2 shapes, R310 era) has the
MLP down projection at 215 us for 1-4 rows, 104 us at 5 and 76 us from 6 rows up; the other five shapes are flat in
rows. Summed over the 64 layers the target's GEMMs take 30.0 ms at one row and 20.5 ms at six. So:

- the no-drafting step (29 ms, c28c) is mostly its one-row GEMMs, and is not the base the drafting step adds to;
- the six-row verify pass should cost about 20.5 + 1.1 (head) + about 2-3 (attention, recurrent layers, norms,
  collectives) = about 24 ms, leaving about 14-15 ms of the 38.5 ms step for the five drafter passes, sampling and
  hand-over: about 3 ms per pass, against about 0.9 ms of device work per pass (one-row GEMMs of the MTP layer
  0.46 ms, its fc and the 65K-row INT4 head about 0.2 ms, attention, norms, three collectives). Depth 6 cost about
  2.7 ms more per step (`notes/2026-10-17-fp8-agent-draft-depth.md`): one more pass, the same figure.

**Sharpened prediction for the clock:** on the drafting arms, host time inside propose_draft_token_ids 8-15 ms per
step, waits under 2 ms. If so, the drafter passes are host-bound and taking them to device speed is worth up to
about 10 ms per step (38.5 -> about 28 ms at 1K, writing about 35 % faster), far more than any single launch trim.
That makes one-token graphs for the drafter (its passes only; the target's kernels untouched, so its answers cannot
change) the first candidate, before the launch trims listed above.

**Small separate lever, banked:** the drafter's down projection runs at one row (215 us); padded to six rows it
would take 76 us, and the census shows row 0 bit-identical at every row count (one invariance class, 1-512 rows).
About 0.7 ms per step at depth 5. Needs a census on R314 before use.

**Caveat (07:35, before any run):** R198 (2026-09-04, R156 image) captured whole decode steps in XPU graphs at MTP1
and depth 3, drafter passes included, and was 1.2-1.4 % slower, not faster: "per-launch submission is cheap enough
on this EPYC host". That argues against a host-bound drafter, at least on that image. The estimate above is
arithmetic on a one-card census and could be wrong in the verify pass instead (six-slot recurrent state writes, the
GDN speculative kernels). The clock decides; if the host waits 5 ms or more per step, the drafter graphs are not
tried and the next step is the device-side look.

## Amendment 07:41 EDT (before any run): the padded down projection, census then arm Lp

`overlays/b70-w8a16-pad-rows` 0.1.0 (`B70_W8A16_PAD_ROWS=1`): a W8A16 GEMM call with fewer than 6 rows whose weight
is K 8704 x N 5120 (the TP2 down projection) runs on its activation padded with zero rows to 6, as one vLLM custom op
(opaque to the compiled graph, row count read at run time), and returns the real rows. The server holds the block
scales in float32 (`create_fp8_scale_parameter`, checkpoint BF16 copied in), the census's dtype. CPU tests
`tests/test_b70_w8a16_pad_rows.py`; installs on R314's `XPUFp8BlockScaledMMKernel` (checked in the image on CPU).

1. **Census first** (`scripts/census-w8a16-pad-rows.py`, R314, card 0, about a minute, before any server): for
   8704 x 5120 and 17408 x 5120 (TP1), every row of every 1-8-row call equal to the 8-row call's row, padded rows
   (zero and random padding) equal to the unpadded call, repeats equal; device times at 1, 2, 4, 5, 6, 8 rows and
   padded 1. **Must hold for 8704 x 5120**, or arm Lp is not run.
2. **Arm Lp** (last, if the census holds): L plus the overlay, same probe.
   - **Must hold:** every Lp answer bitwise equal to L's (same server otherwise), tokens per step equal.
   - **Prediction:** census times like 10-04 (about 215 us at one row, about 76 padded); Lp's ms per step about 0.7
     lower than L's at every length (five drafter passes); the no-drafter arms would gain about 9 ms per token, not
     measured here.
   - **Decision:** answers equal and 0.4 ms or more off per step at 1K: adopt for the context lane (a 1-2 % lever) and
     propose for the TP2 package after its census at the package's own image; a TP1 census row with the same gap
     opens the one-card package question. Any answer different: stop, trace.

## Census result 11:13 EDT (R314, card 0): exact, but no row class; the 10-04 cliff does not reproduce

`data/2026-10-17-step-floor/census-w8a16-pad-rows.json`. Both shapes pass every check (rows of 1-8-row calls equal to
the 8-row call's, zero and random padding equal, repeats equal), so arm Lp runs as registered. But the times are flat:

| K x N | 1 row | 2 | 4 | 5 | 6 | 8 | 1 padded to 6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8704 x 5120 (TP2 down proj) | 82.6 us | 82.4 | 82.4 | 82.5 | 82.4 | 82.6 | 97.1 |
| 17408 x 5120 (TP1) | 159.8 | 160.2 | 160.4 | 160.6 | 160.4 | 160.9 | 181.1 |

82.6 us for 44.6 MB of FP8 weight is about 540 GB/s, near the card's bandwidth: one row is already at speed, and
padding only adds the concatenation (+15-21 us). The prediction (about 215 us at one row) is **wrong** at this
layout (FP8 weight [N, K] passed as its [K, N] view, float32 128 x 128 scales as the contiguous [K/128, N/128]
buffer). The 10-04 census either used another scale layout or another build of the op; not re-read here.

What follows, before any arm has run:
- **Lp is now a check of the server's own layout, not of the lever.** If Lp is no faster than L (expected), the
  server calls the op the way this census does and the lever is closed. If Lp is 0.4 ms or more faster per step, the
  server's call differs from the census (a slow layout in the server) and that layout is the thing to look at.
- **The 07:34 arithmetic loses its premise** if the server is flat too: the six-row verify pass is then not cheaper
  than a one-row pass, the no-drafting step (29 ms) is close to the base the drafter adds to, and the five drafter
  passes come to about (38.5 - 29 - verify extra) / 5, roughly 1.5-1.9 ms each rather than 3. The clock's
  waits-versus-host split still decides; the sharpened prediction (draft time 8-15 ms per step) is withdrawn in favour
  of the original decision tree.

## Amendment 11:32 EDT (L, N, M, P run; P0, L0, Lp not yet): the step is the same on all four, and the cards are busy

**Write probe, ms per step (copy / story):**

| arm | 1K | 8K | 16K | 30K |
| --- | --- | --- | --- | --- |
| L (context lane) | 38.14 / 38.18 | 39.14 / 39.17 | 40.46 / 40.49 | 42.50 / - |
| N (no prefix cache) | 37.93 / 37.81 | 38.80 / 38.98 | 40.36 / 40.24 | 42.27 / 42.31 |
| M (steps of 4,096) | 37.91 / 37.77 | 38.84 / 38.92 | 40.20 / 40.20 | 42.25 / 42.30 |
| P (package flags, 33K) | 37.85 / 37.81 | 38.82 / 38.93 | 40.25 / 40.17 | 42.18 / 42.24 |

**L - P = 0.3 ms at 1K: the registered branch "under 2 ms: a measurement difference".** The package's 33.0 ms was
2.98 tokens per step / 90.3 tok/s, two summary statistics of different requests divided, never a timed step; on
R314 the package's own flags give 37.85 ms. The prefix-cache family (L - N, 0.2 ms), the 832-token steps (N - M,
0.0) and the window (M - P, 0.1) cost nothing measurable while writing.

**The host clock's reading, and why it does not mean host-bound.** On every arm the event waits are about 0.05 ms
(median) and "not waiting" equals the period (execute about 31 ms, sample about 6.8 ms of which draft about 6.0 ms):
by the registered rule (waits under 2 ms, period 35 ms or more) that reads as host-bound. It is not:
- **Added measurement (from 11:19, during arm N; nothing about the arms changed):** each card's compute and copy
  engine busy cycles from the driver (`/proc/<pid>/fdinfo`, `drm-cycles-ccs` over `drm-total-cycles-ccs`, summed over
  the GPU clients), sampled every 0.25 s with the server's token counters (`scripts/sample-xe-engine-busy.py`,
  `scripts/report-xe-engine-busy.py`; read-only). Over every decode-only stretch of N, M and P (each answer of the
  probe): **compute engine 98.7-100 % busy on both cards**, copy engine 45-56 %.
- **Why the clock missed it:** the GDN metadata builder makes the drafting-step mask on the card from a CPU tensor
  every step (R314 `vllm/v1/attention/backends/gdn_attn.py:248`); a blocking host-to-card copy on the in-order queue
  returns only when all earlier work has finished, so the host's wait for the cards sits inside execute_model, where
  the clock counts it as host time. The clock only sees the four explicit events.
- So the step is set by the cards (or by work queued on them: a context waiting on a semaphore also counts as busy).
  **Withdrawn: the drafter-graph and launch-trim candidates** (they shorten host time that is already hidden). This
  agrees with R198 (graphs 1.2-1.4 % slower on this host).

**Where 38 ms goes on the card (arithmetic, to be measured next):** weights read once per pass at about 540 GB/s
(the census rate): target 13.5 GB per card, about 25 ms; its full LM head about 2.3 ms; five drafter passes (the MTP
layer about 0.2 GB per card plus the 65K-row INT4 head) about 3-4 ms. About 31 ms at bandwidth, so about 7 ms of the
38 is something else: the roughly 130-150 cross-card collectives per step (the copy engine is half busy), the
recurrent layers' speculative kernels, attention, norms. The next measurement is a device-side split of one step.

## Amendment 11:46 EDT (P0, L0 run; Lp running): speculation costs 7.8 ms a step, not 3.5; arm Pk added

**No-drafter arms:** P0 33.18 / 33.20 tok/s at 1K (30.1 ms per token), 30.5 at 30K; L0 32.94 / 33.14 (30.3 ms),
30.45 at 30K. Same within 1 %, and close to the 10-03 two-card figure (29.5 ms, R310). Card busy counters: compute
and copy engines 99-100 % busy while writing.

**So the drafting step costs P - P0 = 37.85 - 30.1 = 7.75 ms more than a one-token step on R314,** for five drafter
passes plus five more verify rows. The 10-03/04 sizing (`notes/2026-10-03-fp8-comm5b-result.md`: "cost of
speculating 3.5 ms", 33.0 vs 29.5) used the derived 33.0. Correction to the busy reading of 11:32: the counter is
time a client's context has work on the engine, including semaphore waits (the copy engine reads 99.7 % busy
without drafting, about 50 % with it), so it shows the cards' queues never run dry (the host is not the limit), not
that the cards compute all the time.

**The open question this study cannot answer:** every arm ran on R314. Either the package (R310 image) also takes
about 38 ms per drafting step and 33.0 was an artefact of dividing two summary statistics, or R314's drafting step is
about 5 ms slower than R310's.

**Arm Pk (registered now, runs after Lp, about 6 min):** the TP2 package exactly as shipped,
`packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start --profile recommended` (image eb8165..., R310, its own
environment), port 18197, the same write probe (1K/8K/16K/30K, copy and story, 512 tokens), the same busy sampler.
- **Prediction:** 37-39 ms per step at 1K (the 33.0 was derived; R310 to R314 changed nothing on the drafting path
  that should cost 5 ms). Tokens per step may differ from P's (another image, other prompt-reading numerics).
- **Decision:** Pk 35 ms or less at 1K: R314 has a drafting-step regression of 3 ms or more; the next run bisects
  R310 -> R314 (image first, then one-launch, state-stride and the overlays) before any new lever. Pk 37-39 ms:
  the package's quoted step was never real; the 7.75 ms speculation cost is real on both, and the next measurement is
  a device-side split of a drafting step against a one-token step (one 8-step rank-0 profile on each, the comm5b
  recipe, `overlays/b70-step-profiler`), to find which of the drafter's passes and the verify rows carry it.
  In between (35-37): report both readings, run the profile.

## Arm Lp result (11:43-11:48 EDT): exact, no gain; the padded down projection is closed

Every Lp answer is bitwise equal to L's (8/8 texts, tokens per step equal), and the step is not faster: 38.27 / 38.13
ms at 1K against L's 38.14 / 38.18, 42.60 against 42.50 at 30K (+0.1 ms, noise). The server's own call is as flat
as the census's, so padding only adds the concatenation. Lever closed; the overlay stays as research code.
No breadcrumb block on any arm (no stall, no failure); kernel log clean from 11:12:42 to the end (11:48:31).

## Arm Pk result (11:48-11:53 EDT): the package's drafting step is 38 ms too; 33.0 was never a timed step

`data/2026-10-17-step-floor/write-Pk.log`, the TP2 package as shipped (R310 image, profile recommended):

| ms per step (copy / story) | 1K | 8K | 16K | 30K |
| --- | --- | --- | --- | --- |
| Pk, package as shipped | 37.95 / 37.77 | 42.20 / 42.15 | 50.29 / 50.36 | 59.70 / 59.83 |
| P, package flags on R314 (one launch) | 37.85 / 37.81 | 38.82 / 38.93 | 40.25 / 40.17 | 42.18 / 42.24 |

- **Prediction (37-39 ms at 1K) held.** The package's step at 1K is the same as R314's within 0.1 ms; the quoted
  33.0 ms (and the 10-03/04 "speculation costs 3.5 ms") came from dividing two summary statistics. Registered
  branch: the 7.75 ms speculation cost is real on both; next is the profile pair (P and P0, 8 steps each, rank 0).
- **Side result, the package one-launch proposal:** with the package's own flags, R314's one-launch verify writes
  9 % faster at 8K, 25 % at 16K and 41 % at 30K than the shipped package (same tokens per step, same prompts); the
  same direction as gates 1-3 of `notes/2026-10-17-tp2-package-one-launch-proposal.md`. Owner's call, unchanged.
- Kernel log clean 11:48:55-11:53:08; the package's own stop path left the cards empty.

## Profile pair result (11:56-12:00 EDT): where the 38 ms of a drafting step go on the card

8 decode steps each, rank 0 only (comm5b recipe; profiler timing is not a speed figure, kernel durations are).
Traces `/mnt/fast-ai/bench-results/fp8-r314-floor-{P,P0}-20261017-prof-trace/`, summaries
`data/2026-10-17-step-floor/profile/summary-{P,P0}.json`, matmuls by launching op `scripts/trace-gemm-by-op.py`.
Kernel log clean 11:53:32-12:00:23.

| per step, card 0 (ms) | P0, one token | P, depth 5 | difference |
| --- | ---: | ---: | ---: |
| target FP8 linears (`_xpu_C::fp8_gemm_w8a16`, 256 calls, about 540 GB/s) | 22.57 | 22.6 | - |
| drafter FP8 linears (about 17.5 calls, 4 per pass) | - | 2.62 | +2.62 |
| target LM head, BF16 `aten::mm` (2.13 ms per call, about 600 GB/s) | 2.13 | 2.13 | - |
| GDN `in_proj_ba`, BF16 `aten::mm` (48 calls at 10-20 us) | 0.5 | 0.5 | - |
| drafter `mtp.fc`, BF16 (about 95 us per pass, split over the cards) | - | 0.48 | +0.48 |
| drafter INT4 shortlist head (`int4_gemm_w4a16`, 262 us per pass, about 320 GB/s) | - | 1.15 | +1.15 |
| attention (split-KV FMHA; 6 verify rows take 38.7 us per call against 7.4 for one) | 0.13 | 0.79 | +0.66 |
| GDN kernels (speculative variants when drafting) | 0.63 | 0.99 | +0.36 |
| all-gather kernels (130 / 152 calls) | 0.65 | 0.88 | +0.22 |
| argmax and the rest (norms, elementwise, copies) | about 1.8 | about 2.3 | +0.5 |
| **all kernels** | **28.4** | **34.6** | **+6.2** |
| step without the profiler (write probe) | 30.1 | 37.85 | +7.75 |
| **not in any kernel** (step minus kernels) | **1.7** | **3.25** | +1.55 |

Readings:
- **The target pass is at the memory wall.** Its FP8 linears move 12.2 GB per card in 22.6 ms (about 540 GB/s of the
  B70's 608 GB/s) and the BF16 LM head runs at about 600 GB/s. 25 of the 30 ms of a one-token step is weight reads.
- **Drafting costs about 1.2 ms of kernels per pass** (FP8 layer 0.52, `mtp.fc` 0.1, INT4 head 0.23, attention,
  norms, exchanges), plus the verify rows' extra attention and GDN work. Its FP8 layer already runs at the target's
  rate; an INT4 drafter layer would halve the bytes but the W4A16 kernel runs at about 320 GB/s, so it would save
  roughly 0.1 ms per pass: not worth an acceptance risk.
- **The time in no kernel (1.7 ms without drafting, 3.25 ms with it) matches the exchanges' latency:** the compute
  queue waits for each all-gather's peer copy (130-152 per step, about 13-21 us each beyond the kernel). Together with
  the kernels the exchanges cost about 2.4 ms (one token) to 4.1 ms (drafting) a step, 8-11 %. Moving the same bytes
  faster cannot change any output, but the only faster path is a custom peer-to-peer transport, and the lab's one
  peer-visible kernel lost the device on its first test (`notes/2026-08-16-q8-peer-pair-collective-unsafe.md`).
- **Not left:** host time (the queues never run dry), GEMM row classes (flat on R314), the cache, step and window
  settings (L = N = M = P).

**Where this leaves the lane:** a writing step is within about 15 % of what reading the weights alone takes, and
the biggest single remainder is the cross-card exchange. Next measurement (cheap, no server): the all-gather's
end-to-end latency per call at the decode shapes on the two cards, to confirm the 13-21 us figure before any
transport idea is weighed against its fault risk.

## Registered 12:05 EDT (before it runs): the all-gather's latency on the bare cards

`scripts/bench-xccl-allgather-latency.py`, two processes (one per card) under `torch.distributed.run`, the server's
oneCCL environment (the TP2 package's CCL_* settings), no server: for fp16 [1|6, 5120] and [1|6, 124160], the
median device time of one all-gather alone, and what one gather adds after a 50 MB fp16 matmul (a decode linear).
- **Prediction:** added 13-21 us per call at [1|6, 5120] (the profile pair's no-kernel time over 130-152 calls).
- **Decision:** added 12 us or more: the exchanges' latency is about 2-3 ms per drafting step, and a lower-latency
  transport goes into a design memo weighed against its fault risk (owner's call before any peer-visible kernel).
  Under 8 us: the no-kernel time is something else (event waits, the GDN copies); the profile's gaps get a closer look.

## All-gather latency result (12:06 EDT): about 5-6 us per decode exchange, about 1 ms a step; registered branch "under 8 us"

`data/2026-10-17-step-floor/xccl-allgather-latency.json` (two cards, no server, kernel log clean). A first attempt
synchronised after every call, so the two processes drifted apart and the gathers waited for the other host
(12.8-246 us, discarded); timed in batches of back-to-back calls, the ranks stay in lockstep as in a server step:

| fp16 shape per rank | gather alone | added after a 50 MB matmul |
| --- | ---: | ---: |
| 1 x 5120 | 15.2 us | 4.8 us |
| 6 x 5120 | 15.3 | 6.4 |
| 1 x 124160 (drafter head) | 15.6 | 12.5 |
| 6 x 124160 (target head) | 42.4 | 49.9 |

Bytes arrived unchanged on both ranks for every shape. About 150 decode exchanges at 5-6 us plus the heads' gathers
come to about 1.0-1.2 ms per drafting step: under the 12 us bar, so **no transport memo**; the exchanges are not
where the 3.25 ms of no-kernel time goes. What is left is the cards' own cost per kernel: a drafting step issues
about 1,650 device operations (1,283 for one token; the five drafter passes add about 74 each), so 1-2 us of gap per
operation accounts for the rest. That is a fusion question (fewer, larger kernels in the drafter passes), the same
territory as R198's graphs (1.2-1.4 % slower here), and no single piece of it is above about 2 %.

**Study conclusion:** a 27B FP8 TP2 writing step (37.9 ms at 1K) is about 25 ms of target weight reads at about
540 GB/s, 2.1 ms LM head, about 6 ms of drafting kernels (five passes and the verify rows' extras), about 1 ms of
exchanges and about 3 ms of per-kernel gaps and small kernels. Nothing measured today is a lossless lever above
about 2 % per step; the levers worth their cost stay the ones that cut steps or reads: acceptance (tokens per step)
and the long-context paths (one-launch verify, already +9/25/41 % over the shipped package at 8/16/30K).
