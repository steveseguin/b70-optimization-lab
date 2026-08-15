# Qwen3.6 27B AutoRound INT4 TP2 record source

This directory preserves the exact private source state used by the
`95.384867741895 tok/s` historical Qwen3.6 27B AutoRound INT4 record from
2026-07-11. It is deliberately separate from every GGUF Q8/Q4 lane.

The public repositories do not contain the two recorded source heads. Each
source is therefore represented by:

1. a public prerequisite commit;
2. a small Git bundle containing the private committed continuation; and
3. the exact dirty working-tree patch captured by the benchmark harness.

The bundles retain the commit graph for audit. The patches retain the exact
uncommitted state that actually ran. Neither artifact creates or requires a
named branch: `restore-source.sh` checks out both heads detached.

| Source | Public prerequisite | Recorded committed head | Dirty patch SHA256 |
| --- | --- | --- | --- |
| vLLM | [`c51df43005726a09c6eb7348e8c1b00501c70a8e`](https://github.com/vllm-project/vllm/commit/c51df43005726a09c6eb7348e8c1b00501c70a8e) | `e7213ba8e13b74d7bfa3cbc05435a45df90eb76a` | `dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24` |
| vLLM XPU kernels | [`28e1f5e74c15744b69cf3b760f6160ceabd15de0`](https://github.com/vllm-project/vllm-xpu-kernels/commit/28e1f5e74c15744b69cf3b760f6160ceabd15de0) | `3b4effeeffd83f6ef4696bbe7e76d924a0e9d171` | `edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f` |

The kernel working patch does not include the two graph-safe FlashAttention
patches because those were applied to a staged source copy, not the retained
source checkout. They remain separately tracked at:

- `experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch`;
- `experiments/qwen27_graphsafe_flash_attention/qwen27-force-chunk-decode.patch`.

The large generated kernel binaries are intentionally excluded. Their record
hashes are in the repro packet, and the build recipe reconstructs them from the
restored source with Intel oneAPI 2025.3.

Verify these files with `sha256sum -c SHA256SUMS`, then use
`repro/qwen36-27b-autoround-int4-b70/scripts/restore-source.sh`.
