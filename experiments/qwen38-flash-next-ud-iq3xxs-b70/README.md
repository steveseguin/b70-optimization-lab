# Qwen3.8 Flash-Next UD-IQ3_XXS (Unsloth), quantized compressed version

Publisher: `unsloth/Qwen3.8-Flash-Next-GGUF`, revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, all three `UD-IQ3_XXS` shards.
The owner approved the source and completed download; [packet 1](packet1/README.md)
now authenticates all three files, reconciles all 1,224 tensors and records this
model's first real CPU reference fixtures. **No inference result yet.**

The [owner's rule](../../AGENTS.md#lane-decisions-and-lane-notes), 2026-10-10:

> "treat the IQ3 as a model of its own ... lossless relative to what it is, not relative to FP8"

The [full decision](../../docs/own-xpu-runtime-objective.md#quantized-lines-are-separate-models-owner-decision-2026-10-10)
requires the same lossless, deterministic and no-cheating standard.
This is a separate model lane, with its own weights, oracle and records.
Lossless means unchanged output against these exact quantized bytes, including
fresh-process determinism and agreement with our CPU reference dequantization.
Differences from official FP8 are informational, never a tolerance gate.
The four-card FP8 lane remains the Flash-Next authority.

Our goal is our own model-specific Intel Xe runtime. The
[llama.cpp reference baseline](baseline-llamacpp/README.md) is a measurement
baseline for it to beat, **not our code base**. Nothing from that checkout is
copied into our runtime. Source support and successful compilation do not prove
GPU fit, speed, numerical correctness or determinism.

The [Stage 2 plan](../own-xpu-runtime/STAGE2-PLAN.md) and
[actual GGUF census](../own-xpu-runtime/stage2/packet1c/README.md) provide the
starting evidence. The reference screen is target-only: these GGUFs contain
no MTP block. The owner's native window and resolution of the current halt
remain prerequisites; this preparation performs no GPU work.

This lane carries the Stage 2 plan's separate two-card quantized model forward;
its CPU fixtures never inherit the official FP8 token oracle or quality gates.
The [FP8 lane](../../results/qwen38-flash-next-fp8-b70/HANDOFF.md) remains independent and
its four-card record is never presented as comparable to this compressed model.
Packet 1 confirms that the UD name describes a mixed-grid recipe: there are
no IQ3_XXS tensors. Packed target residency is 53,304,619,520 bytes across two
cards under the plan's PLE/embedding offload and HC-copy assumptions; native
fit is unmeasured. The optional official MTP source remains separately pinned
and unadmitted here.

[Admission note](notes/2026-10-10-packet1-weight-admission.md) ·
[Results status](results/README.md). Next is packet 2: quantized tokenizer,
production shape/operator contract and complete CPU oracle preparation.
