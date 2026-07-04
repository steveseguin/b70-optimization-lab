# LocalMaxxing Submissions

Date: 2026-06-27

Model: `unsloth/gemma-4-26B-A4B-it-GGUF`, Gemma 4 26B A4B Q8 lane.

Status: active Gemma 4 Q8 B70 optimization. As of 2026-06-27, Gemma rows in
this ledger that were submitted from synthetic, repeated, or filled-long
benchmarks are classified as **diagnostic / pre-final-gate** unless they link a
passing fixed realistic prompt-suite result. Do not cite them as representative
real-world decode throughput. Keep single-replica records separate from four
independent replica aggregate capacity, and keep natural-stop, short-prompt
sustained, and filled-long sustained shapes separate.

Hardware note for the Gemma 4 26B submissions: these were run on a headless
Supermicro AMD Threadripper PRO 5955WX platform with 128 GB DDR4 and Intel Arc
Pro B70 32 GB GPUs. The `cmqwkedg303jeqr013z753j62` submission used one B70
replica on GPU0, but is now diagnostic/pre-final-gate until revalidated; the
host has four B70s available for parallel single-replica experiments.

Required current submission gate: fixed realistic prompt suite, one cold
response per prompt, `cached_tokens=0` every row, no prompt/KV/context/response
reuse or n-gram/history acceleration, target model/quantization unchanged,
verified speculation only, and primary metric
`median_tok_s_1_100_after_ttft`.

The Gemma table below is a historical submission ledger. Rows that do not link
a passing fixed-suite realistic-gate artifact are **diagnostic / pre-final-gate
only**, even if their original labels used `fresh` or the first measured row had
`cached_tokens=0`. A single synthetic/filled-long row0 is not enough for a
current headline claim or a new LocalMaxxing submission.

Date: 2026-07-03

Model: `Intel/Qwen3.6-27B-int4-AutoRound`, AutoRound INT4 W4A16, vLLM/XPU on
one Intel Arc Pro B70.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total | Validation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `qwen36-27b-webhie-int4-autoround-b70-vllm-realistic-int8lmhead-bf16scale-mtp3-cg8-65tok-20260703` | `cmr5iu3gk00bfq901nidgcana` | 1 | 69 | 128 | **65.276 median 1-100 after TTFT** | 49.172 median wall full128 | **policy-compliant realistic suite, current Qwen27 record**: fixed `qwen36-27b-autoround-int4-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, `qwen3_next_mtp` accepted tokens verified by the target model. Config matches the promoted webhie MTP3/cg8 runtime INT8 LM-head lane plus BF16 scale storage (`VLLM_XPU_LM_HEAD_INT8_BF16_SCALES=1`), preserving INT8 LM-head weights while reducing scale bandwidth/format cost. Full quality gate passed and matched the prior webhie INT8-LM-head baseline, including 32-repeat stability and 1K long-context needle with cached tokens zero. Strict fresh BF16-scale support rows: `65.005`, `64.864`; same-window FP32-scale controls: `64.234`, `64.090`; baseline reconfirm: `64.431`; primary p10 `59.609`, mean `65.077`, TTFT median `603.580 ms`. Result packet `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`, queue `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-bf16scale-20260703.queue.json`, approved response `data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-bf16scale-20260703.submit.log`. |
| `qwen36-27b-webhie-int4-autoround-b70-vllm-realistic-int8lmhead-mtp3-cg8-64tok-20260703` | `cmr576apv0079q901i6dvsh0l` | 1 | 69 | 128 | **64.306 median 1-100 after TTFT** | 48.194 median wall full128 | **policy-compliant realistic suite, webhie AutoRound variant**: fixed `qwen36-27b-autoround-int4-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, `qwen3_next_mtp` accepted tokens verified by the target model. Config matches the promoted MTP3/cg8 lane plus `VLLM_XPU_LM_HEAD_INT8=1`; label as `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head`, separate from the Intel checkpoint row. Full quality gate passed and matched the prior Intel INT8-LM-head baseline, including 32-repeat stability and 1K long-context needle. Initial webhie support row: `63.336`; same-window Intel INT8-LM-head control: `62.366`; primary p10 `59.496`, mean `63.615`, TTFT median `605.938 ms`. Result packet `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-20260703.json`, queue `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-20260703.queue.json`, approved response `data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-20260703.submit.log`. |
| `qwen36-27b-int4-autoround-b70-vllm-realistic-int8lmhead-mtp3-cg8-62tok-20260703` | `cmr4zkcxb003yq9018408i1pn` | 1 | 69 | 128 | **62.628 median 1-100 after TTFT** | 47.656 median wall full128 | **policy-compliant realistic suite, separate runtime-quantized variant**: fixed `qwen36-27b-autoround-int4-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, target model unchanged, `qwen3_next_mtp` accepted tokens verified by the target model. Config matches the promoted MTP3/cg8 lane plus `VLLM_XPU_LM_HEAD_INT8=1`, which keeps the BF16 `lm_head` resident but uses a default-off transient per-output-channel INT8 LM-head projection; label as `AutoRound INT4 W4A16 + runtime INT8 LM-head`, not the original BF16-LM-head AutoRound identity. Full quality gate passed and matched baseline, including 32-repeat stability and 1K long-context needle. Same-window BF16-LM-head control: `53.332`; INT8 repeat: `62.276`; primary run p10 `58.104`, mean `62.998`, TTFT median `606.575 ms`. Result packet `results/qwen36-27b-autoround-int4-b70/int8-lmhead-20260703.json`, patch `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-quality-pass-20260703.patch`, queue `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-int4-int8lmhead-20260703.queue.json`, approved response `data/localmaxxing-responses/qwen36-27b-int4-int8lmhead-20260703.submit.log`. |
| `qwen36-27b-int4-autoround-b70-vllm-realistic-promotesource-mtp3-cg8-53tok-20260703` | `cmr4gokx90061nv01lhoe3ft8` | 1 | 69 | 128 | **53.522 median 1-100 after TTFT** | 42.545 median wall full128 | **policy-compliant realistic suite**: fixed `qwen36-27b-autoround-int4-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, target model/quant unchanged, `qwen3_next_mtp` accepted tokens verified by the target model. Config: TP1, XPU graph on, `num_speculative_tokens=3`, `max_cudagraph_capture_size=8`, `MAX_NUM_BATCHED_TOKENS=1024`, `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`, `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`. Quality suite passed and matched baseline. Support rows: `54.861` and `53.992`; same-window plain-MTP3/cg8 control: `48.345`. Result packet `results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.md`, queue `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-int4-promotesource-20260703.queue.json`, approved response `data/localmaxxing-responses/qwen36-27b-int4-promotesource-20260703.submit2.log`. First POST failed only because top-level `promptTokens` was `68.5`; queue was corrected to integer `69` while preserving per-prompt token counts in `engineFlags`. |

Date: 2026-07-04

Model: `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF`, GGUF
`UD-Q4_K_XL`, llama.cpp/SYCL on one Intel Arc Pro B70.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total | Validation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `qwen3-30b-a3b-instruct-2507-udq4-llamacpp-realistic128` | `cmr6rr2kv008imn019frg0x3m` | 1 | suite median 65 | 128 | **107.484 median 1-100 after TTFT** | 94.118 median wall full128 | **policy-compliant rapid realistic suite**: fixed `rapid-model-snapshots-b70-realistic-v1`, 12 unique prompts, each prompt once, llama.cpp `cache_prompt=false`, `cached_tokens=0` every row, no prompt/KV/context checkpoint/response reuse, no n-gram/history acceleration, no speculation. Config: `Qwen3-30B-A3B-Instruct-2507-UD-Q4_K_XL.gguf`, HF revision `eea7b2be5805a5f151f8847ede8e5f9a9284bf77`, llama.cpp/SYCL on one B70, `ctx=4096`, `batch=1024`, `ubatch=256`, FlashAttention on, f16 KV. Primary p10 `106.898`, mean `104.993`, full-output after-TTFT median `107.421`, TTFT median `166.953 ms`. Result packet `results/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4/README.md`, evidence `data/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128-20260704T193409Z.json`, queue `experiments/rapid-model-snapshots-b70/localmaxxing/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-realistic128-20260704.queue.json`, approved response `data/localmaxxing-responses/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-realistic128-20260704.submit.log`. A quick four-GPU runtime sweep found no reproducible sub-percent knob win; this is a first-pass rapid snapshot, not a deep per-model optimization lane. |

Date: 2026-07-04

Model: `unsloth/Qwen3.6-27B-MTP-GGUF`, GGUF `UD-Q4_K_XL`, llama.cpp/SYCL on
one Intel Arc Pro B70.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total | Validation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `qwen36-27b-mtp-gguf-q4-b70-llamacpp-realistic-mtp3-30tok-20260703` | `cmr6mn5ct0076mn01on3dnpyn` | 1 | 69 | 128 | **30.679 median 1-100 after TTFT** | 26.581 median wall full128 | **policy-compliant realistic suite, non-competitive model/runtime reference**: fixed `qwen36-27b-autoround-int4-b70-realistic-v1`, 12 unique prompts, each prompt once, `cached_tokens=0` every row, no prompt/KV/context checkpoint/response reuse, no n-gram/history acceleration, draft-MTP3 accepted tokens verified by the target GGUF model. Config: `Qwen3.6-27B-UD-Q4_K_XL.gguf`, llama.cpp/SYCL `9860 (fdb1db877)`, one B70, `ctx=4096`, `batch=1024`, `ubatch=256`, FlashAttention on, f16 KV, `n_max=3`, `n_min=0`, `p_min=0.00`, `--ctx-checkpoints 0`. Primary p10 `27.589`, mean `30.405`, full-output after-TTFT median `29.860`, TTFT median `499.824 ms`. Result packet `results/qwen36-27b-mtp-gguf-q4-b70/README.md`, evidence `data/qwen36-27b-mtp-gguf-q4-b70-baselines/llamacpp-mtp3-aot-np1-realistic128-20260703T060748Z.json`, queue `experiments/qwen36-27b-mtp-gguf-q4-b70/localmaxxing/qwen36-27b-gguf-q4-mtp3-20260703.queue.json`, approved response `data/localmaxxing-responses/qwen36-27b-gguf-q4-mtp3-20260703.submit.log`. This row is useful for expected-performance comparison but does not displace the faster AutoRound vLLM Qwen27 record. |

Date: 2026-07-03

Model: `unsloth/gemma-4-26B-A4B-it-GGUF`, Gemma 4 26B A4B Q8 lane,
llama.cpp/SYCL on one Intel Arc Pro B70.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total | Validation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-26b-a4b-q8-b70-llamacpp-service-32k-smoke-20260703` | `cmr47ivql0045nv011pfdjlaa` | 1 | 32571 | 76 | **115.179 after TTFT** | 979.156 prompt+output wall | **approved long-context service / prompt-processing result, not the short-decode headline**: one cold near-32K request from `lc-24000-late`, `cached_tokens=0`, unique prompt, exact JSON retrieval passed, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; `tokSPrefill=996.600`, TTFT `32682 ms`; supporting service ladder passed `32/32` long-context rows and `64/64` canary rows across four B70 lanes with average lane median prefill `1192.965 tok/s` and long-context decode `131.786 tok/s`; payload `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-service-32k-20260703.payload.json`, response `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-service-32k-20260703.submit.log` |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-finalpostnorm-faon-vmm-ctx32768-full512-124tok-20260701` | `cmr1u77na01k2ld01kalwzs1e` | 1 | suite median 69 | 512 | **124.977 median 1-100 after TTFT** | 108.581 median wall full512 | **policy-compliant realistic suite**: exact promoted full512 recipe rerun after the LM-head/Q8 subgroup experiment; fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; FA-on 32K/VMM VDR2 selected-down baseline plus `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`; reordered-Q8 VDR2, VDR2 selected-down fused weighted-sum, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `CTX_SIZE=32768`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, LM-head subgroup unset; p10 `103.836`, mean `122.474`, full512 after-TTFT `114.871`, TTFT median `178.694 ms`; valid but high-variance, with same exact batch support `121.591`, `119.264`, `113.633`; supersedes `cmr01nnet000mld01x2tt6qds` |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-finalpostnorm-faon-vmm-ctx32768-full512-123tok-20260630` | `cmr01nnet000mld01x2tt6qds` | 1 | suite median 69 | 512 | **123.677 median 1-100 after TTFT** | 106.441 median wall full512 | **policy-compliant realistic suite**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; FA-on 32K/VMM VDR2 selected-down baseline plus `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`; reordered-Q8 VDR2, VDR2 selected-down fused weighted-sum, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `CTX_SIZE=32768`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `105.673`, mean `120.825`, full512 after-TTFT `110.683`, TTFT median `179.125 ms`; valid but high-variance, with second finalpost `116.551` and controls `117.873` / `114.709`; supersedes `cmqztiqdn02vnoe01egox6q3f` |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-faon-vmm-ctx32768-full512-121tok-20260629` | `cmqztiqdn02vnoe01egox6q3f` | 1 | suite median 69 | 512 | **121.414 median 1-100 after TTFT** | 105.881 median wall full512 | **policy-compliant realistic suite**: same FA-on 32K/VMM VDR2 selected-down baseline/control identity as the previous `117.914` row; fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, VDR2 selected-down fused weighted-sum, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `CTX_SIZE=32768`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; LM-head experiment flags unset (`LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV=0`, `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_NO_REORDER=0`); p10 `107.032`, mean `120.136`, full512 after-TTFT `110.391`, TTFT median `179.118 ms`; supporting same-family confirmation `119.948` plus lower variance rows `113.572`, `114.088`, `111.988`; supersedes the FA-on 32K/VMM `117.914` row |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-faon-vmm-ctx32768-full512-20260629` | `cmqzq5zu402troe01t774uyox` | 1 | suite median 69 | 512 | **117.915 median 1-100 after TTFT** | 106.807 median wall full512 | **policy-compliant realistic suite, superseded by same-family baseline row**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, VDR2 selected-down fused weighted-sum, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `CTX_SIZE=32768`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `107.807`, mean `118.881`, full512 after-TTFT `110.958`, TTFT median `180.169 ms`; superseded by `cmqztiqdn02vnoe01egox6q3f` at `121.414` and then `cmr01nnet000mld01x2tt6qds` at `123.677` |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-repeat-20260629` | `cmqyrpox4021dqk01co5o4fcw` | 1 | suite median 69 | 512 | **115.847 median 1-100 after TTFT** | 100.640 median wall full512 | **policy-compliant realistic suite**: same VDR2 selected-down recipe as the prior `115.728` row; fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, VDR2 selected-down fused weighted-sum, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `102.573`, mean `114.574`, full512 after-TTFT `104.661`, TTFT median `181.167 ms`; BF16-direct lanes in the adjacent retest did not beat controls; supersedes the selected-down `115.728` row |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-20260629` | `cmqyo0jyt08ippk01vhiobdnm` | 1 | suite median 69 | 512 | **115.728 median 1-100 after TTFT** | 100.228 median wall full512 | **policy-compliant realistic suite, superseded by same-recipe repeat**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, VDR2 selected-down fused weighted-sum, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `101.449`, mean `113.158`, full512 after-TTFT `104.602`, TTFT median `181.348 ms`; supporting full512 confirmations measured `113.471`, `113.815`, and `114.811`; supersedes the bulk sampled-ID verifier row `98.340` |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-bulksampled-full512-20260628` | `cmqxchyra03xmqr01b963gmi1` | 1 | suite median 69 | 512 | **98.340 median 1-100 after TTFT** | 87.737 median wall full512 | **policy-compliant realistic suite**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `85.979`, mean `95.953`, full512 after-TTFT `91.174`, TTFT median `180.211 ms`; supporting full512 confirmations measured `96.015`, `95.903`, and `94.941`; supersedes the F16-p021 `95.825` row |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-smallncols-full512-20260628T010121` | `cmqx3687103v4qr01ace1ft3m` | 1 | suite median 69 | 512 | **95.825 median 1-100 after TTFT** | 88.262 median wall full512 | **policy-compliant realistic suite, superseded**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `85.504`, mean `95.605`, full512 after-TTFT `91.142`, TTFT median `179.723 ms`; supporting full512 confirmations measured `95.817`, `93.422`, and `95.566`; superseded by bulk sampled-ID verifier row `98.340` |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-recordconfirm-20260627T221722` | `cmqwxep4a03qiqr010chjn93s` | 1 | suite median 69 | 512 | **90.983 median 1-100 after TTFT** | 82.897 median wall full512 | **policy-compliant realistic suite**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `80.120`, mean `90.184`, full512 after-TTFT `85.919`, TTFT median `179.287 ms`; supporting strict repeats in the same batch measured `88.571`, `89.873`, and `87.300`, with a prior same-identity high observation at `91.393`; submitted conservatively from the repeated-confirmation batch and supersedes the VDR2 `90.322` row |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v21-20260627T201757` | `cmqwt1zk803ozqr01hctqss2z` | 1 | suite median 69 | 512 | **90.322 median 1-100 after TTFT** | 83.212 median wall full512 | **policy-compliant realistic suite**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `86.029`, mean `92.180`, full512 after-TTFT `86.217`, TTFT median `179.681 ms`; supporting strict VDR2 rows `89.455`, `89.437`, `88.063`, and `85.906`; supersedes the VDR2 `89.455` row and VDR4 `87.611` row |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627T191931` | `cmqwqzayr03o8qr01j6lgx93n` | 1 | suite median 69 | 512 | **89.455 median 1-100 after TTFT** | 80.625 median wall full512 | **policy-compliant realistic suite, superseded**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; reordered-Q8 VDR2, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`; p10 `77.556`, mean `87.849`, full512 after-TTFT `84.452`; supporting strict VDR2 rows `87.308`, `87.240`, `87.274`, and `88.906`; superseded by the VDR2 `90.322` row |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-mtp-n3-nmin2-p005-ub1024-v8-20260627T174753` | `cmqwnl2ag03lgqr01ch5bxknq` | 1 | suite median 69 | 512 | **87.611 median 1-100 after TTFT** | 77.865 median wall full512 | **policy-compliant realistic suite, superseded**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; prior VDR4 high in the confirmed `n3/p0.05/UB1024` family, with prior strict rows `84.825`, `83.836`, and `84.527`; superseded by the VDR2 `90.322` strict row |
| `gemma4-26b-a4b-q8-b70-llamacpp-realistic-mtp-n3-nmin2-p005-ub1024-20260627T171157` | `cmqwn5wq703l3qr01ilxrw6p2` | 1 | suite median 69 | 512 | **84.825 median 1-100 after TTFT** | 78.321 median wall full512 | **policy-compliant realistic suite**: fixed `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt once, `cached_tokens=0` every row, no prompt/KV/context/response reuse, no n-gram/history acceleration, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target; confirmations `83.836` and `84.527` in same `n3/p0.05/UB1024` family |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627T155347` | `cmqwkedg303jeqr013z753j62` | 1 | 588 | 512 | 176.216 first / 176.403 mean | 139.317 | 1536 repeats / 6144 canary rows passed; Q8 target/verifier with Q4_0 MTP draft only; same Q8 MoE-ID reorder broad verifier path as the prior UB720 record, with reordered Q8_0 MMVQ compile knob `GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2`; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; not warmed/history/ngram accelerated |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub720-nmin3-pmin010-fresh-20260627T144855` | `cmqwi45d803gyqr01td3vf9ka` | 1 | 588 | 512 | 171.108 first / 170.129 mean | 135.666 | 1536 repeats / 6144 canary rows passed; Q8 target/verifier with Q4_0 MTP draft only; same Q8 MoE-ID reorder broad verifier path as the superseded UB704 record, with `UBATCH_SIZE=720`; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; not warmed/history/ngram accelerated |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub704-nmin3-pmin010-fresh-20260627T143126` | `cmqwhkbzj03guqr01h00c8n04` | 1 | 588 | 512 | 170.112 first / 169.876 mean | 134.896 | 1536 repeats / 6144 canary rows passed; Q8 target/verifier with Q4_0 MTP draft only; same Q8 MoE-ID reorder broad verifier path as the superseded UB768 record, with `UBATCH_SIZE=704`; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; not warmed/history/ngram accelerated |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub768-nmin3-pmin010-fresh-20260627T142318` | `cmqwh8du403gfqr01d6ut1ddo` | 1 | 588 | 512 | 169.949 first / 169.550 mean | 135.182 | 1536 repeats / 6144 canary rows passed; Q8 target/verifier with Q4_0 MTP draft only; adds `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` + `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1` to the prior route-cache/fused-output/fused-selected-softmax/RMS-reuse stack; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; not warmed/history/ngram accelerated |
| `gemma4-26b-a4b-q8-b70-llamacpp-syclopt0-faoff-20260623T0715` | `cmqq8phxt0103qo01afcgyjq8` | 1 | 574 | 156 | 41.806 | n/a | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-syclopt0-faoff-parallel1-cache0-20260623T0915` | `cmqq9nqbh010gqo01a9jnzl6r` | 1 | 574 | 146 | 42.154 | n/a | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-syclopt0-faoff-parallel1-cache0-long512-20260623T0945` | `cmqqa6zbx010xqo01cdtfn8e0` | 1 | 75 | 512 | 42.716 | 41.351 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n3-aot-repeat-long512-20260623T0353` | `cmqqctk4w014kqo011gyyks7r` | 1 | 75 | 512 | 48.347 | 46.602 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n3-aot-filledlong512-20260623T0853` | `cmqqexo5x0151qo0154xsie7s` | 1 | 588 | 512 | 68.192 | 63.428 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n3-aot-psplit020-filledlong512-20260623T0858` | `cmqqf759s0154qo01gwqa14uc` | 1 | 588 | 512 | 68.515 | 63.666 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n4-aot-filledlong512-20260623T0858` | `cmqqf75p70157qo018fsavf0g` | 1 | 588 | 512 | 74.395 | 68.797 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n4-aot-psplit020-filledlong512-20260623T0907` | `cmqqfe75s015aqo01xr94yxh0` | 1 | 588 | 512 | 74.498 | 68.900 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n6-aot-nmin2-pmin015-filledlong512-20260623T0912` | `cmqqfnilo015lqo011nm0q2tn` | 1 | 588 | 512 | 83.520 | 76.569 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin015-filledlong512-20260623T0919` | `cmqqfv296015sqo0126mym3ko` | 1 | 588 | 512 | 87.878 | 80.252 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin010-filledlong512-20260623T0925` | `cmqqg1r0l015xqo01e6d696mx` | 1 | 588 | 512 | 88.345 | 80.553 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin010-nobs-filledlong512-20260623T0936` | `cmqqgftv50160qo01km3s7lkt` | 1 | 588 | 512 | 90.243 | 82.243 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filledlong512-20260623T0941` | `cmqqgn3cm0163qo010optg91u` | 1 | 588 | 512 | 90.419 | 82.342 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623T1018` | `cmqqi1p2c016jqo01vndau1y9` | 1 | 588 | 512 | 91.050 | 82.970 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623` | `cmqqkmbhr017oqo017rdfxqh2` | 1 | 588 | 512 | 91.157 | 71.057 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-fasttopk10-filledlong512-20260623T1508` | `cmqqsecuk01azqo018ahv0i1s` | 1 | 588 | 512 | 91.619 | 71.287 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-fasttopk10-cpucleanup-filledlong512-20260623T2217` | `cmqr7ni7u01gxqo01wtqsrn3u` | 1 | 588 | 512 | 91.877 first / 91.899 mean | 71.485 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623T2228` | `cmqr82niq01hgqo01v42y7ue8` | 1 | 588 | 512 | 92.397 first / 92.767 mean | 83.289 | 384/384 chat canary; conservative diagnostic pre-final-gate first-request metric only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624T0812` | `cmqrsupdk000jqr01af3eu6vu` | 1 | 588 | 512 | 95.264 first / 95.386 mean | 81.285 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; diagnostic pre-final-gate first-request metric only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-fresh-20260624T1432` | `cmqs4jnx100k6qr01d1iy78kl` | 1 | 588 | 512 | 96.822 first / 97.226 mean | 82.462 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; direct argmax-ID unroll + q-only assistant inputs; diagnostic pre-final-gate first-request metric only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-fresh-20260624T1357` | `cmqs56wv100kjqr01de3fdspd` | 1 | 588 | 512 | 98.491 first / 97.886 mean | 86.194 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; direct argmax-ID unroll + q-only assistant inputs; `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`; diagnostic pre-final-gate row0 metric only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-syclgraph0-fresh-20260624T1447` | `cmqs7uyqb00lnqr01u9dtv63r` | 1 | 588 | 512 | 98.617 first / 97.956 mean | 86.262 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; direct argmax-ID unroll + q-only assistant inputs; `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `GGML_SYCL_DISABLE_GRAPH=0`; diagnostic pre-final-gate row0 metric only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-deferh-pmin014-fresh-20260624T1735` | `cmqsd2jpn00pwqr017fq21akz` | 1 | 588 | 512 | 101.428 first / 100.769 mean | 88.374 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; verifier row-argmax IDs + deferred target `h_nextn` + `MTP_P_MIN=0.14`; superseded by safer verifier row-argmax result; diagnostic pre-final-gate row0 metric only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-fresh-20260624T1830` | `cmqsf630x00r1qr01d1usfo2d` | 1 | 588 | 512 | 101.482 first / 101.249 mean | 88.582 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; stricter verifier row-argmax shape guard + deferred target `h_nextn` + `MTP_P_MIN=0.14`; superseded by immediate-command-list result; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-immediatecl1-fresh-20260624T1932` | `cmqshlz8j00s0qr01f7lr24oh` | 1 | 588 | 512 | 101.602 first / 100.835 mean | 88.508 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; safer verifier row-argmax + deferred target `h_nextn` + `MTP_P_MIN=0.14` plus `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`; superseded by selected-softmax/weighted-sum result; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-selectedsoftmax-weightedsum-pmin0136-fresh-20260625T0315` | `cmqsylo2l011nqr011yydjvne` | 1 | 588 | 512 | 103.299 first / 102.193 mean | 89.849 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; selected-softmax + weighted-sum MoE source guards, safer verifier row-argmax, deferred target `h_nextn`, `MTP_P_MIN=0.136`, and `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`; superseded by route-cache micro-record; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-rmsreuse-ub768-nmin3-pmin010-fresh-20260627T070421` | `cmqw1tgzx0366qr01g4lkv7f1` | 1 | 588 | 512 | 104.309 first / 103.934 mean | 90.851 | 1536 repeats / 6144 canary rows passed; Q8 target/verifier with Q4_0 MTP draft only; same route-cache/fused-output/fused-selected-softmax recipe with `UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10` on GPU0 plus `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`; superseded within the diagnostic/pre-final-gate lane by later Q8 MoE-ID reorder rows; all benchmark rows `cached_tokens=0` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-nmin3-pmin010-fresh-20260627T035307` | `cmqvv3kop0309qr013ekr8apu` | 1 | 588 | 512 | 104.226 first / 104.174 mean | 90.741 | 1536 repeats / 6144 canary rows passed; Q8 target/verifier with Q4_0 MTP draft only; same route-cache/fused-output/fused-selected-softmax recipe with `UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10` on GPU0; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; support mean also improves over the previous `104.071` record, but this remains a small variance-class row, not material progress toward `>150` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-fresh-20260627T002926` | `cmqvmjvzx02qvqr01qh9jikow` | 1 | 588 | 512 | 104.071 first / 103.589 mean | 90.487 | 1536 repeats / 6144 canary rows passed; Q8 target/verifier with Q4_0 MTP draft only; same route-cache/fused-output/fused-selected-softmax recipe with `UBATCH_SIZE=768` on GPU3; superseded by `cmqvv3kop0309qr013ekr8apu`; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; support mean is lower than prior record, so this was a row0 variance-class micro-record over `103.983`, not material progress toward `>150` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-repeat-fresh-20260626T230510` | `cmqvjupek02pgqr01d46algvg` | 1 | 588 | 512 | 103.983 first / 104.096 mean | 90.479 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; exact same route-cache/fused-output recipe as prior row, repeated on GPU0; superseded by the `104.226` `UBATCH_SIZE=768`, `n_min=3`, `p_min=0.10` micro-record; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; variance-class micro-record over `103.954` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-fresh-20260626T222525` | `cmqviful602p0qr01vp27jw5i` | 1 | 588 | 512 | 103.954 first / 104.135 mean | 90.686 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; route-cache recipe plus `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` and `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`; superseded same-stack diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; small validated micro-record over `103.515` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-ctx8192-gpu2-pmin0136-fresh-20260626T191746` | `cmqvbq8tf02m1qr010dom0vu1` | 1 | 588 | 512 | 103.515 first / 103.193 mean | 90.220 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; same route-cache recipe, validated after a four-GPU CTX screen on GPU2/ctx8192; superseded by fused-output-argmax/fused-selected-softmax record; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; small validated micro-record over `103.301` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626T184617` | `cmqvalync02lhqr01h76rnti3` | 1 | 588 | 512 | 103.301 first / 103.063 mean | 89.977 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; same selected-softmax + weighted-sum recipe plus default-off `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`; superseded by GPU2/ctx8192 route-cache validation; diagnostic pre-final-gate row0 metric only, all benchmark rows `cached_tokens=0`; micro-record only (`+0.001884 tok/s`) |

## Warmed/History Artifacts, Not Headline Records

These four rows were submitted before the fresh/warmed policy was clarified.
They are valid Q8 verification of a repeated continuation, but not valid
realistic cold-suite speed claims because the draftless n-gram source had already
seen the benchmark output. Local queue artifacts were corrected on 2026-06-26
so top-level `tokSOut` records the cold row0 rate and warmed means live under
diagnostic `engineFlags`.

| Label | LocalMaxxing ID | GPUs | Input | Output | row0 fresh tok/s | warmed tok/s | Validation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-24-48-64-filledlong512-20260623T1745` | `cmqqxbkzx01cxqo01j8p97627` | 1 | 588 | 512 | 41.138 | 245.980 | 384/384 chat canary; warmed/history artifact, retraction-needed |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-20-32-64-filledlong512-20260623T1750` | `cmqqxjnif01d0qo01ix4oeixo` | 1 | 588 | 512 | 41.097 | 255.041 | 384/384 chat canary; warmed/history artifact, retraction-needed |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-20-32-64-filledlong512-20260623T1815` | `cmqqxx7bp01dbqo012d2qiiw6` | 1 | 588 | 512 | 41.364 | 280.040 | 384/384 chat canary; warmed/history artifact, retraction-needed |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-20-32-64-filledlong512-20260623T1855` | `cmqqyby6801dvqo01as3wenz2` | 1 | 588 | 512 | 41.308 | 280.642 | 384/384 chat canary; warmed/history artifact, retraction-needed |

Required packet: see
[`results/gemma4-26b-a4b-q8-b70/localmaxxing-and-targets.md`](gemma4-26b-a4b-q8-b70/localmaxxing-and-targets.md).

Submit artifacts:

- queue: `data/localmaxxing-gemma4-26b-a4b-q8-b70-syclopt0-faoff-20260623.queue.json`
- rejected first attempt: `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-syclopt0-faoff-20260623.submit.log`
- approved retry: `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-syclopt0-faoff-20260623.submit2.log`
- second approved update:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-syclopt0-faoff-parallel1-cache0-20260623.submit.log`
- sustained-decode queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-long512-20260623.queue.json`
- sustained-decode approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-long512-20260623.submit.log`
- draft-MTP short-prompt approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-repeat-long512-20260623.submit.log`
- draft-MTP filled-long approved responses:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-psplit020-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n4-aot-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n4-aot-psplit020-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n6-aot-nmin2-pmin015-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin015-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fasttopk10-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fasttopk10-cpucleanup-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623.submit.log`
- Q8-target/Q4_0-draft historical pre-final-gate approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624.submit.log`
- historical Q8-target/Q4_0-draft pre-final-gate approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-syclgraph0-fresh-20260624.submit.log`
- historical row-argmax/defer-h Q8-target/Q4_0-draft pre-final-gate approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-deferh-pmin014-fresh-20260624.submit.log`
- historical selected-softmax/weighted-sum Q8-target/Q4_0-draft pre-final-gate
  approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-selectedsoftmax-weightedsum-pmin0136-fresh-20260625.submit.log`
- historical route-cache + fused assistant output argmax + fused selected-softmax
  weights + RMS reuse + `UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`
  Q8-target/Q4_0-draft pre-final-gate approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-rmsreuse-ub768-nmin3-pmin010-fresh-20260627.submit.log`
- prior route-cache + fused assistant output argmax + fused selected-softmax
  weights + `UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`
  Q8-target/Q4_0-draft pre-final-gate approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-nmin3-pmin010-fresh-20260627.submit.log`
- prior route-cache + fused assistant output argmax + fused selected-softmax
  weights Q8-target/Q4_0-draft pre-final-gate approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-fresh-20260626.submit.log`
- draftless ngram-mod filled-long approved responses:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-24-48-64-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-ctx4096ub512-filledlong512-20260623.submit2.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-poll100-filledlong512-20260623.submit.log`
- draftless ngram-mod filtered no-op submit artifact:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-ctx4096ub512-filledlong512-20260623.submit.log`
  (empty because the first command filtered on a non-matching label)

Correction on 2026-06-23: the four draftless ngram-mod submissions above are
not valid fresh-response headline throughput because the speedup depends on
repeated-output continuation history. They remain useful warmed/history
artifacts, but should be retracted from any public headline leaderboard view.
Their first synthetic measured rows were only about `41 tok/s` after TTFT:
`41.138` (`cmqqxbkzx01cxqo01j8p97627`), `41.097`
(`cmqqxjnif01d0qo01ix4oeixo`), `41.364`
(`cmqqxx7bp01dbqo012d2qiiw6`), and `41.308`
(`cmqqyby6801dvqo01as3wenz2`). Do not average warmed repeated rows into a
fresh-response claim.
API deletion was attempted for all four IDs and returned 404 because
LocalMaxxing currently exposes only `GET/POST /api/benchmarks` and
`POST /api/benchmarks/dry-run`; see
`data/localmaxxing-responses/gemma4-ngram-history-accelerated-delete-attempts-20260623.json`
and the OpenAPI method snapshot at
`data/localmaxxing-responses/localmaxxing-openapi-benchmark-methods-20260623.json`.

The first attempt failed only because the payload used `backend="SYCL/Level Zero"`.
The accepted payload uses LocalMaxxing's enum `backend="xpu"` and stores
`SYCL/Level Zero` as `engineFlags.backendDetail`.

Date: 2026-06-23

Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`, Quark W8A8 INT8,
vLLM/XPU on Intel Arc Pro B70.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `qwen36-35b-quark-int8-b70-tp4-strict-deep-gate-20260615a13deep2` | `cmqq4mw4c00yfqo01gb2ucgxj` | 4 | 512 | 512 | 93.551 | 178.773 |
| `qwen36-35b-quark-int8-b70-tp2-safe-smoke-20260615tp2safe1` | `cmqq4mwgm00yiqo0133bj962q` | 2 | 512 | 512 | 85.869 | 162.283 |

Note: the TP4 submission is the current strict-valid deep gate: JSON `128/128`,
color `256/256`, and quality suite pass. The TP2 submission is the best safer
reference smoke with JSON `16/16` and color `16/16`; quality suite was skipped,
so it is labeled as a TP2 reference rather than a stronger deep-gate result.
Payload queue and response log:
`data/localmaxxing-qwen36-35b-quark-int8-b70-valid-2x4x-20260623.queue.json`
and
`data/localmaxxing-responses/qwen36-35b-quark-int8-b70-valid-2x4x-20260623.submit.log`.

Date: 2026-05-15

Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`, AutoRound W4A16 safetensors,
vLLM/XPU TP4.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `vllm-minimax-m27-clean-weight-piecewise-aot-p512-n1536` | `cmp6a5c1o00mpo3011hg8ncyp` | 4 | 512 | 1536 | 65.752 | 87.670 |

Note: repaired piecewise/AOT compiled path with the default-off MiniMax Q/K
RMSNorm clean-weight guard enabled. Three p512/n1536 repeats were `64.622`,
`66.659`, and `65.976` output tok/s. Raw-prompt quality canaries at 64 and
256 generated tokens both passed with `0` NUL tokens, `0` non-space control
chars, and nontrivial token diversity. This supersedes the earlier quality-
corrected `~61` tok/s TP4 baseline, but the older `~73` tok/s AOT diagnostic
remains invalid because it failed the raw corruption gate.

Date: 2026-05-09

Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`, AutoRound W4A16 safetensors, vLLM/XPU TP4.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `vllm-minimax-m27-autoround-u4-decode-p512-n128` | `cmoxptkfd00hsml01hf2ajhhp` | 4 | 512 | 128 | 29.748 | 148.742 |
| `vllm-minimax-m27-autoround-u4-decode-p512-n256` | `cmoxq7cww00i8ml019ihbeqc9` | 4 | 512 | 256 | 33.034 | 99.101 |
| `vllm-minimax-m27-autoround-u4-fp32-route-p512-n256` | `cmoy8hs3n002smk01ksgcpavr` | 4 | 512 | 256 | 34.158 | 102.474 |
| `vllm-minimax-m27-autoround-u4-pp2tp2-negative-p512-n256` | `cmoy9exmf003lmk01d3it9cz2` | 4 | 512 | 256 | 17.550 | 52.651 |
| `vllm-minimax-m27-autoround-u4-default-ipc-p512-n256` | `cmoy9qat60040mk01l5y8n3al` | 4 | 512 | 256 | 34.578 | 103.734 |
| `vllm-minimax-m27-autoround-u4-default-ipc-p512-n512` | `cmoyagit0004dmk014gk25e2k` | 4 | 512 | 512 | 37.136 | 74.272 |
| `vllm-minimax-m27-autoround-xpu-graph-fixedkv-p512-n256` | `cmoyfl7cm0057mk01suxo0glp` | 4 | 512 | 256 | 32.723 | 98.169 |

Note: unsigned llm-scaler u4 decode-only MoE path, no speculative decode, no expert dropping, no sampling changes, and no power-limit changes. The XPU graph fixed-KV result is a negative/diagnostic run: PIECEWISE graph capture succeeded with local vLLM patches, but it was slower than the non-graph default-IPC path.

Date: 2026-05-03

Model: `Lorbus/Qwen3.6-27B-int4-AutoRound`

All submitted results returned `APPROVED`.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `vllm-int4-single-b70-mtp-500-256` | `cmoq41b9d001alg043wsnthz2` | 1 | 500 | 256 | 45.2 | 133.44 |
| `vllm-int4-single-b70-mtp-500-512` | `cmoq47sll0005l104v3i0f9l3` | 1 | 500 | 512 | 41.3 | 81.60 |
| `vllm-int4-tp2-b70-nonmtp-500-256` | `cmoq4e9dw0002js04ledqyycn` | 2 | 500 | 256 | 49.1 | 144.88 |
| `vllm-int4-tp2-b70-nonmtp-500-512` | `cmoq4krfb000cl40456wobg7e` | 2 | 500 | 512 | 48.3 | 95.56 |
| `vllm-int4-single-b70-nonmtp-500-256` | `cmoq4r8rc0001l804tocgibus` | 1 | 500 | 256 | 31.8 | 93.80 |
| `vllm-int4-tp2-b70-mtp-500-256` | `cmoq4xppt0003ky04xidngli9` | 2 | 500 | 256 | 35.6 | 105.03 |
