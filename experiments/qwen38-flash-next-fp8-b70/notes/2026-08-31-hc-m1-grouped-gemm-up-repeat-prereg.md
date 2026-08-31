# Qwen3.8 Flash-Next FP8 HC M1 grouped-GEMM up-repeat preregistration

Date: 2026-08-31
Status: frozen before component execution

The initial four-pair screen made layer-0/up eligible at 65.12% lower component
latency and showed a 74.34% directional reduction at layer 47, where excessive
control drift withheld eligibility. This bounded replication runs two new
fresh-process control/candidate/control brackets for each of those up weights.

It inherits without change the exact model/checkpoint, runtime stage and
manifest, loader closure, real-weight hashes, one-B70 selector, seed `20260830`,
100 warmups, 21 batches of 100 calls, 100 exact-output repeats, no-clobber
evidence rules, and interpretation from the
[N352 preregistration](2026-08-31-hc-m1-grouped-gemm-n352-prereg.md). The
benchmark SHA-256 is
`8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0`;
the driver SHA-256 is
`650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7`.
The initial layer-0/up and layer-47/up pair SHA-256 values participating in the
three-bracket decision are respectively
`a29e6e2aa3bfa52ab54c3851d9d6f1633ffe1bf627752965fe5e16996d00ca3e`
and `32346b46962e24dcf3365c48b6f6bf31d8424ad9dc6f5ed68ddc404e5d3278f1`.
Their tracked aggregate is
`data/20260831-hc-m1-grouped-gemm-four-pair-screen.json`, SHA-256
`1e4a935c7537938180a68412ac0cad3482be545e75032a553e93a7d71af900cf`.

Each repeat independently requires exact output, at least 5% candidate latency
reduction, and at most 3% control drift. The up-family replication gate passes
only if both new brackets pass for layer 0, at least two of the three total
brackets pass for layer 47, and every arm remains repeatable and finite. A pass
authorizes only a broader 48-layer round-robin component screen, not source
integration or an endpoint claim.

The two new roots must not exist before execution:

- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-repeat-r1-seed20260830`;
- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-repeat-r2-seed20260830`.

For each `REPEAT` in `r1 r2` and `LAYER` in `0 47`, run the frozen pair driver
with projection `up`, placing the output at
`.../hc-m1-grouped-up-repeat-REPEAT-seed20260830/layer-LAYER-up.json`.
