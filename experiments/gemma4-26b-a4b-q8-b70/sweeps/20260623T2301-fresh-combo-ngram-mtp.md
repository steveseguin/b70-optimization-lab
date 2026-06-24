# 2026-06-23T2301 - Fresh first-request n-gram + MTP controls

Goal: evaluate whether `ngram-mod` can improve **fresh-response** throughput
when combined with the current Gemma 4 26B A4B Q8 draft-MTP record lane.

Important validity rule: n-gram/history speculation is only headline-valid when
it helps before the target continuation has already been generated. Repeated
prompt/output benchmark averages that become fast because prior identical
responses populated history are warmed/history-accelerated and must not be
reported as fresh-response throughput. These runs use `BENCH_REPEATS=1`, so the
benchmark row is the first measured request after canaries.

Current valid fresh-response record to beat:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z`
- canary: `384/384`
- first measured request after TTFT: `92.39728860909672 tok/s`
- repeated-request after-TTFT mean: `92.76706524545781 tok/s`
- every benchmark row reported `cached_tokens=0`

## Runs

All rows used the same filled-long prompt (`prompt_sha256`
`04f687a68d60254567d3252624e01a696b0c9843dbb02f5a789d75aada5e4da5`),
`max_tokens=512`, `CANARY_REPEATS=16` (`64/64` rows), `BENCH_REPEATS=1`,
`LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, `--spec-draft-n-max 7`,
`--spec-draft-n-min 2`, `--spec-draft-p-min 0.12`, `--ctx-checkpoints 0`,
`GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, and `cached_tokens=0`
for the measured benchmark request.

| Label suffix | Spec type / knob | Canary | First request after-TTFT tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `combo-ngram20-mtpn7-firstonly-ctx8192ub512poll100` | `ngram-mod,draft-mtp`, match/min/max `20/32/64`, ctx `8192` | 64/64 | `91.68686179917657` | `78.49763353406254` | loss vs `92.397`; do not promote |
| `combo-ngram8-mtpn7-firstonly-ctx8192ub512poll100` | `ngram-mod,draft-mtp`, match/min/max `8/8/64`, ctx `8192` | 64/64 | `46.318032492226244` | `42.684943932865025` | bad cold throughput; lower anchors hurt |
| `combo-ngram16-mtpn7-firstonly-ctx8192ub512poll100` | `ngram-mod,draft-mtp`, match/min/max `16/16/64`, ctx `8192` | 64/64 | `91.28783401823648` | `78.12007753878822` | loss vs record |
| `mtpn7-firstonly-ctx4096ub512poll100` | draft-MTP only control, ctx `4096` | 64/64 | `91.23049752308248` | `78.05013011274936` | loss vs record; ctx `4096` did not help |

## Conclusion

No combo run beat the current fresh-response MTP record. The best first request
was `91.68686179917657 tok/s`, still below `92.39728860909672 tok/s`.

The earlier `>200 tok/s` n-gram-only rows remain useful as warmed/history
artifacts, but they are not valid fresh-response headline results under the
current rule because their speed comes from prior repeated continuations.

Next work should focus on source-level MTP cost reduction or a fresh-valid
speculation source. Avoid spending more runs on n-gram averages unless the first
request after canaries is reported separately and is the promoted metric.
