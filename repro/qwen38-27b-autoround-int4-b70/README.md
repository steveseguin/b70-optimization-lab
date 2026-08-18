# Qwen3.8 27B AutoRound INT4 on 2x Intel Arc Pro B70 — lane setup

New optimization lane, opened 2026-08-18, superseding the Qwen3.6 27B INT4
speculative lane. The two models are **architecturally identical**, so the entire
Qwen3.6 optimization stack transfers unchanged.

## Model

`devan-carlin/Qwen3.8-27B-int4-AutoRound`, base `Qwen/Qwen3.8-27B`, Apache-2.0.
Local copy: `/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan`
(19.02 GB, 8 safetensors shards + 11 small files, all verified).

Content manifest: [`manifests/model.json`](manifests/model.json). The upstream
revision is pinned at
[`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`](https://huggingface.co/devan-carlin/Qwen3.8-27B-int4-AutoRound/tree/bce40cacab0a4535b92fb3d57615c2bea9adf3d1).
An independent download at
`/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround` matched all recorded
file identities and the exact `19,016,930,167`-byte payload.

## Why the existing stack transfers

| Property | Qwen3.6 (old lane) | Qwen3.8 (this lane) |
| --- | --- | --- |
| architecture class | `Qwen3_5ForConditionalGeneration` | same |
| text `model_type` | `qwen3_5_text` | same |
| layers / hidden | 64 / 5120 | same |
| **vocab size** | 248320 | **same** |
| attention heads / KV heads | 24 / 4 | same |
| linear key / value heads | 16 / 48 | same |
| `full_attention_interval` | 4 | same |
| `mtp_num_hidden_layers` | 1 | same |
| `quant_method` | `auto-round` | same |
| bits / group size / packing | 4 / 128 / `auto_round:auto_gptq` | same |

Consequences:

- vLLM routes `auto-round` to `INCConfig`
  (`vllm/model_executor/layers/quantization/__init__.py:164`), so the whole INT4
  W4A16 path applies: `int4_gemm_w4a16`, the oneDNN completion barriers and
  input-dependency controls, and the INT8 LM head.
- `Qwen3_5ForConditionalGeneration` and `Qwen3_5MTP` are both registered
  (`registry.py:564`, `:634`), and the checkpoint ships **29 MTP tensors**
  (`mtp.fc.weight`, `mtp.layers.0.*`, `mtp.norm.weight`), so MTP speculative
  decoding is available.
- The vocabulary is byte-for-byte the same size, so the masked-max greedy
  sampler fix carries its full benefit.
- The upstream README warns that mixed symmetric/asymmetric INT4 checkpoints
  need devan-carlin's empty/shape-compatible qzeros guard on the newer XPU/ARK
  path ([vLLM PR #52428](https://github.com/vllm-project/vllm/pull/52428)).
  The pinned older vLLM tree has only a present/non-null check at
  `inc.py:822-825`, not that newer guard. This exact checkpoint nevertheless
  loaded successfully in the recorded baseline. Do not generalize that success
  to a different AutoRound export or claim PR #52428 is already present.

## Reference point

The model author measured **47.8 tok/s** on 4x B70 at TP=4, no speculation,
`max_tokens=16384` (versus 30.2 for BF16). That is not comparable to this lane's
TP=2 + MTP3 configuration, and it is far below what the identical Qwen3.6
architecture reaches here (~95 tok/s), so it should be treated as a floor, not a
target.

## Running an arm

The Qwen3.6 harness is reused directly. Two environment variables retarget it:

```bash
MODEL_DIR=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan \
VALIDATION_MODEL_MANIFEST=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json \
  ...run-arm.sh spec-native-partition-exact-native 0,1 "$root" "$baseline"
```

`VALIDATION_MODEL_MANIFEST` was added for this lane and defaults to the Qwen3.6
manifest, so every existing Qwen3.6 arm is unaffected.

The known-good deterministic configuration and its flag set are documented in
[`../qwen36-27b-autoround-int4-b70-determinism-20260818/README.md`](../qwen36-27b-autoround-int4-b70-determinism-20260818/README.md)
section 7a; start from that rather than re-deriving it.

## Open items

- No quality baseline exists for this model yet. The Qwen3.6 baseline is a
  different checkpoint and must **not** be reused as a correctness oracle; a new
  one has to be generated before any parity or quality claim.
- The vision tower (333 tensors) is unused for text benchmarking; the config
  carries `language_model_only`.
- Do not use stock `intel/llm-scaler-vllm:0.21.0-b3.1` as a substitute for the
  pinned source stack on a 16 GB host. An independent eager TP2 smoke first hit
  its FP8-only GDN output-projection probe on an INT4 `qweight`; disabling that
  optional probe allowed all weights to load, but a 9 GiB cgroup then killed a
  worker during warmup and triggered one BCS reset. See the
  [safety note](../../experiments/qwen38-27b-b70/notes/2026-08-18-autoround-int4-stock-image-lowram-unsafe.md).
