# M7/M8 MoE activation portfolio: negative component gate

Date: 2026-07-19

## Outcome

The explicit M7/M8 shared and routed activation portfolio is bitwise exact on
all four Intel Arc Pro B70 cards, but it **fails** the frozen pre-model-load
performance gate. The slowest-card/worst-route result is **0.4901208
ms/cycle saved** on physical card 2, below the required **0.50 ms/cycle**.

Per the decision contract, the patch is preserved behind default-off flags,
production defaults remain off, and work stopped before a 96 GiB model load,
service launch, B-A-B suite, or LocalMaxxing submission.

This is a component-cycle result for one active generation. It is not an
endpoint throughput claim.

## Source and binary identity

- vLLM: `284ef5942dd83e532bf23de52eaecf6e6fb323db`
- XPU kernels: `909eaca103fad0d118b7340fc1411edc8b7c4973`
- `_xpu_C.abi3.so` SHA-256, both `build/temp` and package copy:
  `d62ea1cf4728250809052c68fdd74983b4f2c0dcaf924624e7a507c8d4c8392f`
- The requested edits are Python selectors only. `py_compile` passed for both
  source files; no native object was rebuilt or relinked.
- The loaded source-identical activation extension was
  `/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/vllm_xpu_kernels/_C.abi3.so`,
  SHA-256
  `69114af57a671d4e8f006a21525964c3bdd044f4ad8eeedaa39acdff1e737d16`.
  `_moe_C.abi3.so` from that package was
  `e9f3522bf74f3f3a068e9e83e4bc70272c6d9c3668bc725ead86b5bf364bcfe3`.

The vLLM selector now retains explicit legacy M1/M2 admission and adds exact
M7 and M8 branches. The XPU-kernel Python selector retains exact M2 and adds
M7 scoped to the 64-local/256-global DSpark EP4 draft plus M8 scoped to the
40-local/160-global K160 EP4 target. It does not use an `M <= 8` guard.

New default-off flags:

- `VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_DRAFT_M7=0`
- `VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_TARGET_M8=0`
- `VLLM_XPU_V4_DRAFT_M7_ROUTED_CLAMP_SILU=0`
- `VLLM_XPU_V4_TARGET_M8_ROUTED_CLAMP_SILU=0`

An explicit flags-off subprocess confirmed that the shared selector admits
only legacy M1/M2 and the routed selector only legacy M2. Existing launchers
were not changed, so all new flags remain absent/default-off. Rejected
event/host/sharded Markov transport, M8 DPAS/pair-tile MHC, copy-elision,
context-WKV, and fixed-M8-builder flags were not touched.

## Exactness gate

The harness exercised, independently on physical cards 0, 1, 2, and 3:

- 40/40 changing eager cases per card;
- 32/32 changed fixed-address XPUGraph A-B-A cases per card;
- shared `[M,1024]` BF16 clamped SwiGLU to exact `[M,512]` E4M3FN values and
  exact `[M,4]` FP32 scales at M7 and M8;
- routed `[M*6,4096]` BF16 to exact `[M*6,2048]` BF16 activations at M7 and
  M8;
- explicit `-32/-10/-9.9375/-0/+0/9.9375/+10/+32` clamp boundaries;
- candidate-connected exact token canaries after both shared and routed
  outputs;
- the captured real M8 verifier-logit top-1 oracle, exactly
  `[19, 16, 455, 20, 16, 223, 21, 16]` on each rank.

| Physical card / EP rank | Eager | Graph | FP8 values/scales | Routed BF16 | Tokens |
|---|---:|---:|---|---|---|
| 0 | 40/40 | 32/32 | exact | exact | exact |
| 1 | 40/40 | 32/32 | exact | exact | exact |
| 2 | 40/40 | 32/32 | exact | exact | exact |
| 3 | 40/40 | 32/32 | exact | exact | exact |

## Timing gate

One captured portfolio cycle contains the three M7 DSpark MoE stages and 43
M8 K160 target layers. Each card was run in an isolated process with its
physical device selected by `ZE_AFFINITY_MASK`. Timing used 20 warmups, nine
alternating samples, and 100 graph replays per sample.

Five valid EP route families were measured separately:
`typical_quarter_local`, `overlap_quarter_local`, `six_local`,
`all_same_local`, and `all_remote`. The activation selector operates on the
production padded `M*topk` extent, but route-conditioned changing contents
were retained and the minimum saving—not an average—was used for every card.

| Physical card | Worst valid route | Control median (us/cycle) | Candidate median (us/cycle) | Saved (ms/cycle) | Gate |
|---:|---|---:|---:|---:|---|
| 0 | `six_local` | 695.97268 | 199.62592 | 0.49634676 | FAIL |
| 1 | `all_remote` | 688.97192 | 196.16376 | 0.49280816 | FAIL |
| **2 (slowest)** | **`six_local`** | **687.96676** | **197.84596** | **0.49012080** | **FAIL** |
| 3 | `all_remote` | 689.36868 | 196.09200 | 0.49327668 | FAIL |

The overall result misses the gate by `0.0098792 ms/cycle` (about 1.98% of
the required saving). Nearness to the threshold does not change the declared
failure.

## Evidence

- Harness:
  `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/bench-m7-m8-moe-activation-portfolio.py`
- Raw results, stdout, empty stderr logs, exit codes, and flags-off check:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m7-m8-moe-activation-portfolio-20260719T013554Z`
- Real target-token corpus:
  `/mnt/fast-ai/deepseek-v4-corpora/mtp-reuse-m8-sequential-20260718T0440Z`

## Recommendation

Do not spend a 96 GiB model load or a same-binary B-A-B suite on this
portfolio as currently implemented. It is exact and very close to the gate,
so the default-off patch is useful infrastructure for a future compatible,
non-overlapping component, but Item A alone does not satisfy the predeclared
investment rule. Resume only if a separately exact addition raises the
conservative slowest-card/worst-route floor above 0.50 ms/cycle; do not relabel
this run as a pass based on favorable routes or averages.
