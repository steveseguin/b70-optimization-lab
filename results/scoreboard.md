# Performance Index

This is a small, manually maintained index of useful performance expectations.
It is not the identity of the project, a universal leaderboard, or a replacement
for the linked result packets. Those packets and their JSON/log evidence are the
source of truth.

The current local verification platform is Intel Arc Pro B70. Results and
patches for other Intel Arc GPUs are welcome, but they remain clearly labeled
until matching hardware is available for independent reproduction. Testing a
contributor's patch on B70 validates the resulting B70 behavior; it does not
verify a score originally reported on different hardware.

Last manual review: **2026-08-12**.

## Read This Before Comparing Rows

- Compare results only when model revision, quantization and quality class,
  hardware/count, engine/runtime, benchmark suite and shape, cache policy,
  concurrency, and metric definition match. A larger tok/s number in a
  different row is not automatically a faster implementation.
- Most current and rapid-snapshot rows report the median generated-token rate
  for tokens 1-100 after TTFT across 12 unique cold prompts. The MiniMax rows
  instead report mean output and total throughput for a p512/n1536 benchmark.
  They must not be numerically ranked against the cold-prompt rows.
- Historical rows produced by `bench-openai-realistic-suite.py` used a
  100-event numerator over the first-to-100th timestamp span, which contains
  99 intervals. Unless a row explicitly gives both values, treat its displayed
  first-100-token score as the published legacy convention; multiply by 0.99
  for conventional interval accounting. Relative comparisons wholly within
  that historical convention are unchanged. Laguna is the first row audited
  and displayed both ways.
- A target-verified lower-precision draft does not change the declared target
  quantization, but unverified shortcuts or a lower-precision target require a
  separate row and quality label.
- Rapid snapshots are first-pass expected-performance references, not evidence
  that a model has received the same optimization depth as a dedicated lane.
- Natural run-to-run and device-to-device variance can be several percent.
  Small claims need same-window controls, repeats, or crossover evidence.
- `B70-verified` means the row was produced and quality-gated on the
  local B70 system. It does not imply upstream support, portability, warranty,
  or identical results on another host.

## B70-Verified Results

| Model / revision | Quantization | Hardware / layout | Engine / runtime | Suite / benchmark shape | Result | Quality / status | Patch, evidence, contributor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `poolside/Laguna-S-2.1-INT4`<br>`4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb` | compressed-tensors INT4 group-32 W4A16 target; matched INT4 DFlash draft with 31 runtime E4M3FN W8A16 projections per rank; BF16 KV; target-verified speculation | 4x Arc Pro B70 32 GB, TP4+EP4, one active generation | vLLM/XPU `e596ef154`; XPU kernels `6f9dd3c3a`; exact width-12 stack, persistent exact-attention metadata, validated 146/145-segment Breakable PIECEWISE graph | Laguna fixed realistic suite; 13 unique cold prompts, output up to 512; first-to-100th token timestamps; greedy canonical-q1 exactness; DFlash depth 11 | **102.971436 tok/s** submitted legacy 100-event/99-interval median; **101.941721 tok/s** conventional interval median; legacy p10 `71.148884`; full wall `52.767621` | **B70-verified, sealed, metric-qualified**; first valid preregistered cold score, 13/13 token-and-text exact and cache-zero, 512-output-then-next 2/2, rollover 1/1, no warmup generation or retry, clean 73-second pre/post idle gates; LocalMaxxing `cms2ccv2d00lps201rej94pjy` | [qualified packet](laguna-s-2.1-int4-b70/README.md); [repro](../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md); [correction](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `0xSero/DeepSeek-V4-Flash-180B`<br>`7c360e1cd4a5168099dbc54d16d929bf6df04990`, experimental uniform-K160 artifact | FP8 block-scaled dense weights; FP4 experts; FP8 KV; unchanged K160 target with target-verified DSpark7 | 4x Arc Pro B70 32 GB, TP4+EP, one active generation | vLLM/XPU `264c7f2f7`; XPU kernels `313156737`; oneCCL `48fda4f0e`; target and draft PIECEWISE graphs | Fixed realistic suite; 12 unique cold prompts, output 128; median tokens 1-100 after TTFT; target verifier M=8 | **80.820052 tok/s** median high; p10 `71.669556`; three-run median `78.287226`; wall full128 `67.762818` | **B70-verified closed-lane record**; 36/36 realistic rows cache-zero, 24/24 exact canaries, unchanged target verifies accepted tokens; LocalMaxxing `cmrquta9905w3lg013m5vxoqx` | [packet](deepseek-v4-flash-k160-b70/README.md); [repro](../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md); [summary](../experiments/deepseek-v4-flash-reap-xpu-b70/data/dspark-sharded-target-argmax-record-20260718.json); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `unsloth/Qwen3.6-27B-MTP-GGUF`<br>Q4_0 file identity recorded in the linked payload | GGUF Q4_0 target; Q8 target KV; native Q4_K_M DFlash draft with F16 draft KV; target-verified speculation | 1x Arc Pro B70 32 GB, one active generation | llama.cpp/SYCL base `e3546c794` plus preserved BMG-AOT Xe2 M=6 verifier, GDN snapshot-cache, and fused Q6_K draft-head/top-1 stack | Fixed realistic suite; 12 unique cold prompts, output 128; median tokens 1-100 after TTFT; native DFlash5 | **47.818818 tok/s** median; p10 `39.869534`; mean `46.638647` | **B70-verified closed-lane record**; all cached tokens zero; unchanged target verifies accepted draft tokens; matching AOT control `44.2205 tok/s`; LocalMaxxing `cmrjbx8bc02g8mj01yzz2v701` | [closure](../notes/2026-07-13-qwen27-dflash-sycl-closure.md); [evidence](../data/qwen36-27b-mtp-gguf-q4-b70-baselines/q6top1-aot-realistic128-r2-20260713.json); [record note](../experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-q6k-m6-fused-top1-production-record.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `webhie/Qwen3.6-27B-int4-AutoRound`<br>`f5750c90b3776db658594df5fe8051098226dd8e` | AutoRound INT4 W4A16 target; FP16 target compute; runtime INT8 target LM-head with BF16 scales; runtime INT4 group-128 draft LM-head with BF16 scales | 2x Arc Pro B70 32 GB, TP2, concurrency 1 | vLLM/XPU `0.20.2rc1.dev13` local stack; pinned public oneCCL parent `b52f40c` / libccl `4ceafd1`; captured draft, graph-safe FlashAttention full target graph, ReplaySSM pending/direct-output transaction fusion | Qwen fixed realistic suite; 12 unique cold prompts, output 512; median tokens 1-100 after TTFT; ctx 2048; target-verified MTP3 | **95.384868 tok/s** median; p10 `86.975415`; mean `95.623050`; full after-TTFT `91.698097` | **B70-verified**; strict fresh gate and full quality pass, all cached tokens zero, exact cases + repeat128 + baseline parity + 1K needle pass; both swapped crossover assignments positive; short-context-only forced chunk-decode route | [packet](qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json); [strict JSON](../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-fp16-fullgraph-transaction-realistic512-20260711.json); [quality JSON](../data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-fp16-fullgraph-transaction-repeat128-ctx1024-20260711.json); [note](../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-11-fullgraph-transaction-record.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `ggml-org/Qwen3.6-27B-GGUF`<br>`8a7ee08e8b9bfb857107ecc25a5599d2f38b76f8` | GGUF Q8_0 target; F16 KV; no draft or speculation | 2x ASRock Arc Pro B70 32 GB, TP2, concurrency 1 | mndodd llama.cpp/SYCL fork `4302fb599` plus separated low-RAM/DNN-off compile compatibility and exact-F32 two-card all-reduce patch; oneAPI 2026.1 BMG-G31 AOT | Qwen fixed realistic suite; raw completions; temperature 0 / seed 42; 12 unique cold prompts, output 128; median tokens 1-100 after TTFT | **31.025377 tok/s conventional**; `31.338765` historical 100-event compatibility; p10 conventional `30.876411`; wall full-output median `29.922846`; TTFT `179.092 ms` | **B70-verified target-only**; all cached tokens zero; 12/12 complete output hashes equal the matched upstream-derived control; fresh logits gate PPL `5.635366` vs `5.635427`, same-top `100%`; fork is `+5.836%` over that control under either accounting convention | [community packet](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md); [validation](../community/mndodd-qwen36-27b-llamacpp-sycl/validation/2026-08-12-asrock-b70-validation.md); [patch](../community/mndodd-qwen36-27b-llamacpp-sycl/patches/0001-asrock-lab-lowram-dnnless-tp2.patch); source: [mndodd](https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization) |
| `unsloth/gemma-4-26B-A4B-it-GGUF`<br>HF revision not recorded in packet; exact byte-verified GGUF is identified there | UD-Q8_K_XL target/verifier; Q4_0 MTP draft; f16 KV | 1x Arc Pro B70 32 GB, one full replica, concurrency 1 | llama.cpp/SYCL `c926ad098` plus the preserved local Gemma record stack | `gemma4-26b-a4b-q8-b70-realistic-v1`; 12 unique cold prompts, output 512; median tokens 1-100 after TTFT; ctx 32768; target-verified MTP3 | **124.97714084813418 tok/s** median; p10 `103.836100`; full-output after-TTFT median `114.871070` | **B70-verified**; realistic final gate and fresh-response validity pass, all cached tokens zero, `512/512` canary rows | [packet](gemma4-26b-a4b-q8-b70/README.md); [standalone repro](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md); [summary JSON](../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json); [patch snapshot](../patches/gemma4-26b-a4b-q8-b70/20260629-current-llamacpp-gemma-record-worktree.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `Lasimeri/MiniMax-M2.7-int4-AutoRound`<br>model revision not recorded in packet | AutoRound INT4 W4A16, FP16 activations / FP16-family KV; no speculation | 4x Arc Pro B70 32 GB, TP4, batch 1 | vLLM/XPU `0.20.1-local`; base vLLM `c51df430`; llm-scaler `4bfc007`; XPU graph / Level Zero | Strict speed lane: p512/n1536, ctx 2048, max batched tokens 512; mean of four clean long repeats | **89.314195 output tok/s**; `119.085594` total tok/s | **B70-verified, historical strict-speed reference**; exact n64/n256 hashes, semantic suite, arithmetic repeat, and extended sixpack passed | [repro](../repro/minimax-m27-b70-89tps-20260520/README.md); [result JSON](../repro/minimax-m27-b70-89tps-20260520/results/promoted-result-20260519.json); [patch snapshots](../repro/minimax-m27-b70-89tps-20260520/patches/README.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `Lasimeri/MiniMax-M2.7-int4-AutoRound`<br>model revision not recorded in packet | AutoRound INT4 W4A16, FP16 activations / FP16-family KV; no speculation | 4x Arc Pro B70 32 GB, TP4, one active generation | vLLM/XPU based on `c51df430`; llm-scaler `4bfc007`; XPU kernels `28e1f5e`; OpenAI-compatible endpoint | Deployable 32K endpoint; comparable strict gate p512/n1536 at ctx 2048; mean of four repeats | **83.172184 output tok/s**; `110.896246` total tok/s; warm endpoint about `83.8` output tok/s | **B70-verified, deployable reference**; strict gate passed; serves ctx 32768. Kept separate from the faster 2K strict lane | [fresh-install repro](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md); [summary JSON](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/results/summary-20260523.json); [applied patch snapshots](../repro/minimax-m27-b70-89tps-20260520/patches/README.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `Qwen3.6-35B-A3B` | Quark W8A8 INT8 | 4x Arc Pro B70 32 GB, TP4 | vLLM/XPU PIECEWISE forced-comm graph | strict deep gate, p512/n512 | **93.550542 output tok/s** | **B70-verified closed reference**; strict quality gate passed; LocalMaxxing `cmqq4mw4c00yfqo01gb2ucgxj` | [packet](qwen36-35b-quark-int8-b70/README.md); [evidence](../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json) |
| `unsloth/Qwen3.6-27B-MTP-GGUF` | GGUF UD-Q4_K_XL target, intrinsic MTP7, `n_min=1`, `p_min=0.65` | 1x Arc Pro B70 32 GB | llama.cpp/SYCL `fdb1db877` | fixed 12-prompt cold realistic gate, output 128 | **31.480049 tok/s** published legacy median (`31.165249` conventional) | **B70-verified model/runtime support reference**; cached tokens zero; earlier MTP3 LocalMaxxing row `30.678767`, `cmr6mn5ct0076mn01on3dnpyn` | [packet and p-min evidence](qwen36-27b-mtp-gguf-q4-b70/README.md) |
| `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF`<br>`eea7b2be5805a5f151f8847ede8e5f9a9284bf77` | GGUF UD-Q4_K_XL; f16 KV; no speculation | 1x Arc Pro B70 32 GB | llama.cpp/SYCL server 9763 (`dec5ca557`); runner recorded clean source snapshot `fdb1db877` | `rapid-model-snapshots-b70-realistic-v1`; 12 unique cold prompts, output 128; median tokens 1-100 after TTFT; ctx 4096 | **107.483884 tok/s** median; p10 `106.897744`; wall full-output median `94.118294` | **B70-verified rapid snapshot**; realistic final gate passed, prompt cache disabled, all cached tokens zero; first-pass baseline | [packet](rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4/README.md); [result JSON](../data/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128-20260704T193409Z.json); no result-specific source patch; contributor: [Steve Seguin](https://github.com/steveseguin) |
| `bartowski/microsoft_Phi-4-mini-instruct-GGUF`<br>`7ff82c2aaa4dde30121698a973765f39be5288c0` | GGUF Q4_K_M; f16 KV; no speculation | 1x Arc Pro B70 32 GB | llama.cpp/SYCL; runner recorded clean source snapshot `fdb1db877` | `rapid-model-snapshots-b70-realistic-v1`; 12 unique cold prompts, output 128; median tokens 1-100 after TTFT; ctx 4096 | **96.548341 tok/s** median; p10 `96.350769`; wall full-output median `91.749702` | **B70-verified rapid snapshot**; prompt caches disabled, all cached tokens zero; standalone confirmation, first-pass baseline | [packet](rapid-model-snapshots-b70/phi4-mini-instruct-gguf/README.md); [result JSON](../data/rapid-model-snapshots-b70/phi4-mini-instruct-q4km-llamacpp-faon-cacheoff-confirm-ctx4096-realistic128-20260704T224303Z.json); no result-specific source patch; contributor: [Steve Seguin](https://github.com/steveseguin) |

## Community-Contributed Intel Arc Results

| Model / quantization | Hardware / runtime | Result | Evidence boundary |
| --- | --- | ---: | --- |
| `Qwen/Qwen3.6-27B` native FP8 Safetensors | 2x Arc Pro B70, TP2; contributor Docker/vLLM recipe reproduced locally | **30.171 tok/s** median decode across 15 rows | `B70-tested`; different prompt-length benchmark, not directly comparable to fixed-suite rows; [validation](../community/dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md) |
| `unsloth/Qwen3.6-27B-MTP-GGUF` Q4_K_M | 1x Arc Pro B70; llama.cpp/SYCL `15586e2d7`; intrinsic MTP2 | **38.112 tok/s** on one fixed greedy 128-token request; target-only control `25.307` | `B70-tested`; visible bytes matched, but token IDs were not retained, request `min_p` differed, and this is not a fixed-suite median; [validation](../community/dominick253-qwen36-27b-llamacpp-sycl/validation/2026-08-08-reference-lab-validation.md) |

Results from other Intel Arc configurations are welcome when they include the
exact hardware, OS, model revision, quantization, runtime identity, command,
benchmark shape, quality gate, and JSON/log evidence. A community-reported row
remains distinct from a B70-verified B70 row unless it is independently
reproduced on matching hardware.

## Portability And Other-Hardware Observations

No rows have been added yet. Portable patches and observations from other
hardware may be useful to Intel XPU work, but their original performance claims
will be labeled as contributor-reported. If such a patch is tested locally, its
B70 measurement belongs in a separate row with its own runtime identity and
evidence.

## Maintaining This Index

Update this page by hand only after reviewing the linked packet and evidence.
Do not replace a row merely because a single run is faster. Preserve distinct
rows when the model revision, quantization or quality class, runtime, hardware
count, benchmark shape, cache policy, or metric definition changes. Superseded
rows should remain discoverable in their model packet even when this compact
index advances to a newer representative result.
