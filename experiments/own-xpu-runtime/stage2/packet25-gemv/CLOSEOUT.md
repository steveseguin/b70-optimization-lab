# Packet 25 preparation closeout

Question: can large GEMVs retain every output bit while reducing idle subgroup
work, packed decode/collective work or expanded-load overhead?

Identity: `iq3-p17-detmath-v2`, frozen `r234-sg32-split4-bf16`, synthetic
real-format tiles at the model's actual large-GEMV shapes. Current WG128 control
and every candidate remain isolated here. This repair ran only on CPU; no speed is claimed.

Outcome: CPU preparation is complete, with independent arithmetic/race review,
two compilers, fresh processes, per-value and routed checks, mechanically
bounded captures and sealed K0/G1 preparation. [Build receipt](build-receipt.json)
and [CPU gates](cpu-tests.json) are the evidence. GPU qualification is pending.

Useful mechanisms retained: independent-row scheduling, private metadata
arithmetic, paired input loads, bounded half-scale tables, per-token selected
expansion, dense scale reuse and contiguous code loads. The initial mixed-NaN
failures are retained and resolved for CPU fixtures by explicit current-path
fallback, not tolerance. Native current-vs-host NaN class and same-card candidate bit parity remain gates. The added SiLU diagnostic
also found a cross-compiler NaN difference, retained separately; nonlinear
postprocessing is not qualified by this GEMV packet.

Uncertainty: hardware compiler behavior, actual timing, cache/residency effects,
input classification cost, dense input/residual prologues and real-model oracle.
The prepared operator sequence does not include the whole model. No candidate
is promoted or installed in packet23/24. Revisit after coordinator K0/G1 and
real-model gates; retain failures and exclude mismatching arms.

All source, fixes, review and reproducible build commands are retained here.
Only local compile scratch is deleted; final ignored binaries remain for the
coordinator. This closes CPU preparation, not the optimization lane.

## G1-a closeout and G1-b handoff

G1-a passed fourteen preceding fixtures then stopped cleanly at element 14 of
an exceptional IQ2_S fixture; no timing was produced. Its [coordinator evidence](evidence/20261011-g1-a-special-input-current-vs-host/README.md)
is retained unchanged, as are ignored build/K0 and build/G1. CPU reproduction
finds negative quiet NaN on GCC and positive quiet NaN on icpx (both paired
outputs); original device bytes are unknown. This supports NaN propagation as
the expected cause, with direct device diagnosis pending the new bit dumps.

The [README policy](README.md#g1-b-exceptional-input-gate-repair-2026-10-11)
keeps finite values, signed zero, denormals and infinities exact. Host NaN/card
NaN encodings may differ; candidates must retain current-card bits everywhere.
Numerical failures now exclude affected arms and preserve remaining timing work.
Both fresh owners complete before a finite failure is returned. A sequence with
an excluded current format is explicitly skipped, never timed as qualified.
The model rejects nonfinite values as sticky errors; this is no output tolerance.

Rebuilt CPU gates and source/binary seals are in build-receipt.json and
cpu-tests.json. All existing finite and exact CPU digests remain unchanged;
ten exceptional-policy checks and completed-failure summary tests were added.
Revisit after coordinator K0-b/G1-b; no GPU run or production promotion here.
