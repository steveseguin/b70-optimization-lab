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
