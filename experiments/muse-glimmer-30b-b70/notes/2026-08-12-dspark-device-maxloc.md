# DSpark device-side global argmax

Date: 2026-08-12

## Intent

Remove the host synchronization in the correctness-first TP4 DSpark global
argmax path. This is inference-path work only; no drafter training was
performed.

## Fixed identity

- verifier: Muse Glimmer 30B BF16, TP4 on devices `0,1,2,3`;
- assistant: the converted BF16 DSpark artifact documented in
  `2026-08-12-pretrained-dspark-tp4-bringup.md`, `n_max=15`, confidence `0`;
- single request, `parallel=1`, greedy, prompt cache disabled, 256 generated
  tokens for prose, code, and JSON;
- exact kernel stack: oneDNN primitive cache, memory-binding cache, and BF16
  graph conversion cache enabled; direct/oneMKL and SYCL graph experiments
  disabled;
- arithmetic mean of the three reported decode rates;
- reference hashes: prose `914f754747d0edaa`, code `cf2b2c4fd9e36fe5`,
  JSON `4f813a9706abc163`.

Source commit `0d6da754f` adds a default-off communicator path selected by
`GGML_SYCL_COMM_ARGMAX=1`. It recomputes each vocabulary shard's maximum with
an explicit device reduction, then uses recursive-doubling P2P maxloc and
mirrors the global token ID before the dependent Markov lookup. Equal values
retain the greatest global index, matching the CPU last-maximum convention.
The generic host implementation remains the fallback.

## Strict adjacent result

| Arm | Prose | Code | JSON | Mean t/s | Drafted/accepted |
|---|---:|---:|---:|---:|---|
| host maxloc control | 41.231 | 68.334 | 71.192 | 60.252 | 1236/168, 723/203, 733/204 |
| device maxloc | 42.483 | 70.547 | 73.188 | 62.073 | 1236/168, 723/203, 733/204 |

The device collective improved the arithmetic mean by `3.02%`. All three
hashes and all three drafted/accepted counts match the host control exactly.
The debug proof marker reported:

```text
[comm-dbg] argmax fast path: n_backends=4 n_rows=1 shard_widths=50512,50512,50512,50512
```

This is a verified supporting win, not a century claim. The honest best for
this exact three-class identity is now `62.073 t/s`.

## Rejected intermediate implementations

The first asynchronous version reused the pre-existing local ARGMAX output.
It preserved the final output hashes but changed proposal histories: code
became `738/202` instead of `723/203`, and repeated JSON rows became `748/203`
instead of `733/204`. Queue draining via `GGML_SYCL_COMM_ARGMAX_SYNC=1` did not
repair that mismatch, so those rows are correctness negatives despite their
apparently faster throughput.

A diagnostic sequential per-shard device scan restored exact proposal counts,
but regressed to `26.170 / 43.534 / 45.170`, mean `38.291 t/s`; reject it as a
performance negative. The final explicit local device reduction restored both
exact counts and speed.

## Durable evidence

- first unsafe A/B:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-device-maxloc-ab-20260812.jsonl`,
  SHA-256 `53426f9a57437a256a7ca649b50f0f2b7f2b2389bcdcd3775e2db4743b68eda8`;
- diagnostic and final repeats:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-device-maxloc-repeat-20260812.jsonl`,
  SHA-256 `4c9688c5576806b0b06fa11c79c0e3b549edebc3b5153f75e1975d1f32fd6ea4`;
- queue-drain negative:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-device-maxloc-sync-20260812.jsonl`,
  SHA-256 `961e29b99e9ed7f5d330885d9d6d26745387a619db4aea96cd0a0e081bd702f0`;
- final strict adjacent A/B:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-device-maxloc-final-ab-20260812.jsonl`,
  SHA-256 `96fccd6d5aa621d88beba2dc9ab2cab9a8943da08b2fd2ea0d205a4f923d27b0`;
- the four tracked sweep configurations sit beside this note under `sweeps/`;
- production was restored to its incumbent binary and passed the full
  cache-zero code and vision health gate in
  `data/muse-health-20260812-dspark-final-maxloc-restore.json`.

## Decision

Keep the device maxloc behind its default-off environment gate and include it
in combined DSpark experiments. The next target-side kernel-path test is
parallel submission of the four independent simple-backend graphs at each TP
meta boundary, with operation profiling disabled and a strict adjacent A/B.
