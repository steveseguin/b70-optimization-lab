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

Last manual review: **2026-07-11**.

## Read This Before Comparing Rows

- Compare results only when model revision, quantization and quality class,
  hardware/count, engine/runtime, benchmark suite and shape, cache policy,
  concurrency, and metric definition match. A larger tok/s number in a
  different row is not automatically a faster implementation.
- Most current and rapid-snapshot rows report the median generated-token rate
  for tokens 1-100 after TTFT across 12 unique cold prompts. The MiniMax rows
  instead report mean output and total throughput for a p512/n1536 benchmark.
  They must not be numerically ranked against the cold-prompt rows.
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
| `webhie/Qwen3.6-27B-int4-AutoRound`<br>`f5750c90b3776db658594df5fe8051098226dd8e` | AutoRound INT4 W4A16 target; FP16 target compute; runtime INT8 target LM-head with BF16 scales; runtime INT4 group-128 draft LM-head with BF16 scales | 2x Arc Pro B70 32 GB, TP2, concurrency 1 | vLLM/XPU `0.20.2rc1.dev13` local stack; pinned public oneCCL parent `b52f40c` / libccl `4ceafd1`; captured draft and graph-safe FlashAttention full target graph | Qwen fixed realistic suite; 12 unique cold prompts, output 512; median tokens 1-100 after TTFT; ctx 2048; target-verified MTP3 | **93.036242 tok/s** median; p10 `82.845516`; mean `92.773145`; full after-TTFT `91.219731` | **B70-verified**; strict fresh gate and full quality pass, all cached tokens zero, exact cases + repeat128 + baseline parity + 1K needle pass; crossover gains `3.42%` and `2.45%`; short-context-only forced chunk-decode route | [packet](qwen36-27b-autoround-int4-b70/tp2-fp16-graphsafe-flash-fullgraph-20260711.json); [strict JSON](../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-fp16-graphsafe-fa-full-solo-confirm-realistic128-chat-tokenids-qwensuite-20260711T204201Z.json); [quality JSON](../data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-fp16-graphsafe-fa-full-quality128-repeat128-ctx1024-20260711T203355Z.json); [patch](../experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `unsloth/gemma-4-26B-A4B-it-GGUF`<br>HF revision not recorded in packet; exact byte-verified GGUF is identified there | UD-Q8_K_XL target/verifier; Q4_0 MTP draft; f16 KV | 1x Arc Pro B70 32 GB, one full replica, concurrency 1 | llama.cpp/SYCL `c926ad098` plus the preserved local Gemma record stack | `gemma4-26b-a4b-q8-b70-realistic-v1`; 12 unique cold prompts, output 512; median tokens 1-100 after TTFT; ctx 32768; target-verified MTP3 | **124.97714084813418 tok/s** median; p10 `103.836100`; full-output after-TTFT median `114.871070` | **B70-verified**; realistic final gate and fresh-response validity pass, all cached tokens zero, `512/512` canary rows | [packet](gemma4-26b-a4b-q8-b70/README.md); [standalone repro](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md); [summary JSON](../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json); [patch snapshot](../patches/gemma4-26b-a4b-q8-b70/20260629-current-llamacpp-gemma-record-worktree.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `Lasimeri/MiniMax-M2.7-int4-AutoRound`<br>model revision not recorded in packet | AutoRound INT4 W4A16, FP16 activations / FP16-family KV; no speculation | 4x Arc Pro B70 32 GB, TP4, batch 1 | vLLM/XPU `0.20.1-local`; base vLLM `c51df430`; llm-scaler `4bfc007`; XPU graph / Level Zero | Strict speed lane: p512/n1536, ctx 2048, max batched tokens 512; mean of four clean long repeats | **89.314195 output tok/s**; `119.085594` total tok/s | **B70-verified, historical strict-speed reference**; exact n64/n256 hashes, semantic suite, arithmetic repeat, and extended sixpack passed | [repro](../repro/minimax-m27-b70-89tps-20260520/README.md); [result JSON](../repro/minimax-m27-b70-89tps-20260520/results/promoted-result-20260519.json); [patch snapshots](../repro/minimax-m27-b70-89tps-20260520/patches/README.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `Lasimeri/MiniMax-M2.7-int4-AutoRound`<br>model revision not recorded in packet | AutoRound INT4 W4A16, FP16 activations / FP16-family KV; no speculation | 4x Arc Pro B70 32 GB, TP4, one active generation | vLLM/XPU based on `c51df430`; llm-scaler `4bfc007`; XPU kernels `28e1f5e`; OpenAI-compatible endpoint | Deployable 32K endpoint; comparable strict gate p512/n1536 at ctx 2048; mean of four repeats | **83.172184 output tok/s**; `110.896246` total tok/s; warm endpoint about `83.8` output tok/s | **B70-verified, deployable reference**; strict gate passed; serves ctx 32768. Kept separate from the faster 2K strict lane | [fresh-install repro](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md); [summary JSON](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/results/summary-20260523.json); [applied patch snapshots](../repro/minimax-m27-b70-89tps-20260520/patches/README.md); contributor: [Steve Seguin](https://github.com/steveseguin) |
| `Qwen3.6-35B-A3B` | Quark W8A8 INT8 | 4x Arc Pro B70 32 GB, TP4 | vLLM/XPU PIECEWISE forced-comm graph | strict deep gate, p512/n512 | **93.550542 output tok/s** | **B70-verified closed reference**; strict quality gate passed; LocalMaxxing `cmqq4mw4c00yfqo01gb2ucgxj` | [packet](qwen36-35b-quark-int8-b70/README.md); [evidence](../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json) |
| `unsloth/Qwen3.6-27B-MTP-GGUF` | GGUF UD-Q4_K_XL target, MTP3 draft | 1x Arc Pro B70 32 GB | llama.cpp/SYCL `fdb1db877` | fixed 12-prompt cold realistic gate, output 128 | **30.678767 tok/s** median 1-100 after TTFT | **B70-verified model/runtime reference**; cached tokens zero; LocalMaxxing `cmr6mn5ct0076mn01on3dnpyn` | [packet](qwen36-27b-mtp-gguf-q4-b70/README.md) |
| `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF`<br>`eea7b2be5805a5f151f8847ede8e5f9a9284bf77` | GGUF UD-Q4_K_XL; f16 KV; no speculation | 1x Arc Pro B70 32 GB | llama.cpp/SYCL server 9763 (`dec5ca557`); runner recorded clean source snapshot `fdb1db877` | `rapid-model-snapshots-b70-realistic-v1`; 12 unique cold prompts, output 128; median tokens 1-100 after TTFT; ctx 4096 | **107.483884 tok/s** median; p10 `106.897744`; wall full-output median `94.118294` | **B70-verified rapid snapshot**; realistic final gate passed, prompt cache disabled, all cached tokens zero; first-pass baseline | [packet](rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4/README.md); [result JSON](../data/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128-20260704T193409Z.json); no result-specific source patch; contributor: [Steve Seguin](https://github.com/steveseguin) |
| `bartowski/microsoft_Phi-4-mini-instruct-GGUF`<br>`7ff82c2aaa4dde30121698a973765f39be5288c0` | GGUF Q4_K_M; f16 KV; no speculation | 1x Arc Pro B70 32 GB | llama.cpp/SYCL; runner recorded clean source snapshot `fdb1db877` | `rapid-model-snapshots-b70-realistic-v1`; 12 unique cold prompts, output 128; median tokens 1-100 after TTFT; ctx 4096 | **96.548341 tok/s** median; p10 `96.350769`; wall full-output median `91.749702` | **B70-verified rapid snapshot**; prompt caches disabled, all cached tokens zero; standalone confirmation, first-pass baseline | [packet](rapid-model-snapshots-b70/phi4-mini-instruct-gguf/README.md); [result JSON](../data/rapid-model-snapshots-b70/phi4-mini-instruct-q4km-llamacpp-faon-cacheoff-confirm-ctx4096-realistic128-20260704T224303Z.json); no result-specific source patch; contributor: [Steve Seguin](https://github.com/steveseguin) |

## Community-Reported Intel Arc Results

No rows have been added yet. Results from other Intel Arc configurations are
welcome when they include the exact hardware, OS, model revision,
quantization, runtime identity, command, benchmark shape, quality gate, and
JSON/log evidence. A community-reported row remains distinct from a
B70-verified B70 row unless it is independently reproduced on matching
hardware.

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
