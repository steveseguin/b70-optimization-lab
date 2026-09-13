# Torch deterministic mode is not a lever (R295, 2026-09-12 evening)

The 2026-09-12 census found the default oneDNN fp16 GEMM run-to-run nondeterministic for the per-layer
projections at 129+ rows (split-K classes), and that `torch.use_deterministic_algorithms(True)` removes it in
isolation at no measurable cost on the vocabulary projection and a few percent on the small shapes. The obvious
question: does turning it on in the server buy identity under speculation at 64 users, where a depth-3 verify
step produces exactly those row counts?

R295 = R294b + an env-gated hook in `XPUWorker.init_device` (`VLLM_XPU_TORCH_DETERMINISTIC=1`, `warn_only=True`;
`docker/r295-xpu-torch-deterministic.py`, image 489800b4). Two arms on one card (Level Zero index 0), depth 3,
`CLASSPAD=1`, the 67k draft shortlist, the fragile suite at 64 users x 20 passes with the 5 ms admission stagger,
then the no-speculation control on the same server shape. The worker logged the R295 line in det1; the env was
verified in every container. Data: `data/2026-09-12-qwen35-4b-r295-torch-deterministic.json`.

| arm | depth 3, 64 users: exact of 64 per pass | median tok/s | passes identical to pass 2 | no-spec 64 users |
| --- | --- | ---: | ---: | --- |
| det0 (off) | 47, then 42-44 | 1833 | 6 / 18 | 64/64 x5, 2109 tok/s |
| det1 (on) | 45-49, settling at 46 | 1295 | 0 / 18 | 64/64 x5, 2078 tok/s |

Deterministic mode costs 29% under speculation at 64 users (the no-speculation control loses 1.5%), lifts the
exact count by about four rows, and makes the passes less repeatable, not more. So the residual 64-user
nondeterminism under speculation is not the split-K kernel selection the census isolated; it lives in what the
verify step sees (admission order and acceptance dynamics), which the stagger only partly pins on one card.
The two-card stagger recipe (R293, 3164 tok/s exact) remains the exact configuration. Closed: do not pursue R295
as an identity lever. The overlay stays in the repo as an off-by-default knob; launchers forward it only when set.
