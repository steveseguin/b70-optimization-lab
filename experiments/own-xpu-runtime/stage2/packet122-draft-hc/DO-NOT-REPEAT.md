# Packet122 boundaries

| Arm or assumption | Evidence / next condition |
| --- | --- |
| Treat the old HC fusions as a new optimization | Already selected in packet118. The new arm changes subgroup mapping and independent sigmoid placement only. |
| Omit exceptional-value checks | Both compilers pass 16 complete gate/mix cases twice, including NaN payloads; keep the serial exceptional fallback. |
| Advance on an overall median only | Every changed gate and their sum must pass0.8 in both contexts/orders and both fresh processes. |
| Treat cyclic captured-input cache fill as a natural 4K prompt | Explicitly diagnostic; v5 supplies cold real-prompt model checks after the micro. |
| Treat CPU equality as device equality or a speed gain | Device micros and full bracket remain pending. |
| Reopen draft load8, split prefix/rank0 draft or tune prefix N from benchmark outputs | Those arms remain closed; fixed 80,128 follows packet114's non-benchmark rule. |

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
