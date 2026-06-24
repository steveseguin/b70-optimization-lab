# Reproduction Recipes

This directory holds promoted reproduction recipes for benchmark results that
are worth preserving as standalone, shareable artifacts.

Each recipe should include enough detail to rebuild the runtime, prepare the
models, run the same benchmark shape, and inspect the result record without
depending on transient local notes.

## Recipes

| Recipe | Use It For |
| --- | --- |
| [Gemma 4 26B A4B Q8 on 1x Intel Arc Pro B70, 95 tok/s, 2026-06-24](gemma4-26b-a4b-q8-b70-95tps-20260624/) | Copy the current Gemma 26B Q8 target plus Q4_0 MTP draft settings, exact llama.cpp patch, command line, and LocalMaxxing evidence. |
| [MiniMax M2.7 on B70, 110 tok/s, 2026-05-23](minimax-m27-b70-110tps-ubuntu24-20260523/) | Fresh Ubuntu 24 deployable MiniMax baseline with 32K OpenAI-compatible endpoint. |
| [MiniMax M2.7 on B70, 89 tok/s, 2026-05-20](minimax-m27-b70-89tps-20260520/) | Older strict-speed MiniMax packet retained for optimization comparisons. |
