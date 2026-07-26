# Reproduction Recipes

This directory holds promoted reproduction recipes for benchmark results that
are worth preserving as standalone, shareable artifacts.

Each recipe should include enough detail to rebuild the runtime, prepare the
models, run the same benchmark shape, and inspect the result record without
depending on transient local notes.

## Recipes

| Recipe | Use It For |
| --- | --- |
| [Laguna S 2.1 INT4 on 4x Intel Arc Pro B70, published 102.971 / conventional 101.942 tok/s, 2026-07-26](laguna-s-2.1-int4-b70-102tps-20260726/) | Verify the approved LocalMaxxing receipt, restore the exact width-12 DFlash11 source/runtime identity, and run one fail-closed cold suite with token, text, cache, treatment, topology, and dual-accounting gates. |
| [DeepSeek V4 Flash uniform-K160 on 4x Intel Arc Pro B70, 80.820 tok/s, 2026-07-18](deepseek-v4-flash-k160-b70-80tps-20260718/) | Restore the exact vLLM/XPU/oneCCL source history and launch the closed-lane target-verified DSpark7 record with its pinned M7/M8, PIECEWISE, and sharded-target-argmax identity. |
| [Gemma 4 26B A4B Q8 on 1x Intel Arc Pro B70, 125 tok/s, 2026-07-01](gemma4-26b-a4b-q8-b70-125tps-20260701/) | Copy the current strict cold-suite Gemma 26B Q8 target plus Q4_0 MTP draft settings, 32K/FA/VMM command line, validity rules, and LocalMaxxing evidence. |
| [Gemma 4 26B A4B Q8 on 1x Intel Arc Pro B70, 95 tok/s, 2026-06-24](gemma4-26b-a4b-q8-b70-95tps-20260624/) | Prior/superseded Gemma 26B Q8 target plus Q4_0 MTP draft packet retained for history and patch archaeology. |
| [MiniMax M2.7 on B70, 110 tok/s, 2026-05-23](minimax-m27-b70-110tps-ubuntu24-20260523/) | Fresh Ubuntu 24 deployable MiniMax baseline with 32K OpenAI-compatible endpoint. |
| [MiniMax M2.7 on B70, 89 tok/s, 2026-05-20](minimax-m27-b70-89tps-20260520/) | Older strict-speed MiniMax packet retained for optimization comparisons. |
