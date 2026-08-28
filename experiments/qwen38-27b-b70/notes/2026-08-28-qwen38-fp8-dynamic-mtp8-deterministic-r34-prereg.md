# Preregistration: Qwen3.8 FP8 deterministic dynamic-MTP8 R34

## Question

Does composing the qualified deterministic MTP1 target/runtime fixes with the
existing active-width dynamic-MTP mechanism, then extending the exact packed
Gemma RMSNorm replay to the nine-row MTP8 verifier pack, make dynamic MTP8 both
faster than qualified static MTP1 and exact against the qualified MTP0 target?

## Frozen treatment

- Model: official Qwen3.8-27B FP8 revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`.
- Runtime image:
  `neural-download/vllm-openai-xpu:qwen38-fp8-dynamic-deterministic-mtp8-r34`,
  immutable local ID
  `sha256:49780a358477b2a49fd25a5f9c317a443e86554680dabed23c789494c1e19e00`.
- Qualified base: deterministic MTP1 r31 image ID
  `sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b`.
- Dynamic components: active-width GDN extension and active-lookahead Mamba
  allocation from image ID
  `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`.
- New bounded RMS patch:
  `vllm-qwen38-xpu-gemma-rmsnorm-mtp1-mtp8-serial-exact-r34-20260828.patch`,
  SHA-256 `98c26561926abfcfa7b057eb83cda3c2774dff908c3641f09586f748c7dbff44`.
- Operator preflight: 100 trials at `[9,5120]` FP16, covering plain,
  fused-add, and returned residual tensors; zero mismatches and zero maximum
  absolute difference against the one-row native operator.
- TP2, official FP8 plus lab W8A16, FP16/auto KV, XPU Graph off, compiled
  target/draft, `TORCHINDUCTOR_DETERMINISTIC=1`, one active slot, 1,024-token
  service capacity, prompt cache off.
- Dynamic schedule: MTP8 for one active request and MTP1 for 2-128. Only the
  singleton branch is measured here; this experiment grants no aggregate
  authority.

## Frozen performance and quality contract

Run two independent fresh servers, each with a new empty compile cache. On
each server:

1. execute the complete fixed 12-prompt/six-class realistic suite once;
2. use the natural 512-token cap and require every row to cover the first-100
   token timing window;
3. require `cached_tokens=0` for every request and retain complete token IDs;
4. compute the primary rate as the median of the six prompt-class medians over
   the 99 intervals between generated-token events 1 and 100;
5. run the independent 8x repeat, arithmetic, exact-copy, and JSON-schema
   canaries;
6. compare all 12 complete token arrays across the two R34 attempts and
   against both qualified compiled MTP0 r15 target attempts.

The profile qualifies only if both workload and canary batteries pass and all
four complete-array comparisons are 12/12 exact. One passing server is not
sufficient. No selected prompt, short response cap, cache reuse, warmed
repeated fixture, semantic-only substitution, or output-changing margin is
allowed.

## Decision rule

- If the full exactness contract passes, report the median of the two
  class-balanced attempt medians and its exact improvement over qualified
  static MTP1 (`51.9187565 tok/s`).
- If any complete array differs, retain all speed observations as diagnostics
  and keep dynamic MTP withheld.
- Do not publish a 32K, multi-user, LocalMaxxing, or package-headline value
  from this short-context singleton experiment.
