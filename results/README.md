# Results Index

This folder is the promoted and closed-out result ledger for the lab. It is not
limited to the currently active model. Use it for model-specific outcome
packets, record summaries, validity gates, reproduction commands, and links to
evidence.

Keep active experiments in `../experiments/`, chronological investigation notes
in `../notes/`, patch snapshots in `../patches/`, compact run evidence in
`../data/`, and copy-ready recipes in `../repro/`.

For a compact, manually maintained view of expected performance across model
and hardware identities, see the [performance index](scoreboard.md).

Historical first-100-token rows from the shared realistic-suite helper used a
100-event numerator over a 99-interval span. They remain preserved as published
evidence; use the scoreboard accounting note and model-specific corrections
before comparing their absolute values with conventionally counted rates.

## Model Packets

| Model / Lane | Folder | Status | Best Valid Result |
| --- | --- | --- | --- |
| **Poolside Laguna S 2.1 INT4 on 4x B70** | [qualified packet](laguna-s-2.1-int4-b70/README.md); [120.807/119.599 experiment packet](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-30-segmented-dflash-attention-subgraphs-preregistration.md); [older sealed repro](../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md) | **Approved exact current record; standalone promotion in progress** | Four-B70 TP4+EP4, BF16 KV, one active generation, width-12 exact target verification and DFlash depth 11 with segmented draft compute plus six graph-safe draft-attention subgraphs: **`119.598567 tok/s`** under current-policy conventional 99-interval accounting and **`120.806633 tok/s`** under the historical compatibility formula. One cold 13-prompt score, 13/13 token-and-text exact, all `cached_tokens=0`, target 146/145 and draft 20/19 on every rank, no warmup/retry, clean teardown; LocalMaxxing `cms8e85mr00fmpf013wvkqc0s`. |
| DeepSeek V4 Flash uniform-K160 on B70 | [result packet](deepseek-v4-flash-k160-b70/README.md); [standalone repro](../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md); [closeout](../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md) | Paused/closed frontier | Four-B70 TP4+EP, one active generation, unchanged K160 target with target-verified DSpark7: `80.820052 tok/s` strict high and `78.287226 tok/s` three-suite median-of-medians; 36/36 cache-zero realistic rows, 24/24 exact canaries; LocalMaxxing `cmrquta9905w3lg013m5vxoqx`. No later verified endpoint exceeded it. |
| Qwen3.6 27B INT4 AutoRound on B70 | [handoff](qwen36-27b-autoround-int4-b70/HANDOFF.md); [packet](qwen36-27b-autoround-int4-b70/README.md); [TP2 record](qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json); [repro](../repro/qwen36-27b-autoround-int4-b70/README.md) | Closed reference lane | Two-B70 TP2 vLLM/XPU strict result: `95.384868 tok/s` median for generated tokens 1-100 after TTFT on the fixed realistic cold suite, target-verified MTP3, `cached_tokens=0`, with complete exact/repeat128/baseline/needle quality evidence; LocalMaxxing `cmrh35ct50092mj01h7jgydqj`. |
| Qwen3.6 27B GGUF Q8_0 target-only on ASRock B70 | [current result](qwen36-27b-q8-tp2-asrock-b70/README.md); [repro](../repro/qwen36-27b-q8-tp2-asrock-b70/README.md); [source patch](../patches/qwen36-27b-q8-tp2-asrock-b70/README.md); [mndodd contributor baseline](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md) | Active bounded service; `B70-verified` target-only TP2 record | Two-ASRock-B70 TP2, graph off, no speculation: **`35.699225 tok/s` conventional** / `36.059823` historical fixed-suite median, full-512 after-TTFT `35.715918`; `+15.065%` over the matched mndodd fork baseline, all cache counts zero, 12/12 complete 512-token hashes identical, poison red-controls passed. One-card contributor result remains `17.955800` historical / `17.776242` conventional. |
| Qwen3.6 27B GGUF Q4_0 native DFlash/SYCL on B70 | [closure](../notes/2026-07-13-qwen27-dflash-sycl-closure.md); [experiment packet](../experiments/qwen27-dflash-sycl-b70/README.md) | Closed intensive research lane; objectives missed | One-B70 llama.cpp/SYCL, unchanged Q4_0 target with target-verified native DFlash5 and fused Xe2 verifier/draft-head stack: `47.818818 tok/s` median for generated tokens 1-100 after TTFT on 12 unique cold prompts, `cached_tokens=0`; LocalMaxxing `cmrjbx8bc02g8mj01yzz2v701`. The requested 100 tok/s TP1 and 200 tok/s multi-B70 single-session objectives were not reached. |
| Qwen3.6 27B MTP GGUF Q4 on B70 | [packet](qwen36-27b-mtp-gguf-q4-b70/README.md) | Valid reference, not competitive | One-B70 llama.cpp/SYCL, `unsloth/Qwen3.6-27B-MTP-GGUF`, `Qwen3.6-27B-UD-Q4_K_XL.gguf`, draft-MTP3, fixed realistic cold suite, `cached_tokens=0`: `30.678766952807752` median tok/s for generated tokens 1-100 after TTFT; LocalMaxxing `cmr6mn5ct0076mn01on3dnpyn`. Useful as a model/runtime variation reference; the AutoRound vLLM lane is the faster Qwen27 INT4/Q4 headline. |
| Gemma 4 26B A4B Q8 / INT8 on B70 | [handoff](gemma4-26b-a4b-q8-b70/HANDOFF.md); [production service](gemma4-26b-a4b-q8-b70/production-service.md); [packet](gemma4-26b-a4b-q8-b70/README.md); strict repro: [../repro/gemma4-26b-a4b-q8-b70-125tps-20260701](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) | Production-servable frontier/reference | One-B70 llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target, fixed realistic cold suite, `cached_tokens=0`: strict high `124.97714084813418` median tok/s for generated tokens 1-100 after TTFT; LocalMaxxing `cmr1u77na01k2ld01kalwzs1e`. Same-family support and variance notes are in the packet; synthetic/warmed rows are diagnostic only. |
| Qwen3.6 35B A3B Quark W8A8 INT8 on B70 | [qwen36-35b-quark-int8-b70](qwen36-35b-quark-int8-b70/README.md) | Closed reference packet | 4x strict-valid `93.55 tok/s`; TP2 safe smoke `85.87 tok/s` |
| MiniMax M2.7 INT4 AutoRound on B70 | [result packet](minimax-m27-int4-autoround-b70/README.md); [deploy repro](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md); [strict repro](../repro/minimax-m27-b70-89tps-20260520/README.md) | Deployable baseline plus historical strict and constrained-task lanes | Deployable 32K endpoint: `83.172` output tok/s on the comparable p512/n1536 gate. Historical strict 2K lane: `89.314195` output tok/s. Constrained structured-output results are labeled separately in the packet. |
| Gemma 4 12B IT INT4 AutoRound | [../experiments/gemma4-12b-int4-autoround-vllm](../experiments/gemma4-12b-int4-autoround-vllm/README.md) | Production slot plus research profiles | c8 32K image+text endpoint; c10/c12/c16/c64 documented separately |

Every row above was measured in the reference B70 lab. Contributed results that
have not been reproduced here are listed separately below and are not part of
this ledger.

## Community-Reported

Outside contributions that have **not** been reproduced in the reference lab.
These are not lab results and are not comparable to the table above: the
numbers are as reported by their contributor, on their hardware, under their
methodology. Entries live in [`../community/`](../community/README.md) and each
one carries a `STATUS.md` recording exactly what was and was not checked here.

A row graduates out of this table into the ledger above only after it reaches
`B70-tested` or better, per
[`../docs/contribution-verification.md`](../docs/contribution-verification.md).

| Model / Lane | Entry | Evidence level | Contributor-reported claim |
| --- | --- | --- | --- |
| Qwen3.6 27B FP8 native TP2 Docker on 2x B70 | [community entry](../community/dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md); [PR #9](https://github.com/steveseguin/b70-optimization-lab/pull/9) | `B70-tested`; recipe executed here 2026-07-25 | Recipe confirmed working in the reference lab: TP2 serves `Qwen/Qwen3.6-27B` @ `6a9e13bd6` at native FP8 under `intel/llm-scaler-vllm:0.21.0-b1`, 14.13 GiB/card, KV cache 888,488 tokens, healthy ~110 s after start. Measured **30.171 tok/s median decode** (range 29.564-30.528, stdev 0.302, 15 rows over 3 passes, one active generation, 256-token outputs), which falls inside the contributor's reported 28.3-34.7 range; cite this figure rather than their top-of-range "34". Card pairing across PCIe root complexes made no measurable difference (30.482 median). Sampling enabled per the contributed config, so no exactness gate; `cached_tokens` not reported by this build, prefix caching disabled and prompts unique. The multi-GPU Level Zero failure reported by a second contributor does **not** reproduce here. |

## Promotion Rules

Promote a result into this folder only when:

- the model, quantization, GPU count, prompt/output shape, and runtime identity
  are explicit;
- throughput is labeled as output-token throughput, total-token throughput, or
  another named metric;
- correctness and quality gates are recorded;
- raw JSON/log evidence is linked from `../data/` or an external path is
  recorded;
- negative or invalid fast lanes are labeled as such rather than hidden.

If a model lane is paused or closed, keep the packet. Paused packets are how
future work avoids rediscovering the same dead ends when we switch back to a
model after learning something from another lane.

For LocalMaxxing submissions, see [../docs/localmaxxing.md](../docs/localmaxxing.md).
