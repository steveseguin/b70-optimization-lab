# 2026-07-02 Conditional-Bonus Verifier Argmax

## Goal

Reduce Gemma 4 26B A4B Q8 MTP verifier LM-head cost without changing target
model, quantization, prompt suite, or acceptance semantics. The attempted idea
was to compute verifier draft rows in parallel, but compute the bonus row only
when every draft row matched the shifted draft tokens.

This was intended to help the fresh-response short-context decode lane. It was
not intended to claim warmed, repeated-prompt, n-gram, prefix-cache, or response
reuse speedups.

## Patch Artifacts

- Pre-edit source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-conditional-bonus-preedit-source.patch`
- Tested source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-conditional-bonus-source.patch`
- Tested source diffstat:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-conditional-bonus-source.diffstat`

The implementation added a default-off flag:

```bash
LLAMA_SPEC_VERIFY_CONDITIONAL_BONUS_ARGMAX=1
```

The first smoke failed because the new `GGML_OP_MUL_MAT_ARGMAX` mode was not
accepted by the SYCL backend support check. The final tested patch includes the
support-op fix.

## Validation

All throughput below uses the fixed realistic cold-response suite, one request
per prompt, `cached_tokens=0` for every row, no prompt/KV/cache reuse, no
history acceleration, and MTP verified by the Q8 target model.

### Smoke

`data/gemma4-q8-gpu0-condbonus-smoke2-20260702T001/summary.json`

- canary: 8 repeats x 4 cases, 32/32 pass
- realistic gate: pass, `cached_tokens_all_zero=true`
- median tok/s 1-100 after TTFT: `109.0647620975752` at `MAX_TOKENS=64`

This was only a functionality smoke, not a record candidate.

### Same-Window A/B Screen

All four runs used `MAX_TOKENS=128`, `REALISTIC_METRIC_TOKENS=100`,
`CANARY_REPEATS=128`, `CTX_SIZE=32768`, Flash Attention on, VMM on, and the
same UD-Q8_K_XL target model.

| label | GPU | conditional bonus | canary | fresh-valid | median tok/s | p10 tok/s | mean tok/s |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| `gemma4-q8-gpu0-control-condbonus-ab-20260702T0040Z` | 0 | 0 | 512/512 | yes | 115.635 | 106.056 | 115.647 |
| `gemma4-q8-gpu1-condbonus-ab-20260702T0040Z` | 1 | 1 | 512/512 | yes | 101.953 | 92.791 | 101.728 |
| `gemma4-q8-gpu2-control-condbonus-ab-20260702T0040Z` | 2 | 0 | 512/512 | yes | 112.705 | 105.176 | 114.152 |
| `gemma4-q8-gpu3-condbonus-ab-20260702T0040Z` | 3 | 1 | 512/512 | yes | 101.619 | 97.335 | 103.293 |

## Outcome

Rejected. Correctness passed, but the candidate was roughly 10-12% slower than
same-window controls. The likely cause is that the conditional-bonus path adds
an extra custom branch/kernel shape and loses the efficient existing verifier
path benefits; skipping the bonus row does not pay for that overhead.

No LocalMaxxing submission was made. The current valid record remains
`124.97714084813418 tok/s` from
`data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.

## Follow-Up

Do not continue this lane unless the verifier is redesigned more deeply. Better
next source-level targets:

- reduce verifier target forward cost before LM head;
- improve target no-spec decode / MoE kernels that affect both spec and
  non-spec paths;
- prompt-processing and long-context lanes, while re-running the short decode
  gate afterward to prove no regression.
