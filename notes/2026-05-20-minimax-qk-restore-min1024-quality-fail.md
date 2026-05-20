# MiniMax M2.7 Q/K Clean-Weight Guard min_tokens=1024 Quality Fail

Date: 2026-05-20

## Candidate

Current promoted MiniMax M2.7 4x B70 TP4 strict stack plus:

```bash
export VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1
export VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS=1024
```

The goal was to reduce CPU callbacks in the Q/K RMS clean-weight guard for the p512/n1536 benchmark shape. With the current promoted `min_tokens=2`, prefill-sized Q/K norm calls can run the CPU sanity path. Raising the threshold to `1024` bypasses that path for the strict 145-token canary prompts and the 512-token benchmark prompt.

## Quality Outcome

Rejected before benchmarking.

- raw145 n64 exact token hash: passed
  - hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash: failed
  - expected: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
  - observed: `ff27d99c39789c365fcb83d140aad8d168bf0735846015e231ad95bcc5f1ab43`

The n256 output was deterministic and non-degenerate, but it shifted into a repeated Greek-token continuation rather than matching the promoted exact-token trace. This is a quality/reproducibility failure, not a performance result.

## Conclusion

Do not raise `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS` above the promoted value of `2` for the current strict stack. The clean-weight guard is still protecting a real longer-output failure mode; the n64 canary alone is insufficient here.

No throughput benchmark and no LocalMaxxing submission were made.

Raw summary:

`/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-restore-min1024-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T014458Z-summary.json`
