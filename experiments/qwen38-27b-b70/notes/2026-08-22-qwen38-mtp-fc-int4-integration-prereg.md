# Qwen3.8 mtp.fc INT4 integration preregistration (BLOCKED pending build + authorization)

Date: 2026-08-22

Status: **preregistered, launch-BLOCKED.** The operator screen passed
(`qualified-only-for-default-off-integration-design`,
[result](2026-08-22-qwen38-mtp-fc-int4-operator-result.md): ~58-60
us/call saved per shard), and the
[integration design draft](2026-08-22-qwen38-mtp-fc-int4-integration-design-draft.md)
is source-grounded. This note freezes the integration campaign's gates.
It authorizes no GPU2 run: integration is a new experiment that runs only
after (a) the default-off patch is written and reviewed, (b) a fresh
sealed compile-cache is built and its manifest frozen, and (c) explicit
user authorization for the GPU2 campaign - the same per-launch interlock
the operator screen used.

## Bounded claim under test

Does replacing the live FP16 `mtp.fc` matmul (qwen3_next_mtp.py:67, inside
the compiled eagle_head graph) with the qualified eager W4A16 operator,
default-off and bound to that one layer, improve end-to-end MTP5 decode
tok/s without regressing MTP acceptance or the quality battery. The
operator arithmetic caps the direct contribution at ~85 us/target-step
(5 MTP calls), i.e. low single-digit percent at ~40 ms/step - a
contributor toward 105, not the whole move. It is only worth integrating
if it stacks cleanly with the (separately blocked) Q64xK32 lever.

## Fixed design (owned)

- Door `VLLM_XPU_MTP_FC_INT4` (default 0), registered in `envs.py` and
  `envs.compile_factors()` so the cache key forks. Off == today's binary.
- On: at `mtp.fc` weight load only, load the FROZEN qualified packed
  buffers (per-rank backing/qweight/scales, shas in the operator prereg),
  verify shas, and fail startup on mismatch (never silent FP16 fallback -
  that would fake engagement).
- Forward: eager `int4_gemm_w4a16(bias=None, gs=128, g_idx=None,
  input_dependency=True)` with the completion barrier, preserving
  publication before the TP2 gather_output all-gather consumes the shard.
- Fresh persistent compile-cache identity (new namespace); the sealed
  b991/f358 artifacts are NOT reused. Marginfree anchor re-established on
  the new cache before any A-B.

## Gate ladder (each a preregistered arm; stop on first failure)

1. eager parity: the operator screen's CPU oracle, in-process, on the
   loaded layer - byte-consistent with the qualified packing.
2. compile+graph clean boot: both per-rank engagement markers present;
   sealed cache/identity green; no compile-cache writes.
3. real concurrent TP2 smoke on GPUs 2,3.
4. MTP acceptance-rate non-regression vs the incumbent on the short suite.
5. quality battery pass (the standard canaries + needle).
6. endpoint A-B-B-A vs incumbent (short suite, scratch=0 per the
   chunked-prefill finding); conventional-median win with bootstrap
   95% lower bound > 0, or report-only.

## Authorization boundary (unchanged from campaign standard)

This note does not authorize: the patch commit, the cache build, any GPU2
process, or any remote/other-host work. The GPU2 campaign requires the
written+reviewed patch, the frozen fresh-cache manifest, and an explicit
per-run go, exactly as the operator screen required. Cost estimate: one
sealed cache build + anchor arms + the six-gate ladder ~ an evening of
serialized GPU2 time.

## Dependency on the corruption finding

Integration A-B runs the short single-chunk suite, so the multi-chunk
persistent-scratch corruption (task #13) does not invalidate it. But if
the corruption fix lands first and touches the compiled graphs or GDN
splitting ops, this fresh cache must be built AFTER that fix, or rebuilt.
