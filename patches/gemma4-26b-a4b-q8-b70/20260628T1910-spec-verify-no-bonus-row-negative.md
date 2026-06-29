# Gemma 4 26B Q8: verifier no-bonus-row negative

Date: 2026-06-28

Status: **negative / reverted**

## Idea

The current strict Gemma MTP path verifies `sampled + n_draft` target output
rows. For `n_max=3`, row 3 is the bonus token sampled after all three draft
tokens match. The target/verifier LM-head row is a visible cost in node
profiles, so the experiment tried to remove only that bonus output row:

- still decode the sampled token plus all three draft tokens;
- mark the final draft token as `output=false`;
- verify the three draft tokens exactly with target sampled IDs;
- on full accept, emit the three drafted tokens without sampling a bonus row.

This was default-off under `LLAMA_SPEC_VERIFY_NO_BONUS_ROW=1`.

## Patch Shape

Temporary source changes:

- `tools/server/server-context.cpp`: skipped the final draft index in
  `spec_i_batch` and set the final draft batch entry `output=false`.
- `common/sampling.{h,cpp}`: added a `no_bonus` overload of
  `common_sampler_sample_and_accept_n()` that verifies draft rows but does not
  sample the extra bonus row.
- `finish_speculative_accept()`: special-cased full no-bonus acceptance so
  statistics and `common_speculative_accept()` counted all three accepted draft
  tokens.
- `scripts/run-gemma4-26b-first-baseline.sh`: temporarily captured
  `LLAMA_SPEC_VERIFY_NO_BONUS_ROW` in run identity.

The patch was reverted after the screen. The just-built binary from this test
was stale after the revert and must not be reused for later headline runs
without rebuilding.

## Validation

Run:
`data/gemma4-q8-gpu1-nobonusrow-screen128-20260628T1910Z/summary.json`

Identity:

- Target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- GPU: one B70, `ONEAPI_DEVICE_SELECTOR=level_zero:1`
- `n_max=3`, `n_min=2`, `p_min=0.0475`
- `UBATCH=1024`, `ctx=8192`
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`
- `LLAMA_SPEC_VERIFY_NO_BONUS_ROW=1`
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- `--ctx-checkpoints 0`
- Fixed realistic suite, each prompt once, `cached_tokens=0`

Result:

- Canary: pass, 16 repeats / 64 rows
- Fresh-response validity: pass, all `cached_tokens=0`
- Median 1-100 after TTFT: `84.9195 tok/s`
- p10: `77.6098 tok/s`
- Mean: `83.7240 tok/s`
- Full128 after TTFT median: `83.0696 tok/s`

Standing strict record:
`98.3405 tok/s` median 1-100 after TTFT, full512 confirmation.

## Decision

Do not promote and do not retry as a runtime knob. Removing the bonus output row
passed quality, but it was much slower. The likely mechanism is that the server
loses the bonus-token pipeline: it saves one LM-head row, but the final
accepted draft token is then treated like the next sampled token and effectively
reprocessed in the following target step. That defeats the intended verifier
row saving.

This closes the simple no-bonus-row approach on the current stack. The useful
follow-up is different: keep the bonus pipeline but make the bonus sample
cheap, e.g. a head-only bonus over the existing `t_h_nextn` row or a true
row-adaptive verifier that avoids full LM-head rows while preserving exact
target verification.
