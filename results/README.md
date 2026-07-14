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

## Model Packets

| Model / Lane | Folder | Status | Best Valid Result |
| --- | --- | --- | --- |
| Qwen3.6 27B INT4 AutoRound on B70 | [handoff](qwen36-27b-autoround-int4-b70/HANDOFF.md); [packet](qwen36-27b-autoround-int4-b70/README.md); [TP2 record](qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json); [repro](../repro/qwen36-27b-autoround-int4-b70/README.md) | Closed reference lane | Two-B70 TP2 vLLM/XPU strict result: `95.384868 tok/s` median for generated tokens 1-100 after TTFT on the fixed realistic cold suite, target-verified MTP3, `cached_tokens=0`, with complete exact/repeat128/baseline/needle quality evidence; LocalMaxxing `cmrh35ct50092mj01h7jgydqj`. |
| Qwen3.6 27B GGUF Q4_0 native DFlash/SYCL on B70 | [closure](../notes/2026-07-13-qwen27-dflash-sycl-closure.md); [experiment packet](../experiments/qwen27-dflash-sycl-b70/README.md) | Closed intensive research lane; objectives missed | One-B70 llama.cpp/SYCL, unchanged Q4_0 target with target-verified native DFlash5 and fused Xe2 verifier/draft-head stack: `47.818818 tok/s` median for generated tokens 1-100 after TTFT on 12 unique cold prompts, `cached_tokens=0`; LocalMaxxing `cmrjbx8bc02g8mj01yzz2v701`. The requested 100 tok/s TP1 and 200 tok/s multi-B70 single-session objectives were not reached. |
| Qwen3.6 27B MTP GGUF Q4 on B70 | [packet](qwen36-27b-mtp-gguf-q4-b70/README.md) | Valid reference, not competitive | One-B70 llama.cpp/SYCL, `unsloth/Qwen3.6-27B-MTP-GGUF`, `Qwen3.6-27B-UD-Q4_K_XL.gguf`, draft-MTP3, fixed realistic cold suite, `cached_tokens=0`: `30.678766952807752` median tok/s for generated tokens 1-100 after TTFT; LocalMaxxing `cmr6mn5ct0076mn01on3dnpyn`. Useful as a model/runtime variation reference; the AutoRound vLLM lane is the faster Qwen27 INT4/Q4 headline. |
| Gemma 4 26B A4B Q8 / INT8 on B70 | [handoff](gemma4-26b-a4b-q8-b70/HANDOFF.md); [production service](gemma4-26b-a4b-q8-b70/production-service.md); [packet](gemma4-26b-a4b-q8-b70/README.md); strict repro: [../repro/gemma4-26b-a4b-q8-b70-125tps-20260701](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) | Production-servable frontier/reference | One-B70 llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by target, fixed realistic cold suite, `cached_tokens=0`: strict high `124.97714084813418` median tok/s for generated tokens 1-100 after TTFT; LocalMaxxing `cmr1u77na01k2ld01kalwzs1e`. Same-family support and variance notes are in the packet; synthetic/warmed rows are diagnostic only. |
| Qwen3.6 35B A3B Quark W8A8 INT8 on B70 | [qwen36-35b-quark-int8-b70](qwen36-35b-quark-int8-b70/README.md) | Closed reference packet | 4x strict-valid `93.55 tok/s`; TP2 safe smoke `85.87 tok/s` |
| MiniMax M2.7 INT4 AutoRound on B70 | [result packet](minimax-m27-int4-autoround-b70/README.md); [deploy repro](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md); [strict repro](../repro/minimax-m27-b70-89tps-20260520/README.md) | Deployable baseline plus historical strict and constrained-task lanes | Deployable 32K endpoint: `83.172` output tok/s on the comparable p512/n1536 gate. Historical strict 2K lane: `89.314195` output tok/s. Constrained structured-output results are labeled separately in the packet. |
| Gemma 4 12B IT INT4 AutoRound | [../experiments/gemma4-12b-int4-autoround-vllm](../experiments/gemma4-12b-int4-autoround-vllm/README.md) | Production slot plus research profiles | c8 32K image+text endpoint; c10/c12/c16/c64 documented separately |

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
