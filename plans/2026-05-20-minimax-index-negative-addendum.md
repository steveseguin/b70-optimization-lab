# MiniMax Index Custom-Op Addendum

Date: 2026-05-20 UTC

## Result Added To Plan

The current-high MiniMax MoE full-forward index-custom-op candidate was tested
and rejected:

- Candidate: current promoted stack plus `VLLM_MINIMAX_MOE_FULL_FORWARD_INDEX_CUSTOM_OP=1`
- Quality: raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack all passed
- Throughput: `88.648258` output tok/s / `118.197678` total tok/s across four p512/n1536 repeats
- Baseline: promoted `89.314195` output tok/s / `119.085594` total tok/s
- Decision: do not promote, do not submit to LocalMaxxing, leave the index env flag unset

## Planning Impact

This prunes the last easy Python lookup cleanup inside the already-promoted MoE
full-forward custom-op path. The wrapper name lookup is not the limiting
boundary. The next useful source candidates should target real tensor,
collective, or backend scheduling boundaries:

1. A narrow Q/K variance plus apply boundary that keeps the promoted FP32
   allreduce ordering intact.
2. A lower-level attention `o_proj` reduce/fusion path, not another Python
   wrapper around `RowParallelLinear`.
3. A true MoE-output epilogue/allreduce fusion path below the Python wrapper
   layer.

Keep the promotion rule unchanged: exact quality first, four-repeat throughput
second, LocalMaxxing only for repeatable wins or broadly useful promoted
capacity results.
