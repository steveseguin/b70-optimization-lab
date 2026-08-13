# DFlash TP backend greedy sampling: retained win

Date: 2026-08-13

## Decision

Retain the default-off DFlash TP backend-greedy path.  It moves the 15 DFlash
row argmax operations from full-vocabulary host sampling to the existing SYCL
four-rank maxloc collective and improves the fixed BF16 TP4 suite from a pooled
`68.198 tok/s` to `71.859 tok/s` (**+5.368%**).  All three 256-token output
hashes are canonical.  No drafter training was performed.

This is a real inference-path win, but it does not meet the `>100 tok/s` goal.
The implementation currently requires `p_min=0`, because the greedy maxloc
path materializes the selected token but not its probability.  The previously
promoted `67.881 tok/s` champion used `p_min=0.15`, so this result is a new
fastest exact measured stack rather than a directly additive A/B against that
older configuration.

## Final C/A/C result

All arms used the same BF16 Muse target, BF16 DFlash, `n_max=15`, `p_min=0`,
TP4 tensor split, parallel submit, greedy decoding, cache off, one request at a
time, and 256 generated tokens for each fixed prompt.

| arm | prose | code | JSON | mean |
| --- | ---: | ---: | ---: | ---: |
| CPU control before | `48.613` | `70.352` | `85.737` | `68.234` |
| device greedy | **`50.869`** | **`74.874`** | **`89.834`** | **`71.859`** |
| CPU control after | `48.820` | `70.220` | `85.446` | `68.162` |

The candidate therefore beats the pooled controls by `5.368%`.  Candidate
hashes were prose `914f754747d0edaa`, code `cf2b2c4fd9e36fe5`, and JSON
`4f813a9706abc163`.  Acceptance remained effectively stable: prose `172`, code
`198`, JSON `207` accepted draft tokens versus `172/197/207` in each control.
The code arm's one-token difference did not change target output.

The candidate log proves the intended fast path was reached:

```text
[comm-dbg] argmax fast path: n_backends=4 n_rows=1 shard_widths=50512,50512,50512,50512
```

## Integration bug found and fixed

The first full attempt was target-exact but accepted no draft tokens and ran at
roughly `10 tok/s`.  Backend greedy correctly produced a sampled token, but it
also retained the full logits tensor as a sampler output.  The common sampler
then interpreted logits without a matching candidate-ID tensor and generated
bogus contiguous vocabulary IDs.  The terminal greedy sampler now clears the
logits output, and the common sampler has a singleton sampled-token fast path.
A short three-class smoke then matched the CPU row-control hashes with 100%
acceptance before the final C/A/C was admitted.

## Source and gates

Source commit: `/home/steve/src/llama.cpp-muse-100` commit `35e462c5a`
(`speculative: add DFlash TP greedy experiment`).  The path is default-off and
requires all of:

```text
LLAMA_DFLASH_TP_GREEDY=1
LLAMA_TP_BACKEND_SAMPLING=1
GGML_SYCL_COMM_ARGMAX=1
```

It deliberately falls back to CPU sampling when `p_min > 0`.  The production
TP2 fleet was not changed.

## Evidence

- final result:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-tp-greedy-final-ab-20260813.jsonl`,
  SHA256 `a18beb44ea39c4bf178370f59b3341634b46386afc50d929d5b15792530296a7`;
- fixed short smoke:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-tp-greedy-fix-smoke-20260813.jsonl`,
  SHA256 `bbbf77e348605818dbe472ce758bd049a55768acda962fca51e406e730385a33`;
- diagnostic row trace:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-tp-greedy-row-debug-20260813.jsonl`,
  SHA256 `3aa26a6d6d9675accabbc694cef44b4d2dc2cb714d07cfa21944f67510f7777c`;
- final run identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-tp-greedy-final-ab.json`;
- restored production health:
  `data/muse-health-20260813-dflash-tp-greedy-final-restore.json`.

The source rebuilt through `llama-server` with oneAPI 2026, `git diff --check`
passed before commit, and production was restored without reboot.  Both
services are active and the full model/cache-zero code/vision health gate
passes.
