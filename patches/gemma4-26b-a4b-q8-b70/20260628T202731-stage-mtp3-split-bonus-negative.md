# 2026-06-28T202731 - Stage MTP3 Split-Bonus Negative

## Intent

Reduce verifier work for Gemma 4 26B A4B Q8 draft-MTP without changing the
target/verifier model, quantization, or validation policy.

Current speculative verifier row contract for `n_max=3`:

- row 0 verifies draft token 0;
- row 1 verifies draft token 1;
- row 2 verifies draft token 2;
- row 3 produces the bonus token, used only when all three draft tokens match.

The existing staged verifier path (`LLAMA_SPEC_VERIFY_STAGE_MTP3=1`) decodes
rows `0..1`, then rows `2..3` if the first two rows match. This patch added a
second default-off gate, `LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS=1`, to decode
rows as `2 + 1 + 1`: row 2 is decoded first, and row 3 (bonus) is decoded only
if row 2 also matches.

## Source Patch

Repository:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`

Touched file:
`tools/server/server-context.cpp`

Summary:

- add static flag `server_env_enabled("LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS")`
  inside `try_decode_staged_mtp3()`;
- when enabled, Stage B uses `batch.get_view(2, 1)` instead of `batch.get_view(2, 2)`;
- if row 2 matches draft token 2, run Stage C with `batch.get_view(3, 1)`,
  set `common_speculative_set_verify_h_base(..., 3)`, then sample row 0 as the
  bonus.

Harness plumbing:

- `scripts/run-gemma4-26b-first-baseline.sh` now forwards
  `LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh` logs the flag;
- the summary parser now includes
  `launcher_identity.llama_spec_verify_stage_mtp3_split_bonus` for future runs.

## Result

Run:
`data/gemma4-q8-gpu1-stage-mtp3-splitbonus-strict128-20260628T202731Z/summary.json`

Identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one B70, GPU1;
- strict realistic suite, each prompt once;
- `cached_tokens=0` for every request;
- `MAX_TOKENS=128`;
- `n_max=3`, `n_min=2`, `p_min=0.0475`;
- current record stack plus `LLAMA_SPEC_VERIFY_STAGE_MTP3=1` and
  `LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS=1`.

Metrics:

- canary: pass;
- realistic final gate: pass, cached0;
- median tokens 1-100 after TTFT: `73.698 tok/s`;
- p10: `71.838 tok/s`;
- mean: `74.247 tok/s`;
- full128 after TTFT: `74.884 tok/s`;
- wall full128: `67.511 tok/s`;
- median TTFT: `178.951 ms`.

## Decision

Negative. Do not promote and do not run full512.

The split-bonus schedule is semantically correct, but it is far below the
standing strict full512 record (`98.340 tok/s`) and below the earlier unprofiled
staged-MTP3 strict128 control (`78.100 tok/s`). The extra decode call and loss of
the normal verifier batch shape cost more than the skipped bonus row saves.

Keep the patch default-off as a research artifact. If this idea is revisited,
the likely useful version is not another `2 + 1 + 1` decode schedule. It would
need a true head-only late bonus over `t_h_nextn` or graph-level row-adaptive
verifier support.
