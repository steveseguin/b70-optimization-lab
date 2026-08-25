# Qwen3.6 Q4_K_M F16-KV TP1 MTP1 parent sentinel R1 failure

R1 is preserved at
`/mnt/fast-ai/bench-results/qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1`
and remains `failed-preserve-do-not-expand`. It fills no matrix cell and does
not authorize the seven-depth MTP1 curve.

Both exact-depth HTTP arms completed their own request gates. The MTP0 control
measured `22.54901425418198 tok/s`; the MTP1 candidate measured
`30.16612325933283 tok/s`, with `59/68` draft tokens accepted on the exact
request. These are synthetic 8K serving observations, not promoted rates.

The runner then called the quality client with system `python3`. Four exact
canaries and two repeat requests were served before the client reached its
deferred `transformers.AutoTokenizer` import for the 8K needle. That environment
did not provide `transformers`, so execution stopped before the needle and
before the client wrote `quality.json`. The six short-request values and their
pass/fail states were therefore not persisted and none may be claimed. The
traceback was console-only; the cause is established by reproducing the import
failure with system Python and matching it to the pinned client code and server
request sequence. `quality.stdout.json` is empty, and the terminal validator
was not reached.

Cleanup is **observed, not terminal-validator certified**. The candidate server
log ends with `cleaning up before exit`; the fallback terminal receipt followed
about 0.23 seconds later, and the present process census is idle. However, the
`set -e` dependency stop bypassed the explicit `stop_server`, postflight render
gate, and terminal validator, so R1 never passed the frozen cleanup gate.

This was not the only unsatisfied scientific gate visible in the preserved
evidence. The control output-token hash is `20fe4323...68a7`, while the
candidate hash is `326ffa80...dc0`. R1 therefore does not satisfy the frozen
target-output-parity requirement either, even though each arm's individual
exact-depth receipt passed. No quality, parity, speed, or expansion conclusion
transfers from R1.

R2 may correct the quality interpreter, but it must use a new create-only root,
rerun both arms, and retain every identity, exact-depth, parity,
draft-engagement, cache-zero, quality, cleanup, and no-speed-floor gate. It may
not reuse R1 rows. The structured source is
[`../data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1-failure.json`](../data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1-failure.json).
