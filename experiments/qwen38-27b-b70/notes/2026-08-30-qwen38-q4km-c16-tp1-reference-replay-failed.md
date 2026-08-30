# Qwen3.8-27B Q4_K_M c16 TP1 intermediate-reference replay: failed

The fresh intermediate-reference replay matched only **11/16** frozen token-ID sequences. Completion, zero-cache, isolation, collision, WDC-negative, kernel, and cleanup gates passed; its 15.76202373510137 tok/s rate is diagnostic only.

This profile had disabled the explicit lab fused attention/GDN/MMVQ/Q8-handoff and forced-reorder doors, so those features as a group are not sufficient to explain nondeterminism. Live census showed Q8 quantization dedup still default-on at mode 1, plus other integration defaults. The next screen isolates Q8 dedup by setting `GGML_SYCL_Q8_QUANT_DEDUP=0` while preserving the rest of this intermediate reference profile.
