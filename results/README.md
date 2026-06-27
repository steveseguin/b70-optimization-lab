# Results Index

This folder is the promoted result ledger. Use it for model-specific outcome
packets, record summaries, and links to reproducible evidence. Keep active
experiments in `../experiments/`, chronological investigation notes in
`../notes/`, and reusable reproduction recipes in `../repro/`.

## Current Model Packets

| Model / Lane | Folder | Status | Best Valid Result |
| --- | --- | --- | --- |
| Gemma 4 26B A4B Q8 / INT8 on B70 | [gemma4-26b-a4b-q8-b70](gemma4-26b-a4b-q8-b70/README.md); prior repro: [../repro/gemma4-26b-a4b-q8-b70-95tps-20260624](../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md) | Active optimization | Fresh-response one-B70 Q8-target record: llama.cpp draft-MTP `n=7`, Q8 target with Q4_0 MTP draft only, fast argmax + direct argmax-ID unroll + q-only assistant inputs + safer verifier row-argmax IDs + deferred target `h_nextn` + selected-softmax/weighted-sum MoE source guards + CPU cleanup + VMM/ubatch/thread tuning + `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, plus default-off one-shot `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, Gemma4 assistant fused output argmax, and fused selected-softmax weights; `104.071 tok/s` first no-cache request after TTFT, `103.589 tok/s` supporting repeated-request mean, 1536 repeats / 6144 canary rows, LocalMaxxing `cmqvmjvzx02qvqr01qh9jikow`. This is a `UBATCH_SIZE=768` row0 variance-class micro-record over the previous `103.983 tok/s` row; the prior row had a higher support mean, so this is not a material breakthrough toward `>150`. Draftless `ngram-mod` reached `245-280 tok/s` only as warmed/history acceleration on repeated filled-long outputs; row-0 fresh was about `41 tok/s`, so it is not a valid fresh-response headline claim. Submitted ngram IDs are marked retraction-needed. |
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
