# Qwen3.8 Flash Next FP8 + DeepSeek V4 Flash 0731 REAP post-download gate

Status: both targets passed their pinned full validations. Qwen completed at
`2026-08-26T21:25:03Z`; DeepSeek completed at `2026-08-28T20:13:48Z`. These
storage passes are not B70 runtime validation.

The inert validator is
[`scripts/validate-20260826-pinned-hf-downloads.py`](../scripts/validate-20260826-pinned-hf-downloads.py).
Running it without `--execute` only prints the frozen plan. It must reject an
explicit run before creating evidence if either matching `hf download` process
or any `.incomplete` file remains. It validates the targets sequentially and
does not read, print, or pass a Hugging Face token.

## Frozen identities and closure

| Target | Revision | Files / bytes | Shards / bytes | Index closure |
| --- | --- | ---: | ---: | ---: |
| `Qwen/Qwen3.8-Flash-Next-FP8` | `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` | 144 / 185,563,783,127 | 131 / 185,523,317,458 | 152,089 tensors; `total_size=185502232570` |
| `0xSero/DeepSeek-V4-Flash-0731-REAP` | `ddc04540efda3d2a0788b129f1fad828ddc19b60` | 80 / 107,818,438,413 | 48 / 107,808,354,264 | 45,821 tensors; `total_size=107803320952` |

The validator pins the exact cached Hugging Face tree SHA-256 for each immutable
revision. Qwen has 133 LFS objects: 131 model shards plus the model index and
tokenizer. DeepSeek's `SHA256SUMS` has 79 entries covering exactly every tree
file except itself; the checksum file itself is closed by its pinned Git blob
ID. Its REAP manifest's NVIDIA/DGX Spark pass is provenance only, not B70
evidence.

## Frozen order and interpretation

1. Require both download processes to have exited and zero `.incomplete` files.
   Persistent empty `.lock` files are not a failure.
2. Validate the pinned tree hashes, exact root inventory, exact byte counts,
   per-file completion metadata, revision, and ETag/LFS identity.
3. Run the pinned, tokenless Hugging Face dry-run. It must return the full exact
   file set with no file requiring download.
4. Hash one target and one file at a time. Check LFS SHA-256, publisher SHA-256
   where supplied, and Git blob IDs for ordinary files.
5. Strict-parse the index and every safetensors header. Require exact contiguous
   shard closure, exact index-to-header tensor sets, valid non-overlapping
   payload ranges, exact tensor counts, and exact indexed payload bytes.
6. Preserve dry-run output, hash receipts, header receipts, and the final result
   beneath `data/model-intake/post-download-validation-20260826/<UTC>/`.

The gate is fail-closed. A failure means quarantine and repair/redownload only
the identified artifact; it does not authorize a benchmark, model-file edit,
or reinterpretation of an older result. A pass authorizes only the separately
preregistered B70 target-only bring-up.

The completed Qwen evidence root is:

`data/model-intake/post-download-validation-20260826/20260826T211840Z/`

Its `summary.json` records `status=pass`; the hash log contains 144 passing
file rows and the header log contains 131 passing shard rows. Qwen is therefore
fully validated as a downloaded artifact, but no B70 load is authorized until
the separate XPU runtime and memory gates close.

The completed DeepSeek evidence root is:

`data/model-intake/post-download-validation-20260826/20260828T201005Z/`

Its `summary.json` records `status=pass`; the hash log contains all 80 passing
file rows and the header log contains all 48 passing shard rows. The receipt
binds revision `ddc04540efda3d2a0788b129f1fad828ddc19b60`, the exact
107,818,438,413-byte tree, publisher `SHA256SUMS`, 45,821 tensors, and the
tokenless pinned dry-run. This authorizes only the separately preregistered
target-only B70 bring-up and revision-bound draft-pack construction; it does
not transfer the historical K160 speed or quality result.

## Verifying a relocated Qwen copy

Use the path-parameterized
[`verify-qwen38-flash-next-fp8-tree.py`](../scripts/verify-qwen38-flash-next-fp8-tree.py)
after copying this exact Qwen tree to another disk. The revision and artifact
identity remain frozen in the verifier; only the candidate model root and JSON
receipt path are configurable. The receipt must be outside the model tree.

```bash
python3 scripts/verify-qwen38-flash-next-fp8-tree.py \
  --model-root /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 \
  --receipt /mnt/fast-ai/llm-models/.verification/Qwen3.8-Flash-Next-FP8.json
```

It binds the cached Hugging Face tree metadata to revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, requires the exact 144-file,
185,563,783,127-byte root inventory, hashes LFS and ordinary Git artifacts by
their respective conventions, checks the fixed config and weight-index hashes,
and requires the index to close over all 131 declared shards. It writes either
a pass or failure receipt atomically. This is a full model read of roughly
185.6 GB; do not run it while the copy or another large model-store transfer is
active.

After both downloads are visibly complete, the exact explicit invocation is:

```bash
python3 scripts/validate-20260826-pinned-hf-downloads.py \
  --execute --ack VALIDATE_PINNED_DOWNLOADS_20260826
```

The combined ordinary checksum pass reads about 293 GB from the USB volume and
should not overlap another large transfer or hash job.
