# MiniMax M2.7 RowParallel o_proj In-Place Allreduce Negative

Date: 2026-05-20 UTC

## Summary

Tested `VLLM_XPU_ROWPARALLEL_OPROJ_INPLACE_ALLREDUCE=1` with
`VLLM_XPU_ROWPARALLEL_OPROJ_INPLACE_ALLREDUCE_MAX_NUMEL=6144` on top of the
current promoted 4x B70 MiniMax M2.7 AutoRound stack.

The candidate preserved output quality across the full strict gate, including
the exact `raw145-n256` canary and extended sixpack suite, but throughput was
below the promoted baseline. It should not be promoted or submitted to
LocalMaxxing.

## Result

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Engine: `vLLM 0.20.1-local`, XPU, TP4
- Hardware: 4x Intel Arc Pro B70 32GB
- Shape: p512/n1536, ctx2048, batch 1, MBT512, block256
- Candidate mean output: `88.85241478409328` tok/s
- Candidate mean total: `118.46988637879103` tok/s
- Promoted baseline output: `89.31419538094708` tok/s
- Delta: `-0.46178059685380` output tok/s, about `-0.517%`

Per-repeat output tok/s:

- `88.6925108280999`
- `89.68137564710311`
- `88.22656167466515`
- `88.80921098650497`

Per-repeat total tok/s:

- `118.25668110413321`
- `119.5751675294708`
- `117.63541556622019`
- `118.41228131533995`

## Quality Gate

Passed:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

Hashes matched the promoted references:

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

## Candidate

The patch narrowly changed `RowParallelLinear.forward()` for attention
`o_proj` layers. When the output was XPU FP16/BF16 and the tensor was small
enough, it called `torch.ops.vllm.all_reduce_inplace()` directly and reused the
same tensor instead of the normal `tensor_model_parallel_all_reduce()` path.

The intent was to remove an allocation/copy boundary on the attention
hidden-state allreduce while keeping arithmetic and operation ordering intact.
The full quality pass confirms the hook was math-safe for this strict shape,
but the throughput loss suggests the Python-level conditional/custom-op path
adds more overhead than it removes.

## Reliability Notes

The exact and semantic gates showed intermittent shutdown noise:

- `Bad address (src/pipe.cpp:367)` appeared after raw145 n256 and semantic-suite
  shutdown.

The commands completed and quality hashes were valid, but the extra teardown
noise is another reason not to promote the candidate.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-rowparallel-oproj-inplace-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T001136Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-rowparallel-oproj-inplace-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T001136Z-quality`
- Benchmark JSONs:
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260520T002709Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260520T003004Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260520T003252Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260520T003545Z.json`

## Decision

Rejected. Runtime source and venv changes were reverted. The strict harness
keeps the environment capture fields for this variable so future replay can
describe the candidate cleanly.
