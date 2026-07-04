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

2026-07-04 Qwen3-Coder next-candidate note:

- Next rapid lane: `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF`
  `Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf`, HF revision
  `b17cb02dd882d5b6ab62fc777ad2995f19668350`, expected size
  `17665334432` bytes. Download target:
  `/mnt/usb-models/llm-models/qwen3-coder-30b-a3b-instruct-gguf/`.
- Rationale: same practical MoE size class as the promoted
  `Qwen3-30B-A3B-Instruct-2507` GGUF row (`107.484 tok/s`), but coder-tuned
  and very user-relevant. Qwen's public model card describes
  `Qwen3-Coder-30B-A3B-Instruct` as 30.5B total / 3.3B active, 48 layers, 128
  experts with 8 active, native 262K context, and non-thinking output. Use the
  same strict rapid suite and llama.cpp settings first.
- Available Q4-class Unsloth GGUF sizes from HF metadata at setup time:
  `IQ4_XS` `16378076320`, `IQ4_NL` `17310784672`, `Q4_0` `17379990688`,
  `UD-Q4_K_XL` `17665334432`, `Q4_K_S` `17456012448`, `Q4_K_M`
  `18556689568`, and `Q4_1` `19192503456` bytes. Start with `UD-Q4_K_XL` for
  continuity with the Qwen3 30B snapshot; only compare `IQ4_NL`/`Q4_K_M` if
  the first row is useful and download time is justified.

2026-07-04 Qwen3-Coder strict result:

- `UD-Q4_K_XL` downloaded cleanly to USB and matched size `17665334432` bytes.
- Promoted strict one-B70 row:
  `results/rapid-model-snapshots-b70/qwen3-coder-30b-a3b-instruct-udq4/README.md`.
  Representative evidence:
  `data/rapid-model-snapshots-b70/qwen3-coder-30b-a3b-instruct-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T214053Z.json`.
  Result: `108.1165394591524 tok/s` median tokens 1-100 after TTFT,
  p10 `106.57270050892973`, mean `105.32833006465762`, median TTFT
  `164.12943904288113 ms`, `cached_tokens=0` on all `12/12` prompts.
  LocalMaxxing approved it as `cmr6w2ekt00gimn01orbith22`.
- Quick four-GPU screen found only sub-percent movement: default ctx4096
  `107.76` / repeat `107.59`, ctx2048 high `108.30` but repeat `107.51`,
  ctx1024 `107.17`, ub512 `107.16`, poll0 `106.25`, poll100 `108.05` /
  confirm `108.12`. Treat `POLL=100`, ctx4096 as the representative first-pass
  row, not as a deep optimization.

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
  `aria2c` resume. Byte size matched `14548880928`, but the local SHA was
  `b9ba590957befd5fdb970de3668337883c59b70d54f9718f495bb8e9f3b71433` and
  the invalid run emitted no stream text chunks despite `completion_tokens=128`.
  Do not treat it as a model/runtime result. The file was quarantined on USB
  with a `.corrupt-sha-b9ba-20260704T2027` suffix.
- A clean single-stream `curl` download produced local SHA
  `bcf82c1d4963f91d744d202efeee0724c0987625cd97a737ea2af68b49f141cf`
  and streamed normal text. The earlier HTTP ETag
  `b735208f3cf85b9a11fe508e520fa9aa3afb8c384563e5755a7ab5a6bcce74f5`
  should not be treated as the file SHA for this object.
- Promoted strict `UD-Q4_K_XL` row, with server prompt cache disabled via
  `--cache-ram 0`: `27.29674347655439 tok/s` median tokens 1-100 after TTFT,
  p10 `27.126019755475596`, mean `27.356226121944818`, TTFT median
  `1501.7739470349625 ms`, `cached_tokens=0` on all `12/12` prompts. Evidence:
  `data/rapid-model-snapshots-b70/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-faon-cacheoff-v2-ctx4096-realistic128-20260704T205443Z.json`.
  LocalMaxxing approved it as `cmr6ura7300e4mn01yrdw7wto`; queue/response are
  `experiments/rapid-model-snapshots-b70/localmaxxing/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-realistic128-20260704.queue.json`
  and
  `data/localmaxxing-responses/mistral-small-3.2-24b-instruct-2506-udq4-llamacpp-realistic128-20260704.submit.log`.
- Quick four-GPU screen found no simple win over the cache-off baseline:
  `POLL=100` `24.956425259573045`, `UBATCH_SIZE=512`
  `25.267271232446316`, `CTX_SIZE=2048` `24.978475041077193`; FA-off did not
  reach readiness promptly and was killed during model fitting/loading.

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

2026-07-04 HF/GGUF metadata refresh while Qwen3-Coder downloaded:

- `unsloth/GLM-4.7-Flash-GGUF` has `UD-Q4_K_XL` at `17520169312` bytes and
  `Q4_K_M` at `18312339808` bytes; likely the best next 30B-class rapid model
  after Qwen3-Coder if we want another high-value MoE snapshot.
  Download target:
  `/mnt/usb-models/llm-models/glm-4.7-flash-gguf/GLM-4.7-Flash-UD-Q4_K_XL.gguf`,
  revision `0d32489ecb9db6d2a4fc93bd27ef01519f95474d`.
  Architecture notes from `zai-org/GLM-4.7-Flash`: `30B-A3B` MoE,
  `Glm4MoeLiteForCausalLM`, 64 routed experts + 1 shared expert, 4 experts per
  token, MLA-style attention. Q8 is `~31.8GB` (`Q8_0`) to `~35.6GB`
  (`UD-Q8_K_XL`), so it is too tight or impossible for a clean one-B70 strict
  row with KV/cache overhead; start with `UD-Q4_K_XL`.
  Runtime plan for the first strict row: llama.cpp/SYCL, one B70, `ctx=4096`,
  F16 KV, FlashAttention on, `--jinja`, `--reasoning off`, `--cache-ram 0`,
  per-request `{"cache_prompt":false}`. Avoid KV quant on the first pass:
  public llama.cpp GLM-4.7-Flash reports include FlashAttention + KV-quant
  failures, especially on longer prompts. General-use sampling guidance from
  Z.ai/Unsloth (`temp=1.0`, `top_p=0.95`, `min_p=0.01`, neutral repeat
  penalty) is useful for deployments but not for strict benchmark rows, which
  stay deterministic (`temperature=0`, `top_p=1`).
- `bartowski/zai-org_GLM-4.7-Flash-GGUF` has `IQ4_XS` `16250044288`,
  `Q4_K_M` `18474983296`, and `Q4_K_L` `18710400896` bytes. Use only if the
  Unsloth GLM file fails or if we specifically want a bartowski/imatrix
  comparison.
- `bartowski/nvidia_Nemotron-Cascade-2-30B-A3B-GGUF` has `IQ4_XS`
  `18166698432`, `Q4_K_M` `24725740992`, and `Q4_K_L` `24857861568` bytes.
  The Q4_K_M/L files are larger and may be slower to load, but this is a useful
  model-family snapshot if we continue the rapid pass.
- `bartowski/microsoft_Phi-4-mini-instruct-GGUF` is small enough to run quickly:
  `Q4_K_M` `2491874688` bytes and `Q8_0` `4084611456` bytes. Use as a compact
  sanity/reference lane after the 30B-class candidates; do not compare its
  throughput directly against 30B-class MoE models as a quality-equivalent
  result.

Treat these as candidates, not claims. Each still needs model-size, quant,
runtime-support, quality, and strict fresh-response validation before promotion.

2026-07-04 GLM-4.7-Flash strict result:

- `GLM-4.7-Flash-UD-Q4_K_XL.gguf` downloaded cleanly to the USB model store
  and matched the expected byte size `17520169312`.
- Promoted strict one-B70 row:
  `results/rapid-model-snapshots-b70/glm-4.7-flash-udq4/README.md`.
  Representative evidence:
  `data/rapid-model-snapshots-b70/glm-4.7-flash-udq4-llamacpp-faon-cacheoff-poll100-confirm-ctx4096-realistic128-20260704T221455Z.json`.
  Result: `40.7691297367011 tok/s` median tokens 1-100 after TTFT,
  p10 `40.01936615541169`, mean `40.26057811873019`, median TTFT
  `206.20633498765528 ms`, `cached_tokens=0` on all `12/12` prompts.
  LocalMaxxing approved it as `cmr6xkr2f00gomn01k4u2dua8`.
- Faster `~44 tok/s` rows appeared in concurrent four-GPU screens, but
  standalone confirmations on GPU0/GPU1 landed around `40.7 tok/s`, so the
  conservative standalone row is the headline.
- A temporary GPU0 frequency lock to `2800,2800` MHz held under load and
  reported no throttling, but did not improve throughput; the GPU was restored
  to the default `400,2800` range. This points to model/runtime architecture
  cost rather than a simple clocking issue.
- Treat this lane as a valid expected-performance snapshot, not a frontier
  target. Revisit only for a new GLM-specific llama.cpp/SYCL kernel path,
  another materially better GLM quant, or a vLLM/XPU runtime path.

## Distill / Reasoning References

DeepSeek-R1-Distill-Qwen 14B/32B or similar can be sampled after the practical
instruct/coder models. Treat them as useful model-variation snapshots, not as
the main speed frontier.
