# Qwen3.8 FP8 TP2 MTP1 XPU Graph R58 negative

Date: 2026-09-01

R58 tested one change to the final deterministic R50 static-MTP1 profile:
`VLLM_XPU_ENABLE_XPU_GRAPH=1` with a size-one PIECEWISE capture. The strict
12-prompt/six-class natural-512 suite remained quality-clean and every complete
candidate array matched the matched-image R54A MTP0 oracle. The candidate is
still rejected because it missed its preregistered performance floor.

| Gate | Result |
| --- | --- |
| Class-balanced decode | `51.229844 tok/s` |
| Qualified graph-off incumbent | `51.808087 tok/s` |
| Candidate delta | `-1.116%` |
| 99% non-inferiority floor | `51.290006 tok/s` — **fail by 0.060162** |
| Complete arrays vs R54A MTP0 | `12/12` exact |
| Cache / workload / canaries | pass |
| New GPU faults or resets | zero |

The server accepted 2,899 of 3,626 draft tokens (`79.950%`). vLLM also warned
that XPU Graph is experimental and officially supports only single-GPU
execution. Stage 2—the 18-case 2K-32K matrix—was therefore not authorized.
Graph-off remains the robust default; no public speed or curve changes.

The first real request still JIT-compiled
`eagle_prepare_next_token_padded_kernel` and
`eagle_prepare_inputs_padded_kernel`. That is a separate cold-request latency
issue and does not rescue the rejected graph treatment.

Raw receipts are retained outside Git under
`qwen38-fp8-context-optimization-20260901/mtp1-xpugraph-r58`; their hashes are
bound in the structured result.
