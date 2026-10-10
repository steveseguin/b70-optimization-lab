# Qwen3.8 Flash-Next UD-IQ3_XXS (Unsloth), quantized compressed version

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
