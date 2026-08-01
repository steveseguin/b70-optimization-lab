# Laguna exact M12 shared-elementwise record

Date: 2026-07-31 America/Toronto

Status: **verified exact BF16-KV four-B70 record; approved by LocalMaxxing as
`cms9wuuf300cqpm01t5i285tq`**.

## Result

The width-12 target now uses separately named exact native operations for the
shared-expert `SiLU(gate) * up` and the routed BF16-scale boundary plus shared
addition. The arithmetic and every BF16 rounding boundary are unchanged. Over
48 target layers the component reduced 192 device operations to 96 and saved
`0.734276300 ms`; the strict endpoint result is:

| Metric | Result |
| --- | ---: |
| conventional 99-interval median | **125.4619731637751 tok/s** |
| historical compatibility | **126.72926582199506 tok/s** |
| conventional p10 | 87.14257704068571 tok/s |
| conventional mean | 145.39496746282836 tok/s |
| full-output after-TTFT median | 165.87634713661552 tok/s |
| full wall median | 56.18228440405635 tok/s |
| TTFT median | 5953.834546999133 ms |

This improves the preceding exact `124.64241272122038 tok/s` record by
`0.81956044255472 tok/s`, or **`0.6575293471%`**. The remaining conventional
gap to 130 is `4.5380268362249 tok/s` (`3.6170536154%` relative to this row).

## Qualification

- first formally valid score from the final source identity;
- 13/13 canonical-q1 token IDs and output-text hashes exact;
- `cached_tokens=0` on all 13 unique cold requests;
- each prompt invoked once; no warmup generation, response reuse, history,
  prefix cache, or benchmark retry;
- exact target `146/145` and segmented draft `14/13` capture/replay on all four
  TP/EP ranks;
- four rank-local M12 shared-elementwise execution markers;
- 72-second prestart and poststop idle intervals;
- clean service, worker, port, and GPU teardown.

Sealed run:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-shared-elementwise-m12-formal-20260801T053000Z
```

The preceding complete diagnostic at
`laguna-shared-elementwise-m12-fixed-20260801T052000Z` measured
`125.06865574449961 tok/s` and was exact, but remains non-promoted because the
original evidence call used vLLM's local-rank-only logging scope. The wrapper
correctly rejected its single marker. Commit `1a7f61fe` changed only the
evidence scope to per-process; this record is the first run satisfying the
frozen four-rank evidence gate.

## Identity

- target `poolside/Laguna-S-2.1-INT4` revision
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft `poolside/Laguna-S-2.1-DFlash-INT4` revision
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- vLLM `1a7f61feffbc61b21b73f812d231c7426386ccdc`;
- XPU kernels `99886d783372e621941228250091dc8ebdc1595d`;
- candidate `_C.abi3.so` SHA256
  `36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095`;
- grouped-GEMM DSO SHA256
  `c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
- runtime lock SHA256
  `64b0f04d29aabcabd65c0f71ff6a4c0923208228abd0559f2308e63fb3334829`;
- BF16 KV, TP4+EP4, one active generation, exact target width 12, DFlash
  depth 11, greedy draft and standard target rejection;
- prior record selectors retained, with
  `VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=1` and legacy
  `VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0`.

Formal command arguments after the run directory:

```text
12 11 1 0 0 1 0 0 0 1 1 0 0 '' 64 0 '' 6 0 1 0 0 1 0 0.90 0 0 0 1 0 1 1 0 0 0 1
```

## Reproduction artifacts

- structured packet: `data/laguna-shared-elementwise-m12-record-20260731.json`;
- preregistration and full failure chronology:
  `notes/2026-07-31-shared-elementwise-m12-preregistration.md`;
- component artifact:
  `laguna-shared-elementwise-m12-component-20260801T042945Z`;
- runtime lock: `tools/runtime-lock-shared-elementwise-m12.json`;
- XPU-kernel patch and bundle:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-add-exact-Laguna-M12-shared-elementwise-ops.patch` and
  `vllm-xpu-kernels-laguna-shared-elementwise-m12-99886d783-20260731.bundle`;
- vLLM patches `0001-xpu-enable-exact-Laguna-M12-shared-elementwise-ops.patch`,
  `0002-xpu-preserve-Laguna-MoE-layer-prefixes.patch`, and
  `0003-xpu-emit-Laguna-selector-evidence-per-worker.patch`;
- vLLM bundle
  `vllm-laguna-shared-elementwise-m12-1a7f61fef-20260731.bundle`.

## Transferable learning

Exact, repeated elementwise fusions can still pay inside captured graphs when
their absolute full-cycle cost is large enough; the `0.734 ms` component floor
predicted a small but real endpoint gain. Preserve explicit low-precision
rounding boundaries rather than algebraically simplifying them. Constructor
temporaries must never reuse model-layer identity names, and runtime evidence
must use process scope when the audit requires every worker. A valid semantic
result can still be non-promotable if its execution-proof contract fails.

## Publication

The authenticated server dry-run returned `valid: true`. The conventional
result was accepted with HTTP 201 and immediately approved as
[`cms9wuuf300cqpm01t5i285tq`](https://www.localmaxxing.com/en/runs/cms9wuuf300cqpm01t5i285tq).
The queue and response are preserved under `data/`; the prior matching
`cms9thsax00ccpm01cmddk057` row is superseded.
