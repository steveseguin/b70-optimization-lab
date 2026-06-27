# Results Index

This folder is the promoted result ledger. Use it for model-specific outcome
packets, record summaries, and links to reproducible evidence. Keep active
experiments in `../experiments/`, chronological investigation notes in
`../notes/`, and reusable reproduction recipes in `../repro/`.

## Current Model Packets

| Model / Lane | Folder | Status | Best Valid Result |
| --- | --- | --- | --- |
| Gemma 4 26B A4B Q8 / INT8 on B70 | [gemma4-26b-a4b-q8-b70](gemma4-26b-a4b-q8-b70/README.md); prior repro: [../repro/gemma4-26b-a4b-q8-b70-95tps-20260624](../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md) | Active optimization | Current policy-compliant one-B70 result: llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by the target, fixed realistic cold prompt suite, `cached_tokens=0` every request, no cache/history reuse. Current submitted strict high is reordered-Q8 VDR2, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`: `90.32179401019857` median tok/s for generated tokens 1-100 after TTFT, p10 `86.02930423477346`, mean `92.1804554185734`, full512 after-TTFT `86.21689344139463`; LocalMaxxing `cmqwt1zk803ozqr01hctqss2z`. Supporting VDR2 strict rows measured `89.45543282863798`, `89.43737321875525`, `88.06323469748838`, and `85.90621112154868`; the prior VDR2 `89.45543282863798` and VDR4 `87.61145306230438` submissions are superseded. Synthetic 170+ and warmed n-gram 245-280 tok/s rows are diagnostic only, not real-world headline throughput. |
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
