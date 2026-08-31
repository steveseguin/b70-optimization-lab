# Qwen3.8 ordinary native-GDN cross-process D4 result

Date: 2026-08-31

Status: **negative causal screen; 12/12 state trajectories stable**

At every strict-suite prefill row count, the complete native-GDN prefill
output plus conv/SSM state and the subsequent 32-step M=1 decode trajectory
plus final state were bitwise identical across two chains inside each process
and across four fresh processes. All four process receipts were byte identical.

The ordinary native GDN recurrent transition is not the remaining MTP0 cause.
This is raw-operator evidence only. Next, screen the actual 248,320×5,120
BF16 checkpoint LM-head weight (loaded as server FP16) at M=1 across fresh
processes, hashing all logits and greedy selection.

Condensed result:
`../data/2026-08-31-qwen38-ordinary-gdn-cross-process-d4-result.json`.
