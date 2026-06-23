# Results Index

This folder is the promoted result ledger. Use it for model-specific outcome
packets, record summaries, and links to reproducible evidence. Keep active
experiments in `../experiments/`, chronological investigation notes in
`../notes/`, and reusable reproduction recipes in `../repro/`.

## Current Model Packets

| Model / Lane | Folder | Status | Best Valid Result |
| --- | --- | --- | --- |
| Gemma 4 26B A4B Q8 / INT8 on B70 | [gemma4-26b-a4b-q8-b70](gemma4-26b-a4b-q8-b70/README.md) | Active optimization | Best valid one-B70 Q8 draft-MTP filled-long result: `91.62 tok/s` after TTFT, 384/384 chat canary, LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`; target is four independent Q8/INT8 single-GPU replicas |
| Qwen3.6 35B A3B Quark W8A8 INT8 on B70 | [qwen36-35b-quark-int8-b70](qwen36-35b-quark-int8-b70/README.md) | Closed reference packet | 4x strict-valid `93.55 tok/s`; TP2 safe smoke `85.87 tok/s` |
| MiniMax M2.7 INT4 AutoRound on B70 | [../repro/minimax-m27-b70-110tps-ubuntu24-20260523](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md) | Deployable baseline | 32K endpoint, about `83-84 tok/s` output on current host |
| MiniMax M2.7 strict speed lane | [../repro/minimax-m27-b70-89tps-20260520](../repro/minimax-m27-b70-89tps-20260520/README.md) | Older strict-speed baseline | Historical `89+ tok/s` class strict packet |
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

For LocalMaxxing submissions, see [../docs/localmaxxing.md](../docs/localmaxxing.md).
