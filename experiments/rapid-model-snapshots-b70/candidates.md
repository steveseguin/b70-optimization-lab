# Candidate Notes

## Qwen3 30B-A3B / Qwen3-Coder 30B-A3B

Why first vLLM/XPU target:

- likely best new-model fit for the existing Intel/vLLM XPU path;
- MoE active-parameter profile should be B70-friendly;
- prior Qwen work gives us strong benchmark, variance, and graph discipline;
- useful to users as a modern general/coder family.

Initial plan:

1. inspect available INT4/GPTQ/FP8/GGUF variants and local fit;
2. start with vLLM/XPU if an official Qwen3 30B-A3B INT4/GPTQ path loads
   cleanly;
3. use short context (`4096` or `8192`) for rapid decode snapshots;
4. disable thinking where appropriate for apples-to-apples short decode;
5. compare against GGUF only if vLLM setup is poor or blocked.

Download/setup notes:

- `model.safetensors` is large enough that interrupted downloads should be
  verified before use. A 2026-07-04 resume attempt produced an oversized file
  that `safetensors` rejected with `file not fully covered`; it was quarantined
  in place with a `.corrupt-*` suffix and a fresh download was started into
  `model.safetensors.download`.
- Promote the download to `model.safetensors` only after both checks pass:
  exact byte size `16933256392` and a successful `safetensors.safe_open()`
  metadata read from the vLLM environment.
- `aria2c -c` is acceptable for speeding up a clean `.download` partial, but
  do not resume across files produced by different tools unless the partial is
  known to be the same raw object. HF/Xet redirects can make bad resumes look
  successful until `safetensors` validation catches them.

2026-07-04 vLLM/XPU GPTQ result:

- Official `Qwen/Qwen3-30B-A3B-GPTQ-Int4` downloaded and validated on the USB
  drive at `/mnt/usb-models/llm-models/qwen3-30b-a3b-gptq-int4`.
- Strict vLLM/XPU one-B70 startup attempt failed before readiness:
  `torch.ops._C.gptq_shuffle` is missing from this XPU build, and quick op
  inspection also showed `gptq_gemm`, `gptq_marlin_repack`, and `marlin_gemm`
  absent. Artifact directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/vllm-runs/qwen3-30b-a3b-gptq-int4-vllm-tp1-cg8-noprefix-realistic128-20260704T185920Z`.
- Do not count as a benchmark result; it never served. Treat as a runtime
  support blocker for GPTQ on the current local vLLM/XPU build.
- Pivot for the rapid lane: try a Q4+ GGUF under llama.cpp first, starting with
  `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF` `UD-Q4_K_XL`.

Watch-outs:

- do not reuse Qwen3.6-specific GDN/MTP assumptions blindly;
- record `COMPILATION_CONFIG`, XPU graph flags, TP/PP, and quant identity;
- keep prefix caching/APC off for headline rows.

Useful references:

- vLLM XPU supported-models table lists `Qwen/Qwen3-30B-A3B`,
  `Qwen/Qwen3-30B-A3B-GPTQ-Int4`, and
  `Qwen/Qwen3-coder-30B-A3B-Instruct` as XPU-supported:
  <https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/>.
- Intel/vLLM Arc Pro B-series notes describe MoE support and the persistent
  MoE GEMM direction for Qwen3-style MoE models:
  <https://vllm.ai/blog/2025-11-11-intel-arc-pro-b>.
- Qwen model card for the selected first checkpoint:
  <https://huggingface.co/Qwen/Qwen3-30B-A3B-GPTQ-Int4>.
- Possible later variant: `JunHowie/Qwen3-30B-A3B-Instruct-2507-GPTQ-Int4`
  claims a newer 2507 base and `desc_act=False` GPTQ Int4 setup. Do not switch
  before establishing the official Qwen baseline; treat it as a second-pass
  variant if the official checkpoint is valid but leaves obvious headroom.

## Mistral Small 3.2 24B Instruct

Why first llama.cpp dense target:

- useful dense instruct model size class;
- likely one-B70 fit at Q4/Q6 and possibly Q8 depending context/KV;
- llama.cpp GGUF setup should be fast;
- different architecture from Gemma/Qwen, useful snapshot for users.

Initial plan:

1. inspect available GGUF files and sizes;
2. download one high-quality file first, preferring Q8 if it fits, otherwise Q6
   or Q4_K-class;
3. run no-spec strict realistic baseline;
4. screen quick knobs (`ctx`, `ubatch`, FlashAttention, VMM, poll, threads);
5. try MTP/spec only if a target-verified draft path exists and is fresh-valid.

## Gemma 4 12B

Why queued:

- likely very fast on one B70;
- useful production reference;
- can compare vLLM AutoRound and llama.cpp GGUF.

Watch-outs:

- keep distinct from Gemma 4 26B Q8 production lane;
- do not move the Gemma 26B hot model while testing 12B.

2026-07-04 quick TP1 result:

- `gemma4-12b-int4-autoround-vllm-tp1-cg8-noprefix-realistic128`:
  `MAX_MODEL_LEN=4096`, graph PIECEWISE/capture 8, prefix caching disabled.
  Startup compiled after an `ocloc` error fallback, then first strict prompt
  failed with `UR_RESULT_ERROR_OUT_OF_RESOURCES` in XPU FlashAttention.
- `gemma4-12b-int4-autoround-vllm-tp1-eager-noprefix-ctx2k-realistic128`:
  `MAX_MODEL_LEN=2048`, `--enforce-eager`, prefix caching disabled. First
  strict prompt failed with the same FlashAttention `UR_RESULT_ERROR_OUT_OF_RESOURCES`.
- Conclusion: do not count Gemma 4 12B as a clean one-B70 rapid snapshot yet.
  Existing useful Gemma 12B material remains the documented TP4/c8 production
  profile in `experiments/gemma4-12b-int4-autoround-vllm/`; revisit TP1 only if
  we intentionally debug XPU FlashAttention/resource behavior or try another
  runtime/quant.

## Phi-4 Family

Why queued:

- compact high-speed reference;
- useful baseline for users who want smaller models.

## LocalMaxxing-Derived Second-Pass Candidates

2026-07-04 model-index scan:

- `Qwen/Qwen3-Coder-30B-A3B-Instruct`: practical 30B-A3B coder-family
  comparison after the base/instruct Qwen3 30B baseline.
- `nvidia/Nemotron-Cascade-2-30B-A3B`: reported in the same practical size
  class and likely worth a rapid vLLM probe if setup is not blocked.
- `zai-org/GLM-4.7-Flash`: 31B-class flash model with strong community
  throughput signals. Keep distinct from the larger GLM 5.x variants that were
  skipped as too large for this pass.
- `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct`: smaller MoE coder reference;
  useful if Qwen3-Coder setup is blocked or to compare runtime behavior.

Treat these as candidates, not claims. Each still needs model-size, quant,
runtime-support, quality, and strict fresh-response validation before promotion.

## Distill / Reasoning References

DeepSeek-R1-Distill-Qwen 14B/32B or similar can be sampled after the practical
instruct/coder models. Treat them as useful model-variation snapshots, not as
the main speed frontier.
