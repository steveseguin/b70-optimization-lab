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

**Caveat (07:37, before any run):** R198 (2026-09-04, R156 image) captured whole decode steps in XPU graphs at MTP1
and depth 3, drafter passes included, and was 1.2-1.4 % slower, not faster: "per-launch submission is cheap enough
on this EPYC host". That argues against a host-bound drafter, at least on that image. The estimate above is
arithmetic on a one-card census and could be wrong in the verify pass instead (six-slot recurrent state writes, the
GDN speculative kernels). The clock decides; if the host waits 5 ms or more per step, the drafter graphs are not
tried and the next step is the device-side look.
