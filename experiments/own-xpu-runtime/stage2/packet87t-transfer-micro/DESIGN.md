# Packet87t — implementation design gate



Transport-priced prediction clears +0.5%. This is a design, not a sealed engine or a measured model gain.



- target: rank1 rows [0,202240); rank0 suffix 46080 rows; modeled +1.0685%. Expanded suffix storage: 155,750,400 bytes, before logits/staging/scratch.

- draft: rank1 rows [0,46336); rank0 suffix 45056 rows; modeled +0.7749%. Expanded suffix storage: 152,289,280 bytes, before logits/staging/scratch.



Export the existing normalized BF16 final.mix bytes only after its final event. Rank0 keeps its speculative state and private auxiliary scratch; its suffix head waits for its target half to finish. Use the measured pinned-host staging and release/acquire sequence ownership. No peer DMA or new queue is assumed.

Preserve every row’s operands, quantization expansion, reduction order and BF16 logit rounding. Reduce each partition; return a 16-byte value/global-index/finite-status payload. Merge rounded logits, use the lowest global index on ties including signed zero, and OR sticky errors. No nonfinite winner may emit.

Target: both hit and miss paths use the verified current target final.mix, never the speculative hidden state. Draft: dispatch suffix work only after the prior verifier established a hit; keep the complete draft prefix resident on rank1 for unchanged misses. Never move the draft trunk or reuse a guessed result.

Bound each payload to one sequence and position; prohibit reuse until destination completion. Cancellation, EOS, nonfinite status, worker exit and stale sequence abort publication, then drain both owners. A pending head cannot mutate KV, rollback images or the draft state.

Before sealing an engine: admit full real-shape memory under unchanged budgets; check partition offsets and all logits/ties/finite flags against the unchanged oracle, consecutive tokens, repeats and a fresh process. Then use matched fresh-server brackets. The microbenchmark does not satisfy those gates.

Idle DMA prices are the model decision input: existing compute is already in A/B/D. Busy totals expose queue contention and form a pessimistic sensitivity only. Revisit the design if native contention or row bandwidth invalidates those assumptions.



Evidence: [RESULT.json](RESULT.json), [DECISION.md](DECISION.md).
