# 2026-07-05 - Native GDN Spec Prefix Contract Check

Status: **closed diagnostic / contract confirmed**. No model throughput claim
and no LocalMaxxing submission.

## Why

The current valid Qwen27 record remains `65.27648650325429 tok/s` for
`webhie/Qwen3.6-27B-int4-AutoRound` with runtime INT8 LM-head BF16 scales.
Fast target-INT8 + draft-INT4 lanes reached `68-72 tok/s` but failed repeat
quality, while ReplaySSM+align is quality-clean but slower (`61-62 tok/s`).

Before writing another GDN state patch, we needed to verify the native packed
`gdn_attention_spec_decode` state-column contract directly. A previous prefix
source/count hypothesis produced plausible speed but wrong text; this check
prevents reopening that trap.

## Harness

Added:

- `../../../scripts/check-gdn-native-spec-prefix.py`

The script calls native XPU `torch.ops._xpu_C.gdn_attention_spec_decode`
directly and compares its published packed prefix rows against repeated
one-token native `torch.ops._xpu_C.gdn_attention` decode steps. It does not
launch a vLLM server and does not measure endpoint throughput.

The contract under test:

- `spec_state_indices_tensor[:, j]` is the state after packed spec row `j`;
- `num_accepted_tokens=N` selects source column `N - 1` for the next packed
  spec step;
- there is no independent persistent base column inside the native packed
  table. Column 0 is copied from the selected accepted source before the op and
  then overwritten with the row-0 prefix state.

This matches the read-only source audit:

- `gdn_attn_interface.cpp` first selects `accepted_state_indices` from
  `num_accepted_tokens`, selects column 0 as the running destination, copies
  accepted conv/SSM state into column 0, then runs the packed op;
- `spec_decode.hpp` maps `num_accepted_tokens` to `count - 1`;
- both conv and SSM publishers write `state_indices[row, spec_pos]`, including
  `spec_pos == 0`.

## Commands

```bash
cd /home/steve/llm-optimizations

export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels${PYTHONPATH:+:$PYTHONPATH}"

/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py \
  --device xpu:0 --num-reqs 3 --spec-len 4 --head-k-dim 32 --head-v-dim 32 \
  --json-out data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-check-20260705-gpu0.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py \
  --device xpu:1 --num-reqs 2 --spec-len 3 --head-k-dim 64 --head-v-dim 32 \
  --json-out data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-check-20260705-gpu1.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py \
  --device xpu:2 --num-reqs 4 --spec-len 5 --head-k-dim 32 --head-v-dim 64 \
  --json-out data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-check-20260705-gpu2.json
```

## Results

Artifacts:

- `../../../data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-check-20260705-gpu0.json`
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-check-20260705-gpu1.json`
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-check-20260705-gpu2.json`
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-spec-prefix-check-20260705-gpu0-fp32.json`

Summary:

| Artifact | Shape | Result |
| --- | --- | --- |
| `gpu0.json` | 3 requests, spec len 4, k/v 32/32 | pass; conv exact, z exact, SSM/core within tolerance; restart source max SSM diff `0.0018310546875` |
| `gpu1.json` | 2 requests, spec len 3, k/v 64/32 | pass; conv exact, z exact, restart max SSM diff `0.00030517578125` |
| `gpu2.json` | 4 requests, spec len 5, k/v 32/64 | pass; conv exact, z exact, restart max SSM diff `0.001922607421875` |
| `gpu0-fp32.json` | fp32 diagnostic | pass under tolerance; packed-vs-one-step numeric ordering is still not bit-exact for SSM/core |

Interpretation:

- The native packed prefix publication/source-selection contract is internally
  consistent across varied `num_accepted_tokens` and shape screens.
- Conv prefix rows and z outputs are exact in these checks.
- SSM/core outputs can differ slightly between packed and repeated one-token
  execution because the arithmetic order differs; the harness uses tolerance
  for this and keeps exact-equality fields separate.
- The fast draft-INT4 repeat/order failure is not explained by a simple native
  `num_accepted_tokens` source-column off-by-one.

## Consequences

Do **not** repeat or promote patches that globally convert GDN
`num_accepted_tokens` to accepted-drafts-only, plus-one source columns, or
prefix-count source columns. Those ideas select the wrong boundary and have
already produced plausible-but-invalid outputs like `blue, green, red` or
`blue, green, red, yellow` in the wrong mode.

The next credible implementation path is an exact accepted-prefix
GDN/DeltaNet transaction:

1. keep normal `num_accepted_tokens` semantics (`count - 1` source in the
   packed native table);
2. make ReplaySSM/tape commit the exact path instead of relying on a separate
   post-verify Python per-layer loop;
3. prefer commit-at-next-GDN-forward or a batched native commit over another
   scheduler-visible column-offset patch;
4. validate with `../../../scripts/check-gdn-spec-recurrent-exact.py` and this
   native prefix harness before any endpoint run.
