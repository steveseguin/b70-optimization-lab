# MiniMax M2.7: U4 WS Up Signed-Branch Template Candidate

Date: 2026-05-21

## Candidate

Source-level llm-scaler candidate in:

`/mnt/fast-ai/src/llm-scaler-promoted-rebuild-20260520T120230Z/vllm/custom-esimd-kernels-vllm/csrc/moe_batch/moe_int4.sycl`

The MiniMax W4A16 WS up kernel was changed from a runtime `signed_compact`
branch to a compile-time specialization:

- generic signed path remains available for S4 kernels
- MiniMax U4 path dispatches to `SIGNED_COMPACT=false`
- hot decode math remains equivalent: U4 nibbles are mapped with `value - 8`

This was intended to remove a branch from the dominant `moe ws up routed
cutlass int4` kernel identified by eager MoE tracing.

## Build Notes

The first rebuild used `/opt/intel/oneapi/setvars.sh --force`, which selected
oneAPI 2026.0 and produced an import-time segfault. This matches earlier
compiler-compatibility findings.

The safe rebuild path was:

```bash
SRC=/mnt/fast-ai/src/llm-scaler-promoted-rebuild-20260520T120230Z/vllm/custom-esimd-kernels-vllm \
OUTDIR=/home/steve/bench-results/minimax-m2.7-post-repro-optimization \
MAX_JOBS=2 \
/home/steve/llm-optimizations-publish/scripts/build-llm-scaler-moe-int4-xpu.sh
```

Build log:

`/home/steve/bench-results/minimax-m2.7-post-repro-optimization/build-moe-int4-u4-oneapi2025-20260521T175842Z.log`

Import smoke passed from the isolated Python path.

## Quality Gate

Strict quality gate passed before benchmarking:

- raw145 n64 exact token hash matched:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash matched:
  `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite matched:
  `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat r8 matched:
  `261779104d5abf1642713bfc560ca8d2d6c0f16edbcc929c8b0819b5a760dd7c`

Summary:

`/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-moe-u4-up-signed-template-strict-tp4-ctx2048-mbt512-bs256-20260521T180057Z-summary.json`

## Benchmark

Prompt/output: p512/n1536, TP4, 4x B70, strict-quality-gated run.

Output tok/s:

- 90.498154
- 90.591831

Mean output tok/s: 90.544993

Total tok/s:

- 120.664206
- 120.789108

Mean total tok/s: 120.726657

## Decision

Rejected for promotion. Quality was preserved, but speed did not beat the
accepted quality-clean warm result of 93.443623 output tok/s.

No LocalMaxxing submission was made because this is not a new best result and
does not add a distinct public leaderboard configuration beyond the existing
strict-quality promoted runs.

## Lesson

The runtime signed/unsigned branch in the WS up kernel is unlikely to be a large
remaining bottleneck. The compiler may already be handling it well, or the extra
template instantiations/code layout offset any branch removal.

Next higher-value work should focus on either:

- graph-safe kernel timing for MiniMax top-k and non-llm-scaler kernels
- lower-level collective/allreduce replacement instead of more Python/env shape
  toggles
- MiniMax MTP/speculative decode implementation only if target verification can
  remain exact-token clean
