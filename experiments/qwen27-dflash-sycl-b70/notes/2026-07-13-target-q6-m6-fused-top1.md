# Target Q6_K M=6 fused top-1

Date: 2026-07-13

The existing native-DFlash Q6_K fused output-head kernel was generalized from
five draft rows to six target rows and matched against the raw target
`output.weight -> argmax[6]` graph. Production activation is separately gated
by `GGML_SYCL_XE2_Q6_TARGET_M6_TOP1`; compare and forced-read-failure modes keep
the full head/logits path. An unexpected compact-read failure in fused mode
fails closed instead of copying stale, unmaterialized logits.

Correctness passed the same-decode shadow: 41 M=6 cycles / 246 target IDs had
zero fused-versus-production argmax mismatches, while the independent host
compact/full-logit oracle also had zero mismatches. The apparent ID difference
against an earlier run was confirmed to be production cross-run numerical
variation; fused and ordinary agreed within each exact decode.

The short same-GPU crossover was a valid but insufficient win:

- ordinary: median 47.0339, p10 38.7938, mean 44.6189 tok/s;
- fused: median 47.7862, p10 39.7890, mean 45.2859 tok/s;
- deltas: +1.60% median, +2.57% p10, +1.49% mean;
- width-six target-decode median: 50.920 -> 50.374 ms, only -0.546 ms;
- fused target cycles: 179, fallbacks: 0.

This fails the >=3% gate, so no full 12-prompt suite or LocalMax submission is
justified. The exact-five-EOG mode remains a separately keyed, correct generic
masked-argmax fallback: its graph is split at the sparse SET_ROWS boundary and
does not falsely activate the raw fused matcher.

The result says the vocabulary head was not the missing large bucket. Further
polish on this dp4a reduction cannot close the 100 tok/s gap; the next verifier
attempt must materially accelerate the head (for example a real Xe2/XMX path)
or move to a larger fused decoder boundary.

Evidence:

- shadow: `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/targetm6-q6shadow-jit-gpu0-20260713`;
- control: `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/targetm6-q6crossover-A-control-jit-gpu0-20260713.json`;
- fused: `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/targetm6-q6crossover-B-fused-jit-gpu0-20260713.json`;
- masked fallback: `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/targetm6-q6shadow-mask-jit-gpu0-20260713`.
