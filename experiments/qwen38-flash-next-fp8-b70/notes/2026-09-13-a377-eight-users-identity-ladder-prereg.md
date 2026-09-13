# Preregistration: A377 - eight users on the Flash-Next MTP0 line, with the per-request identity gate

## Question

Every Flash-Next line is certified at one sequence. The front page's "Many users" cell is empty.
With the cards freed by the 5.0 GiB census placement, can the promoted MTP0 line serve up to
eight sequences with every concurrent output equal to its single-user output, and what is the
aggregate decode rate?

## Arm

A377: promoted MTP0 line (overlay `2a372e86`, served stage, W13-N64 map), placement
`data/20260913-q38-expert-host-placement-a315-census-5gib-mc8-per-rank.json`, `max_num_seqs=8`,
`max_num_batched_tokens=64` (unchanged; prefill stays chunked), KV `1412136960` bytes (120 pool
blocks; eight sequences at 4,352 tokens), decode graph capture sizes [1, 2, 4, 8],
`VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=8` and `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=8` (the row-wise
selectors that made two-row steps batch-invariant, at eight rows). Generator: the A336 diag
generator with the new `USERS:` option. Port 19990.

Driver `tools/q38-concurrency-oracle-driver.sh`: `scripts/bench-openai-concurrency-oracle.py` on
the fixed 12-prompt realistic suite, completions mode, 128 tokens with `ignore_eos`, temperature 0,
concurrency 1, 2, 4, 8, two repeats, `--require-output-identity` (each concurrent completion must
equal the sequential oracle generated on the same server; the 9B lane's ladder used the same
client and flags).

## Predictions

- Identity: the MoE tuned map keys on the row count (M), so M=2/4/8 use other tile configs than
  M=1; if those change accumulation order the ids differ and the gate fails at the first
  concurrency that differs. The row-wise selectors cover the all-reduce and the HC norm only.
  This arm measures rather than assumes.
- Throughput: single-user ~40 tok/s on this line; decode is weight-bandwidth-bound, so aggregate
  rate should grow nearly linearly to 4 users and sub-linearly at 8 (MoE activates more experts
  per step); the placement's host hits add a little per step.

## Stop rules

Server fails health (memory); the oracle reports an identity failure at some concurrency: that
concurrency and above are not lossless on this line and are recorded, the largest exact
concurrency is the candidate "Many users" cell. Either way the numbers are published with the
gate outcome stated.
