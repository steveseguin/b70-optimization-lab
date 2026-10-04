# Comm-5 preregistration: a clean two-card step profile, and persistent gather buffers (2026-10-03)

Written before the run. Runner:
[`../scripts/run-20261003-fp8-comm5-campaign.py`](../scripts/run-20261003-fp8-comm5-campaign.py). Background and the
cost model: [the exchange-fusion memo](2026-09-18-two-card-exchange-fusion-memo.md).

## Why now

The two-card recipe has been at about 90.3 tok/s since comm-2. The memo's two next steps were never run because the
host was halted on faults. Tonight the host is clean on kernel 7.0.0-38 (25 two-card starts today, no fault lines), and
both packages have just been re-accepted, so the service can be borrowed for an hour.

## What is being tested

1. **Measurement first.** The September 17 two-card trace had both ranks profiling, which inflated the step 3.4x and
   wrecked the cost attribution. The profiler's rank gate was fixed on September 18 and has not been used since. Stage
   one takes a 30-step trace on rank 0 only, with the shipped allgather overlay on. It answers: how much of the ~33 ms
   step is device-busy, how much is gaps between kernels, and what one collective really costs on the host.
2. **Candidate: `b70-allgather-pbuf`.** The shipped overlay allocates a fresh `(2,) + shape` buffer for every one of
   the 155 collectives in a decode step. The candidate keeps one buffer per (shape, dtype, device) for inputs of up to
   64 rows and reuses it. The gather and the `gathered[0] + gathered[1]` add are byte-for-byte the same calls, and the
   add still returns a new tensor, so the arithmetic cannot change; the only new risk is ordering (a later gather
   overwriting the buffer before an earlier add has read it), and the exactness gates exist to catch that.
   CPU test: [`../tests/test_b70_allgather_pbuf.py`](../tests/test_b70_allgather_pbuf.py).

## Gates and the decision rule

- Control: the shipped recipe on the research launcher, one fresh server, strict twice, same session.
- Candidate: two fresh servers, strict twice each (12/12 against the comm-2 no-MTP reference every time); on the first
  server also the 64-prompt ladder (sequential oracle plus two queued passes), the 2K/8K/16K context screen and the
  chat-quality suite, all against the comm-2 no-MTP references.
- **Go** only if every candidate gate is exact **and** the median of the four candidate strict runs is at least
  **1.0 % above** the median of the two control runs. Tonight's 23 package-launcher servers ran 89.85 to 90.41 tok/s,
  so 1 % is about three times the run-to-run spread.
- Exact but under 1.0 %: recorded as exact and neutral, not shipped. Any non-exact gate: closed, with the first
  divergence recorded.
- One stop of the service, one restore, no retry of any server. A GPU fault line halts the campaign and skips the
  restore.

## Expectation, stated in advance

Small. A device allocation from PyTorch's caching allocator is a few microseconds; 144 of them is well under a
millisecond of a 33 ms step. The honest prior is **0 to 1 %**, more likely neutral than a go. The profile is the part
of this run that is certain to be useful: it decides whether the fused add-and-norm kernel (memo candidate e, 1-2 days
of work) is worth starting, or whether the two-card lane is finished at about 90.3.

## Also changed for this run

The research launcher [`../scripts/run-fp8-tp1-server.py`](../scripts/run-fp8-tp1-server.py) still started containers
with `--memory-swap 16g`. It now uses `12g`, the same no-swap setting both package launchers ship. Every research
server before today ran with the 4 GiB swap allowance.

## Addendum, 22:45 EDT: attempt 1 halted before the test; the rerun changes order only

The first run halted in its profile stage ([what happened](2026-10-03-fp8-comm5-attempt1-guard-kill.md)) and tested
nothing. The rerun, [`../scripts/run-20261003-fp8-comm5b-campaign.py`](../scripts/run-20261003-fp8-comm5b-campaign.py),
keeps every gate and the 1.0 % rule above exactly as written. Only the order changes: control, candidate A, candidate
B, then an optional 8-step profile, then the service restore. It needs a fresh boot.
