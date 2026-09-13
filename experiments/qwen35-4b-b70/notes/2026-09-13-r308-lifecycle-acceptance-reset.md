# R308 lifecycle trace: accepted count lost at re-add

The completed 9B lifecycle diagnostic confirms the acceptance-count reset in
all six selected failing requests. This identifies the observed mechanism;
no functional fix was tested in this campaign and nothing is promoted.

The [independently parsed summary](../data/2026-09-13-r308-lifecycle-negative/summary.json)
preserves each request ID and source log line for this ordered transition:

1. `ACCEPTED_AFTER` records GPU accepted count **2** at computed position 252.
2. `REMOVE` records CPU/GPU accepted count **2**, with `resumed=False`.
3. `READD` records CPU accepted count **1** at computed position 254, still
   `resumed=False`.
4. `RUNNER` receives CPU/GPU accepted count **1** for the final one-token step.
5. The final sampled ID differs from the same-image MTP0 oracle.

All six outputs have complete numeric token-ID arrays and zero cached tokens.
Their prefixes match the expected outputs and only the last generated token
at absolute position 255 differs. Selected cases are L14, L16, and L14-tail238,
each repeated twice. The trace requests are associated with probe rows by
chronological serial execution (`concurrency=1`), then checked against each
traced final sampled ID; the probe rows themselves do not retain request IDs.

Postflight records two normal devices, two successful compute smokes, successful
allreduce on both ranks, and no new fault signatures. The `DONE` marker means
the negative diagnostic completed, not that output identity passed.

The [raw evidence](../data/2026-09-13-r308-lifecycle-negative/evidence/),
[source hashes](../data/2026-09-13-r308-lifecycle-negative/source-manifest.json), and
[replayable parser](../data/2026-09-13-r308-lifecycle-negative/capture.py) preserve
the observation. Instrumentation can affect execution. A functional repair
must separately pass the same numeric-ID oracle and fresh-server requirements.
