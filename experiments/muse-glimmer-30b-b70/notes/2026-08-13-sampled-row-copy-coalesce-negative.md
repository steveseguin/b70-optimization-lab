# Coalesced backend-sampled row copy: noise-sized negative

Date: 2026-08-13

## Decision

Do not promote `LLAMA_BACKEND_SAMPLING_COALESCE_ROWS=1`.  Coalescing the 16
adjacent four-byte sampled-token reads into one 64-byte asynchronous read is
byte-exact, but measured only `73.144 tok/s` versus pooled controls at
`73.081 tok/s` (**+0.087%**).  This is below the retention threshold and well
inside run noise.  No drafter training was performed.

The three class rates were candidate `52.186/75.371/91.875`; controls were
`51.990/75.548/91.598` and `52.069/75.454/91.826`.  Output hashes were canonical
and acceptance was `172/197/207` in the candidate and first control (the final
control drafted one fewer unused prose token).

Source commit `5775f7507` preserves the default-off implementation.  Evidence:

- identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-sampled-copy-coalesce-ab.json`;
- result:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-sampled-copy-coalesce-ab-20260813.jsonl`,
  SHA256 `f88fed16df7307d47f62b35ef23be3c3224c028b148b1b4120204e272a152fb4`;
- restored production health:
  `data/muse-health-20260813-dflash-sampled-copy-coalesce-restore.json`.

Production was restored without reboot and passed the full model/cache-zero
code/vision gate.  The production TP2 fleet was not changed.
