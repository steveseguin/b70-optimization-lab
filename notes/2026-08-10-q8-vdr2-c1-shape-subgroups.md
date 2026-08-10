# Qwen3.6 27B Q8 VDR2 c1 shape-adaptive workgroups: rejected

## Decision

Reject the default-off `GGML_SYCL_REORDER_Q8_0_C1_SHAPE_SUBGROUPS=1`
candidate. Preserve it as a negative structural experiment, but do not expose a
runner profile or launch a model-service crossover. Exact component correctness
passed; balanced same-card component timing was a small weighted regression.

## Why it was tried

The retained VDR2 profiler packet contains 921 complete decode cycles. The
selected exact reordered-Q8 kernel accumulated `46.593445008 s`, or
`50.5900597 ms/cycle`. That is `83.9237%` of the independently measured
`60.281 ms/token` wall baseline.

The same kernel is `99.5474%` of the profiler's *filtered trace time*
(`46.805277875 s`). Those figures are not interchangeable: 99.55% describes
only the filtered trace, while 83.92% is the defensible share of unprofiled
token wall. The remaining wall budget is about `9.69094 ms/cycle`.

The largest launch groups were output-row count 17408 (`41.62%`, average
`165.235 us`) and output-row count 5120 (`29.39%`, average `116.692 us`). The
5120 bucket mixes the `k=17408` down projection with shorter-k attention/GDN
outputs, explaining its wide approximately 61-215 us spread. Qwen source maps
the exact hot pairs to 128 gate/up calls per cycle at `(m=17408,k=5120)` and 64
down calls at `(m=5120,k=17408)`.

Prior production-width Q4 evidence suggested that packing four or two SG16
row-owning subgroups per workgroup might help these two shapes. This was only
cross-quant evidence, so the candidate was explicitly a cheap falsification.

## Frozen source delta

Base commit: `15586e2d7165570fb3aa7c26e0d442e289ef69de`.

The focused patch adds a default-off compile-time knob and refactors only the
reordered Q8_0 c1 launcher:

- `(ncols=5120,nrows=17408)` uses `reorder_mul_mat_vec_q8_0_q8_1_sycl_launch<4>`
  (WG64);
- `(ncols=17408,nrows=5120)` uses `...launch<2>` (WG32);
- every other shape retains `...launch<WARP_SIZE>` (WG256).

Subgroup width remains 16, one subgroup still owns one output row, and VDR2
dot/reduction math is unchanged. Multi-column c2 dispatch is untouched.

- Source patch: `patches/qwen36-27b-q8-gguf-b70/20260810-q8-vdr2-c1-shape-subgroups.patch`
- SHA-256: `2fa07cea2f9d74aca8785c10887c5f7ffcd329d74f16f7c352deec759c6ee25b`
- Test-only fixture patch: `patches/qwen36-27b-q8-gguf-b70/20260810-q8-vdr2-c1-shape-subgroups-component-fixture.patch`
- Fixture SHA-256: `79d56dd0dae67b096c8f5a312ea54023f58d927dc0c5ca946d9fd4008df3f1b6`

Both patches pass `git apply --check` against the clean base. The fixture keeps
Q8 src0 in a WEIGHTS buffer and registers only the two exact Q8_0 x F32, n=1
shapes in `test-backend-ops`; it is not part of the candidate DSO delta.

## Build and runtime identity

The candidate compiled successfully with VDR2 plus the shape knob. Configure
took 3.23 s and the focused SYCL build took 207.43 s. The frozen candidate DSO
is `86898952` bytes with SHA-256
`aa123bcbea2f07381b31f869811e2ad513f2e1098031ee89e4e8fa160c72dfaf`.

The candidate origin bundle is:

`/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-c1-shapewg-hybrid`

Compared with the frozen VDR2 control, exactly one regular file differs:
`libggml-sycl.so.0.18.1`. The unchanged server SHA-256 is
`1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`.

Build evidence:

`/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-c1-shapewg-build-evidence-20260810`

## Component gate

Run packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/component-q8-vdr2-c1-shapewg-20260810T072931.577095866Z`

Preflight found no relevant inference/validation process or benchmark listener;
all four distinct B70s used 43 MiB. Control and candidate each passed both exact
cases against the strict CPU reference. `GGML_SYCL_DEBUG=1` confirmed the
reordered c1 wrapper for both exact shapes, and the frozen exact-pair dispatch
therefore entered template `<4>` and `<2>` respectively.

The balanced order was C-A-A-C / A-C-C-A on physical GPU0, with four samples
per runtime. Each process used the test harness's warmup and at least one second
of measurement per shape.

| Exact shape | Control median | Candidate median | Saving |
| --- | ---: | ---: | ---: |
| m=17408, k=5120 | 167.165 us | 168.330 us | -0.6969% |
| m=5120, k=17408 | 168.130 us | 167.995 us | +0.0803% |

Using the exact 128:64 calls/cycle weighting, the candidate saves `-0.4369%`
(a regression). The projected change is `-140.48 us/token`, or `-0.2330%` of
the `60.281 ms` unprofiled wall. This is far below the required approximately
5% hot-shape and 2-3% weighted-token thresholds.

All four GPUs returned to 43 MiB, no fault was observed, and no model service
was launched. The negative result closes this candidate before service-level
testing.
