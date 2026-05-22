# MiniMax M2.7 Promoted Runtime Quality Sanity - 2026-05-21

## Purpose

After rejecting the Q/K AR+apply custom-op screen, the experimental hook was removed from both the source checkout and installed vLLM runtime. This run verifies that the restored promoted runtime still matches the quality canaries used for the public 89 tok/s setup.

## Configuration

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Runtime: vLLM XPU, TP4, llm-scaler WS INT4 path
- Promoted env: `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`
- Bench repeats: disabled (`BENCH_REPEATS=0`)
- Extended quality: enabled
- Arithmetic repeat quality: 16 runs

## Result

Status: `quality_passed`

Passed checks:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

Known hashes confirmed:

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- arithmetic repeat: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

The script printed a post-shutdown `Bad address (src/pipe.cpp:367)` and Python resource-tracker cleanup warnings after all quality checks had passed and the summary JSON had been written. No vLLM worker processes or stale `/dev/shm/psm_*` / `sem.mp-*` entries remained afterward.

## Artifacts

- Summary JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/quality-sanity-after-qk-neutral-20260521/minimax-promoted-runtime-sanity-after-qk-neutral-20260521-strict-tp4-ctx2048-mbt512-bs256-20260521T022011Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/quality-sanity-after-qk-neutral-20260521/minimax-promoted-runtime-sanity-after-qk-neutral-20260521-strict-tp4-ctx2048-mbt512-bs256-20260521T022011Z-quality`
- Structured data: `data/minimax-m27-promoted-runtime-quality-sanity-after-qk-neutral-20260521.json`
