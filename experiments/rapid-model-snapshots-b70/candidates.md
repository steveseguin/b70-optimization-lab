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
- This appears aligned with upstream reports such as
  <https://github.com/vllm-project/vllm/issues/39474> ("GPTQ models fail to
  load on Intel XPU" with missing `_C.gptq_shuffle`). Newer vLLM XPU docs still
  list this model as supported, so a later recovery lane should try an updated
  Intel/vLLM container or v0.22.x+ XPU build before writing off GPTQ entirely:
  <https://docs.vllm.ai/en/v0.22.1/models/hardware_supported_models/xpu/>.
- Pivot for the rapid lane: try a Q4+ GGUF under llama.cpp first, starting with
  `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF` `UD-Q4_K_XL`.

2026-07-04 llama.cpp/GGUF strict result:

- Download completed on the USB drive:
  `/mnt/usb-models/llm-models/qwen3-30b-a3b-instruct-2507-gguf/Qwen3-30B-A3B-Instruct-2507-UD-Q4_K_XL.gguf`.
  File size was verified as `17690497440` bytes, matching the remote object.
- HF revision: `eea7b2be5805a5f151f8847ede8e5f9a9284bf77`.
- First diagnostic llama.cpp run with default `cache_prompt=true` was invalid:
  it reported `cached_tokens=3` after the first prompt. Keep the rapid
  llama.cpp runner default `{"cache_prompt":false}` for strict headline rows.
- Promoted first-pass strict row:
  `results/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4/README.md`.
  Representative evidence:
  `data/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128-20260704T193409Z.json`.
  Result: `107.48388363267362 tok/s` median tokens 1-100 after TTFT,
  p10 `106.89774398673791`, mean `104.9928121456826`, median TTFT
  `166.9534610118717 ms`, `cached_tokens=0` on all `12/12` prompts.
- Same-window quick knob screen did not find a reproducible win:
  `UBATCH_SIZE=512`, `BATCH_SIZE=512`, `POLL=0`, `POLL=100`,
  `POLL=100 UBATCH_SIZE=1024`, `THREADS=16`, and `GGML_SYCL_ENABLE_VMM=0`
  all landed within noise or below the simple default. The one `POLL=0`
  `108.00493036986039 tok/s` high did not repeat (`106.14230746788732`), so do
  not promote it as a recipe change.

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

2026-07-04 setup note:

- Starting with `unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF`
  `Mistral-Small-3.2-24B-Instruct-2506-UD-Q8_K_XL.gguf`, HF revision
  `b750ec2299225e492f1bd27cab88a0a595fa848f`.
- Expected object size: `28991868448` bytes.
- The partial Q8 download was moved off NVMe to
  `/mnt/usb-models/llm-models/mistral-small-3.2-24b-instruct-2506-gguf/`
  and resumed there. Do not use NVMe for this large Q8 candidate unless it
  becomes the active hot path.
- LocalMaxxing public API had two existing base-model rows near `39.5 tok/s`,
  but none for the Unsloth GGUF HF ID at time of setup. Treat our row as a
  useful one-B70 B70/Q8 snapshot if it serves and passes the strict gate.
- Because Q8 is about `29 GB`, first try a fully-GPU fit. If `ctx=4096` spills
  layers to CPU or fails, use `ctx=2048` before lowering KV precision. If Q8 is
  fundamentally too tight, pivot to Q6 or `UD-Q4_K_XL` and label the quality
  class separately.

2026-07-04 Q8/Q4 first-pass notes:

- `Mistral-Small-3.2-24B-Instruct-2506-UD-Q8_K_XL.gguf` downloaded cleanly to
  the USB model store and matched the expected byte size `28991868448`.
- Q8 strict one-B70 `ctx=4096`, FA-on, F16 KV, prompt cache disabled per
  request passed the strict gate but was not competitive:
  `16.380395177161446 tok/s` median tokens 1-100 after TTFT, p10
  `16.33483296767248`, mean `16.394351802026414`, median TTFT
  `2686.1701778834686 ms`, `cached_tokens=0` on all `12/12` prompts. Evidence:
  `data/rapid-model-snapshots-b70/mistral-small-3.2-24b-instruct-2506-udq8-llamacpp-faon-ctx4096-realistic128-20260704T201848Z.json`.
  Treat as a valid diagnostic/fit result, not a useful promoted row unless a
  high-quality Q8 baseline is explicitly needed.
- The first `UD-Q4_K_XL` file was contaminated by a failed multi-range
  `aria2c` resume: byte size matched `14548880928`, but local SHA
  `b9ba590957befd5fdb970de3668337883c59b70d54f9718f495bb8e9f3b71433`
  did not match the HF ETag/SHA
  `b735208f3cf85b9a11fe508e520fa9aa3afb8c384563e5755a7ab5a6bcce74f5`.
  The invalid run emitted no stream text chunks despite `completion_tokens=128`;
  do not treat it as a model/runtime result. The file was quarantined on USB
  with a `.corrupt-sha-b9ba-20260704T2027` suffix and a clean single-stream
  download was started.

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

## Gemma 4 E4B

Why sampled:

- already present locally as a small GGUF;
- useful sanity check for the rapid llama.cpp harness while larger downloads
  are in flight.

2026-07-04 quick result:

- `gemma-4-E4B-it-Q4_0.gguf`, one B70, llama.cpp/SYCL, `ctx=4096`, FA-on,
  F16 KV, strict realistic suite with `cached_tokens=0` passed the gate but was
  unexpectedly slow: `23.05365781067809 tok/s` median tokens 1-100 after TTFT,
  p10 `22.396720763242648`, mean `23.218213001293122`, median TTFT
  `277.40637050010264 ms`.
- Evidence:
  `data/rapid-model-snapshots-b70/gemma4-e4b-it-q4-llamacpp-faon-ctx4096-realistic128-20260704T203603Z.json`.
- Treat as a valid internal reference only, not a promoted/public row. This
  model/quant/runtime combination is too slow for its size and should be
  revisited only if we specifically care about Gemma E4B or have a better
  runtime/quant candidate.

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
