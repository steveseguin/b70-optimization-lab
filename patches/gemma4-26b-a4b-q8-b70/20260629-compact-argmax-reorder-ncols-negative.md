# 2026-06-29 Compact Verifier Argmax Reorder-Ncols Negative

## Intent

Try to make the Gemma 4 verifier fused-output-argmax path competitive with the
current regular verifier path by sharing Q8 output-weight loads across the
small verifier row group (`nvec=2..8`). The code adds a default-off SYCL route
behind:

```bash
LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1
LLAMA_SYCL_MUL_MAT_ARGMAX_REORDER_NCOLS=1
```

The source snapshot is:

- `patches/gemma4-26b-a4b-q8-b70/20260629-compact-argmax-reorder-ncols-experiment.patch`
- SHA256: `98a8f6b6edc861302eea229532551a628773426896f51cac86644e96805f04a8`

## Strict128 A/B

Both lanes used the fixed realistic cold-response suite, each prompt once,
`cached_tokens=0`, `MAX_TOKENS=128`, `CANARY_REPEATS=128`, UD-Q8_K_XL target,
Q4_0 MTP draft, and the current VDR2 selected-down record stack.

| lane | env delta | validity | median tok/s 1-100 | p10 | mean | median full after TTFT | wall full |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `gemma4-q8-gpu0-compactargmax-control-strict128-20260629T135022Z` | none | canary 512/512, fresh gate pass | `110.18642209569018` | `107.7418192276554` | `113.48803941258602` | `110.8510213436314` | `93.98315639882682` |
| `gemma4-q8-gpu1-compactargmax-ncols-strict128-20260629T135022Z` | fused verifier argmax + reorder-ncols | canary 512/512, fresh gate pass | `109.94207305976514` | `98.97389525819446` | `112.39365878410307` | `113.97438195415582` | `96.5334638878719` |

Result artifacts:

- `data/gemma4-q8-gpu0-compactargmax-control-strict128-20260629T135022Z/`
- `data/gemma4-q8-gpu1-compactargmax-ncols-strict128-20260629T135022Z/`

## Decision

Negative for promotion. The new route is valid, but it does not beat the
regular verifier path on the strict128 screen and remains below the promoted
full512 record (`115.8466634928202 tok/s`). Do not run a full512 confirmation
unless a later patch materially changes the fused verifier economics.

Keep the patch as a durable experiment artifact. If revisiting fused verifier
argmax, first prove the graph actually avoids enough LM-head or scratch/reduce
work with node timing; the current reordered-ncols load sharing is not enough.
