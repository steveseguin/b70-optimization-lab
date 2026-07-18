# Packed Max Collective And M=8 DPAS MHC Closure

Date: **2026-07-18**

Status: **both candidates rejected; exact vector M=8 path retained**

## Outcome

Two plausible follow-ups to the 80.820052 tok/s DSpark7 record failed their
admission gates:

1. Packing each rank's BF16 Markov score and inverse global token ID into one
   `int64`, followed by XCCL `MAX`, was incorrect on all four cards and slower
   than the existing four-pair gather. The slowest-rank median for seven
   sequential decisions rose from **1.557571 ms to 2.351866 ms**, a
   **0.794295 ms/cycle regression**. The returned packed value decoded to an
   impossible token ID (`775692`) in the first negative-score/tie case.
2. Routing fixed M=8 MHC through the existing TF32 DPAS path reduced the
   row-tiled component from **8.036463 ms to 7.182942 ms**, an isolated
   **0.853521 ms/cycle saving**, but changed `next_post_mix`, `next_comb_mix`,
   and `layer_input`. The first service arithmetic canary returned **1053**
   instead of **1073** on both the initial request and replay. The other four
   canaries passed and every request was cache-zero, so the exact gate isolated
   a numerical-quality failure rather than cache or service-state contamination.

Neither candidate reached a realistic performance suite. There is no endpoint
throughput claim and no LocalMaxxing submission.

## Packed XCCL `int64 MAX`

The gate is preserved at:

- script: `../scripts/bench-tp4-packed-max-allreduce.py`;
- result:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-packed-max-allreduce-20260718/gate.json`.

The attempted key layout itself is logically sufficient for BF16 ordering and
lowest-token tie breaking, but the measured XCCL path did not deliver the
requested signed-`int64` maximum semantics for this payload. Even if its
arithmetic were repaired, its measured collective path is already slower than
the control. Do not retry another scalar dtype encoding through generic XCCL
without first proving the collective primitive independently.

## Generic M=8 DPAS MHC

The component and service evidence is preserved at:

- component:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-dpas-mhc-gate-20260718T2230Z`;
- service pre-canary:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-m8-mhc-dpas-candidate-20260718T2240Z`;
- vLLM source: `217df8fc3a9db36fe66e8263a2e281bb37ffce05`;
- XPU prototype/fail-close: `e6a5f6c` / `827b7799296b6dafb1c9a95a5eba341e55663733`.

The experiment is fail-closed behind
`VLLM_XPU_V4_MHC_POST_PRE_M8_DPAS=1`; launcher identity records the flag and
its default remains `0`. The XPU library was rebuilt after the fail-close
change. The generic DPAS path changes the MHC reduction order, so its component
speed is not admissible for the unchanged target-quality lane.

## Next boundary

Retain the exact fixed-M8 vector arithmetic and reduce its shared `fn[24,16384]`
traffic instead. The next candidate assigns two verifier rows to one workgroup,
loads each FN vector once, and maintains separate per-row accumulators with the
same K traversal, subgroup reduction, workgroup reduction, BF16 boundary, and
Sinkhorn order as the promoted vector path. It must be bitwise exact on changed
eager inputs and graph replay before any endpoint load.
