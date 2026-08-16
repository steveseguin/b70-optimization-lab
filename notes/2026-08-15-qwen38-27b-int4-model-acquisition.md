# Qwen3.8 27B INT4 AutoRound Model Acquisition

Date: 2026-08-15 (America/Toronto)

## Outcome

Downloaded and fully verified the closest Qwen3.8 successor to the active
Qwen3.6 27B AutoRound/XPU model:

- Hugging Face: `devan-carlin/Qwen3.8-27B-int4-AutoRound`;
- pinned revision: `bce40cacab0a4535b92fb3d57615c2bea9adf3d1`;
- external-storage path:
  `/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan`;
- convenience symlink:
  `/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-devan`;
- repository bytes: `19,016,930,167` (`17.71 GiB`).

Every pinned repository file passed exact size and identity verification. LFS
files were checked with SHA-256 and small files with Git blob SHA-1. This
covered all seven main safetensor shards, `model_extra_tensors.safetensors`,
the tokenizer, index, configuration, and model card: 19/19 files and
`19,016,930,167` expected bytes passed.

The structured manifest is
[`data/qwen38-27b-model-acquisition-20260815.json`](../data/qwen38-27b-model-acquisition-20260815.json).

## Selection Rationale

The pre-download Hugging Face audit found no Intel-owned Qwen3.8 AutoRound
checkpoint. The selected checkpoint is the closest structural match to the
current optimized target, `webhie/Qwen3.6-27B-int4-AutoRound` revision
`f5750c90b3776db658594df5fe8051098226dd8e`:

- AutoRound W4A16, INT4, group size 128, symmetric configuration;
- `packing_format=auto_round:auto_gptq`;
- seven main safetensor shards;
- one intrinsic MTP layer carried in `model_extra_tensors.safetensors`;
- `mtp.fc` and sensitive GatedDeltaNet `in_proj_a`/`in_proj_b` projections kept
  at BF16;
- the remaining MTP attention/MLP draft block quantized to INT4;
- model card explicitly targets vLLM on four Intel Arc Pro B70 cards.

The checkpoint uses AutoRound `0.14.2`; the existing webhie Qwen3.6 checkpoint
uses AutoRound `0.13.0`. The Qwen3.8 card does not disclose its calibration
dataset, sample count, or iteration count, so it is structurally aligned but
must not be described as an exact reproduction of the webhie quantization
recipe.

## Native MTP

No separate MTP download is needed for vLLM native MTP. The target config has
`mtp_num_hidden_layers=1`, the MTP tensors are indexed in
`model_extra_tensors.safetensors`, and `mtp.fc` remains BF16. This matches the
packaging style used by the current Qwen3.6 target.

## Experimental DSpark Companion

Also downloaded and fully verified:

- Hugging Face: `RadixArk/Qwen3.8-27B-DSpark`;
- pinned revision: `85ef153be924f17ce4bf62726954eeaa4a73e854`;
- external-storage path:
  `/mnt/usb-models/llm-models/qwen3.8-27b-dspark-radixark`;
- convenience symlink:
  `/mnt/fast-ai/llm-models/qwen3.8-27b-dspark-radixark`;
- repository bytes: `2,718,609,744` (`2.53 GiB`);
- BF16 weight SHA-256:
  `9d26d5e637551c244d543c67c790bd0947f360e005c569e5851a185ffe692786`.

All 6/6 pinned files passed verification. This drafter is an experimental
archive, not a known-compatible companion for the downloaded INT4 target. It
was trained and evaluated against `Qwen/Qwen3.8-27B-FP8`, uses custom
`dspark.py` and `dflash.py` code, and its documented serving path is SGLang
DSPARK with FA3. Its repository license is only labeled `other` and has no
LICENSE file. Do not enable `trust_remote_code` or use this checkpoint in a
service until its code, license, target compatibility, and XPU runtime support
are audited.

## Storage And Transfer Notes

- `/mnt/usb-models` had about `1.3 TiB` available and was selected for weights.
- `/mnt/fast-ai` is root-filesystem-backed and had only about `5.7 GiB`
  available, so it received symlinks only.
- `/media/steve/CorsairExternal` was not mounted.
- The initial HF Xet transfer stalled after creating resumable partial files.
  It was interrupted without deleting them and resumed successfully over
  standard Hugging Face HTTP.

## Validation Boundary

This acquisition verifies artifact identity only. It does not establish that
the checkpoint loads on the current vLLM/XPU stack, that its mixed
symmetric/asymmetric loader path is correct, that quality matches BF16, or that
native MTP/DSpark is correct on B70. The model card warns that the XPU/ARK path
needs a `qzeros` guard for mixed symmetric/asymmetric layers while the published
top-level config says `sym=true`; treat that inconsistency as a required loader
and correctness gate before benchmarking.

