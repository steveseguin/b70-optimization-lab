Prepared bounded raw-history replay; not compiled or run yet. No model or GPU required.

Inputs must come from a future complete, sealed 244-row native capture accepted by validate.py after both owners exit successfully and full-source neutrality passes. The failed R1 first-row payload is prohibited. extract_controls.py retained exactly 384 bytes of actual blk.4.ssm_a and blk.4.ssm_dt.bias, checked against GGUF/placement identities; see its extraction receipt in /dev/shm/sc117-l4-native-replay-20261028-r1. Raw ssm_a is already the actual negative F32 control and receives no synthetic transformation.

First replay unchanged production specialised::gdn stage 0 and stage 1 with actual native raw conv/alpha/beta, exact controls, zero initial state and flags 94. All 244 output rows must match captured native y bitwise. Failure exits before crossed-input analysis; preserve it rather than normalizing or changing the adapter to force a pass.

Only after qualification: run the actual pinned ggml RMSNorm/scale, softplus/gate, sigmoid and GDN graph on the same native raw history. Compare per-row outputs, then feed ggml prepared history through the unchanged production stage 1. Compare against the independently retained CPU prepared history separately. These comparisons can bracket same-input stage-0 arithmetic versus different upstream histories; they are neither additive error attribution nor a proof of the final token disagreement cause.

Build and run commands/provenance remain to be finalized against the existing pinned archives. No production arithmetic or canonical source changes are needed for this standalone replay. Root speed gate and matched timing take priority; no compilation or heavy CPU during measured requests.
