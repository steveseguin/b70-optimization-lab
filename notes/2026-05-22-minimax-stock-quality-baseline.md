# MiniMax M2.7 Stock-Quality Baseline

Date: 2026-05-22

Goal: establish what the MiniMax M2.7 AutoRound INT4 model/runtime can do on a
least-risk path so we can judge whether optimized fast paths are preserving or
damaging output quality.

The promoted optimized path and patch bundles were preserved before this
baseline work:

- Safety snapshot:
  `/home/steve/optimization-safety/minimax-current-state-20260522T185722Z`
- Existing promoted repro folder:
  `/home/steve/llm-optimizations-publish/repro/minimax-m27-b70-89tps-20260520`
- Promoted compressed patch bundles still present:
  - `repro/minimax-m27-b70-89tps-20260520/patches/vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64`
  - `repro/minimax-m27-b70-89tps-20260520/patches/llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64`

## Baseline Definitions

### Attempt A: no llm-scaler MoE, eager/no graph

This is the closest local test to a default vLLM INC path:

- `VLLM_XPU_USE_LLM_SCALER_MOE=0`
- no MiniMax WS/logits/custom-op accelerators
- no XPU graph
- `enforce_eager=True`
- JSON validator only, no structured decoding

Smoke result:

- Path:
  `/home/steve/bench-results/minimax-m2.7-stock-quality-baseline/20260522T185905Z-eager-no-llmscaler-alpha-smoke/result.json`
- Task: `alpha_names`
- Pass: `1/1`
- Output throughput: `10.220 tok/s`
- Parsed JSON hash: `bf168752774e60ead346a22d057c9d57a65f8775bbd8b7b95d94c80dd2f97aff`

Broader repeat attempt:

- Path:
  `/home/steve/bench-results/minimax-m2.7-stock-quality-baseline/20260522T190143Z-eager-no-llmscaler-json-repeat3`
- Result: stalled after model load/KV setup with repeated vLLM
  shared-memory broadcast-block messages and no output files.
- Conclusion: no-llm-scaler is useful as a minimal smoke, but not a reliable
  broader quality baseline on this system today.

### Attempt B: basic llm-scaler MoE only, eager/no graph

This is the practical stock-quality baseline for this hardware:

- `VLLM_XPU_USE_LLM_SCALER_MOE=1`
- `VLLM_XPU_USE_LLM_SCALER_MOE_WS=0`
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS=0`
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0`
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=0`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=0`
- `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=0`
- `VLLM_XPU_ENABLE_XPU_GRAPH=0`
- `enforce_eager=True`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1` kept enabled because it is a
  correctness guard for the Q/K norm weight, not a speed optimization.

JSON repeat result:

- Path:
  `/home/steve/bench-results/minimax-m2.7-stock-quality-baseline/20260522T191047Z-eager-basic-llmscaler-json-repeat3-gmem090/result.json`
- Tasks: `alpha_names`, `number_facts`, `b70_status`
- Pass: `9/9`
- Rejected outputs: `0`
- Accepted output throughput: `13.120 tok/s`
- Total throughput counting prompt tokens per candidate: `31.035 tok/s`
- Repeatability:
  - `alpha_names`: 3/3 accepted, one token hash, one parsed JSON hash
  - `number_facts`: 3/3 accepted, two token hashes but one parsed JSON hash
  - `b70_status`: 3/3 accepted, one token hash, one parsed JSON hash

This is the cleanest current answer to "what does good stock JSON quality look
like?" The model can satisfy strict JSON, ordering, arithmetic, exact field
names, and exact string requirements on a no-graph path.

Website result:

- Path:
  `/home/steve/bench-results/minimax-m2.7-stock-quality-baseline/20260522T191422Z-eager-basic-llmscaler-website-small/result.json`
- Tasks:
  - `skeleton_status_html`: pass, valid complete static HTML, `9.982 tok/s`
  - `simple_gpu_calculator`: fail only on `control_characters`,
    `14.167 tok/s`
- Failure detail:
  the calculator output was structurally complete and included CSS, labels,
  form, JS parsing, calculation, and result area, but emitted a NUL byte in:
  `min="\x00"` where ordinary HTML should have used `min="0"`.

## Interpretation

- The model is capable of clean, deterministic strict JSON on a slow/no-graph
  path.
- It is capable of simple useful HTML on the same path.
- Control-character corruption is not exclusive to the fast forced-graph path:
  it can also appear in no-graph practical HTML, at least in numeric literals.
- The forced-graph 89-93 tok/s path remains suspect for practical quality
  because repeated JSON showed large failure rates. The stock-quality baseline
  establishes that good JSON is possible; fast paths must match this behavior.
- Do not compare fast-path quality against the no-llm-scaler stalled run.
  Compare against Attempt B.

## Working Baseline Standard

Until we have a better upstream/fresh-install baseline, treat this as the
quality floor to preserve:

1. Basic llm-scaler MoE only, eager/no graph.
2. Strict JSON validator, no structured decoding.
3. `9/9` JSON pass on the three-task repeat3 suite.
4. Simple static HTML should pass.
5. Any generated non-whitespace control character is a quality failure.

The next useful comparison is to run the same JSON and small website gates on
each optimized candidate and require equal or better pass behavior before
claiming a speed result is quality-preserving.
