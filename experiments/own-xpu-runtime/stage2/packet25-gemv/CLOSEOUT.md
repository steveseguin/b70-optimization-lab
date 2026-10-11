# Packet 25 preparation closeout

Question: can large GEMVs retain every output bit while reducing idle subgroup
work, packed decode/collective work or expanded-load overhead?

Identity: `iq3-p17-detmath-v2`, frozen `r234-sg32-split4-bf16`, synthetic
real-format tiles at the model's actual large-GEMV shapes. Current WG128 control
and every candidate remain isolated here. No device ran and no speed is claimed.

Outcome: CPU preparation is complete, with independent arithmetic/race review,
two compilers, fresh processes, per-value and routed checks, mechanically
bounded captures and sealed K0/G1 preparation. [Build receipt](build-receipt.json)
and [CPU gates](cpu-tests.json) are the evidence. GPU qualification is pending.

Useful mechanisms retained: independent-row scheduling, private metadata
arithmetic, paired input loads, bounded half-scale tables, per-token selected
expansion, dense scale reuse and contiguous code loads. The initial mixed-NaN
failures are retained and resolved for CPU fixtures by explicit current-path
fallback, not tolerance. Native current-vs-host NaN parity remains a gate. The added SiLU diagnostic
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
