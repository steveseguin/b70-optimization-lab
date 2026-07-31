# Laguna decode GRF128 component pass and endpoint preregistration

Date: 2026-07-31 America/Toronto

Status: **component passed; one frozen endpoint candidate leg authorized**.
No endpoint throughput is claimed in this note.

## Built candidate

- kernel source: `e4163f93574326b2772742e0f51372a5a3777aa5`;
- base: `46a88e09d96fe06871c87a23de534fb47f1e039b`;
- DSO SHA-256:
  `df2f63a04630c3b50d3ffe2d61db3e3d68914436ba14270dcc45ddfec6b3467f`;
- DSO size: `25,896,936` bytes;
- preserved DSO:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-decode-grf128-build-e4163f9-20260731T0918Z/libgrouped_gemm_xe_2.so`;
- build command: `ninja -C build/temp libgrouped_gemm_xe_2.so`;
- build result: PVC, BMG, BMG G21 A0, and BMG G31 A0 all passed;
- elapsed: about 16 minutes, with the device frontend peaking near 106 GB
  used host memory.

The shorter build compared with the prior 42-minute/123-GB MAD build is not a
performance result. It is consistent with removing the rejected
`DEQUANT_MAD=1, SCALE_VEC=0` instantiation before adding the separately named
decode kernel.

## One-card component result

Fresh valid artifact root:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-decode-grf128-component-20260731T0925Z`

The same candidate DSO was mapped in both worker processes. Only
`VLLM_XPU_LAGUNA_DECODE_GRF128` changed from literal `0` to `1`; scale-vector
stayed on, MAD/fold stayed off, prefetch stayed 6, and exactly one physical
B70 was visible. Three independently generated inputs were compared for each
real Laguna target-MoE GEMM shape.

| Shape | Raw BF16 exactness | 256-GRF median | 128-GRF median | isolated speedup |
| --- | ---: | ---: | ---: | ---: |
| W13, `M=120 N=2048 K=3072` | 3/3 | 0.344897 ms | 0.342481 ms | 1.0071x |
| W2, `M=120 N=3072 K=1024` | 3/3 | 0.186690 ms | 0.180698 ms | 1.0332x |

Overall raw exactness is **6/6**. Input, packed-weight, scale, and route-count
hashes also match between arms. The direct component result is promising but
modest; it does not imply a model-level gain and by itself does not reach the
130 tok/s objective.

The earlier `...T0924Z` root is a harness-only failure: system Python could
not import Torch, so no GPU call occurred. It is excluded from all evidence.

## Endpoint preregistration

Run exactly one cold candidate leg on the last verified 121.037 historical
metric stack:

- model: Laguna S2.1 INT4 target, official DFlash INT4/FP8 projection draft;
- BF16 KV, TP4/EP4, one active generation;
- width 12, DFlash depth 11;
- vLLM `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- kernel source `e4163f93574326b2772742e0f51372a5a3777aa5`;
- DSO hash above and candidate runtime lock;
- persistent exact-attention metadata, width-12 router/workspace stack,
  draft segmented graph plus inline draft attention;
- target inline gathers off, replicated embedding off;
- `SCALE_VEC=1`, `DEQUANT_MAD=0`, `SCALE_FOLD=0`, prefetch 6;
- only new selector: `VLLM_XPU_LAGUNA_DECODE_GRF128=1`;
- no warmup, frozen 13-prompt suite once, 512 max tokens, metric window 100,
  seed 1, cached tokens zero.

Required pass conditions are unchanged:

1. 13/13 token IDs and text hashes match the frozen q=1 teacher;
2. cached tokens are zero for all prompts and every prompt runs once;
3. target graph topology is 146/145 on all four ranks;
4. draft graph topology is 14/13 on all four ranks;
5. the recorded environment contains the literal GRF128 selector and the
   mapped grouped-GEMM SHA is the candidate SHA;
6. clean graceful teardown and verified idle interval; no reset or reboot.

If any condition fails, do not quote the rate. If all pass, report both the
historical 100-event/99-span compatibility metric and the conventional
99-interval metric. Compare first with the exact `121.03724088473012` /
`119.82686847588282` incumbent identity, while recognizing that one cold leg
cannot establish a small change below the host noise floor.

