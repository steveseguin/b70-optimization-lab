# Parallel TP host submission

Date: 2026-08-12

## Decision

Keep `GGML_META_PARALLEL_SUBMIT=1` as a default-off exact kernel-path win.
It submits the four independent simple-backend graphs concurrently, joins the
host threads, and then runs the existing TP collective. Per-device queue order
and all arithmetic are unchanged. No drafter training was performed.

Source commit: `f9434ef2b` (`meta: add experimental parallel device
submission`). Experimental server SHA-256:
`8eea728f1752424475a49db07ecef8776cb42d5347f84f208243afdb8887f50f`.
The operation profiler was disabled because its shared counters are not
thread-safe.

## Fixed identity

- Muse Glimmer 30B BF16 target, stock BF16 DFlash, TP4 devices `0,1,2,3`;
- DFlash `n_max=15`, `p_min=0.15`;
- single request, `parallel=1`, greedy, prompt cache disabled, 256 generated
  tokens for prose, code, and JSON;
- oneDNN primitive cache, binding cache, and BF16 graph conversion cache on;
- direct BF16/oneMKL, command graphs, device argmax, and operation profiling
  off;
- only changed variable: `GGML_META_PARALLEL_SUBMIT=0/1`.

Canonical hashes were `914f754747d0edaa`, `cf2b2c4fd9e36fe5`, and
`4f813a9706abc163` for prose, code, and JSON.

## Strict adjacent results

| Order | Arm | Prose | Code | JSON | Mean t/s |
| --- | --- | ---: | ---: | ---: | ---: |
| control first | serial | 46.488 | 67.559 | 81.651 | 65.233 |
| control first | parallel | 48.507 | 70.428 | 84.696 | 67.877 |
| candidate first | parallel | 48.331 | 70.037 | 85.285 | 67.884 |
| candidate first | serial | 46.663 | 67.349 | 82.318 | 65.443 |

The candidate improved the arithmetic mean by `4.05%` in control-first order
and `3.73%` in candidate-first order. The pooled arm means are approximately
`65.338 -> 67.881 tok/s`, or `+3.89%`.

Every row produced all 256 tokens and all canonical hashes. Within each
adjacent pair, drafted and accepted counts were identical in all three
classes. The JSON draft count moved from 672 in the first pair to 674 in the
second pair for both arms, so that epoch variation does not confound the
within-pair comparison.

Raw evidence:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-submit-ab-v3-20260812.jsonl`,
  SHA-256 `ba1ebc9ded794e70bb7f2a2f04b790ba0b2a3d418150c352d7226223ace60aca`;
- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-submit-ab-v4-reversed-20260812.jsonl`,
  SHA-256 `0831662108cad14b568e0e8fdd3a3121dbf9c37c9017ff4be883cc0713404f20`.

The fresh v3 identity was used only after the authorized host reboot and full
four-device mapping, per-card compute, native peer-read, and XCCL recovery
gates passed. Production was restored after the window and passed the complete
model, cache-zero code, and vision gate in
`data/muse-health-20260812-parallel-submit-restore.json`.

## Narrowed oneMKL combination negative

The current `GGML_SYCL_BF16_MKL=1` gate was narrowed to verification widths
N=2 through N=16, leaving N=1 on the incumbent oneDNN path. It was tested on
top of parallel submission:

| Arm | Prose | Code | JSON | Mean t/s |
| --- | ---: | ---: | ---: | ---: |
| parallel control | 48.248 | 70.320 | 84.518 | 67.695 |
| parallel + oneMKL N2-N16 | 47.668 | 72.026 | 83.424 | 67.706 |

The ratio was only `1.00016x`, inside noise, while the code hash changed from
canonical `cf2b2c4fd9e36fe5` to `b4a2bda611510441` and proposal histories
changed. Reject this combination. Raw evidence:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-bf16-mkl-ab-20260812.jsonl`,
SHA-256 `81944bb0576509ddd700b071e970451948045045b77b36273f5d70b25bf675a0`.

## Next action

The retained exact stack is approximately `67.9 tok/s`, still not the
`>100 tok/s` objective. Continue kernel work with a guarded batch=2 oneDNN
gate/up projection that removes one logical FFN projection submission per
layer, then measure it adjacent to this retained parallel-submit stack.
