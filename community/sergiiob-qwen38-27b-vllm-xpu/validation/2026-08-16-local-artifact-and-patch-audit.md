# Local artifact and patch audit — 2026-08-16

This is not a model benchmark. It validates the public identities and copied
patch mechanics before any GPU workload.

## Outcome

- Exact container digest pulled successfully.
- Installed runtime reports vLLM `0.27.2rc1.dev77+gac7509e2b.xpu` and
  `vllm-xpu-kernels` `0.1.12.3`.
- Both copied patchers apply to the installed package, compile, and report
  already-patched on a second run in a disposable, network-disabled,
  device-less container.
- The exact model revision was downloaded locally. All five weight shards and
  the tokenizer match their Hugging Face LFS SHA-256 identities.
- Header inspection confirms all 15 `mtp.*` tensors are BF16 on disk.
- No model was loaded and no GPU code was executed in this artifact audit.
  A later, separately documented target-only GPU validation is linked below.

Evidence level remains `community-reported` for throughput and quality.

See
[`2026-08-16-local-target-only-graph-validation.md`](2026-08-16-local-target-only-graph-validation.md)
for the later B70-tested target-only result. MTP and long-context evidence
remain community-reported.

## Local identities

```text
image: vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
platform manifest: sha256:95949ab8df6d9b358b7c34a6a6a9af04c63cbe07847de70db6a3aae8025de87e
model revision: 9d189a60e4c0ad7f9f47cd94bfa393ca10b3924e
local model: /mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp
```

Verified large-file hashes:

```text
30c8e2b1c82cdcc840848b5c98bafe2f74269b1e6472a053ce7d7b2d002f39a7  model-00001-of-00005.safetensors
ff66eaf6ecc6e4b214f281ac532dcfcb07c60d5a8c78cf145bc93c38c00c024e  model-00002-of-00005.safetensors
15284cb88d52ea1648b4fcc68901286d7c4795388e05ae1e143c8026fcb0be44  model-00003-of-00005.safetensors
878ae6ebc9553de5340df0d6097aa319f58650382c89e474b39d0c0a98e76932  model-00004-of-00005.safetensors
2a6ebd04c77c2d5ce5952ca81a4197f1c34f712a00c293a25242ec27ac413729  model-00005-of-00005.safetensors
06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523  tokenizer.json
```

## Low-memory download lesson

The first attempt used the CLI default of eight file workers inside a 2 GiB
container. Five large Xet transfers ran concurrently, the container reached
its hard memory ceiling, and it exited 137. The host remained responsive and
the completed first shard was retained.

The successful resume kept the same 2 GiB ceiling and added:

```text
hf download ... --max-workers 1
```

Memory then stayed near 0.5–1.9 GiB and the remaining files completed. Four
abandoned `.incomplete` files from the killed attempt were removed only after
all final files passed SHA-256, recovering about 8.7 GB. No completed model
artifact or Hugging Face metadata was removed.

Use `--max-workers 1` for future multi-shard Hugging Face downloads on this
15 GiB host. Never overlap one with a BMG AOT build or model workload.

## Patch anchor result

Unpatched installed-source hashes:

```text
08a83fa1f6bd76fee2e0567d8d440fc05191cbb7a019c1a797ccefb63f51346d  qwen3_5_mtp.py
fda86b96ab5daaf50bd02d022518779c220401dbedc7b28cf478f4c48e72d3d3  gdn_attn.py
```

Patched installed-source hashes:

```text
9c501be7166c3bfc817d07fd9bed1f9ee06e2336ab7d173b6447711c4be76782  qwen3_5_mtp.py
135799921da0d842aae828a23bdbce010ca08ab76848ea08b1e1c1736caf401a  gdn_attn.py
```

The image has two vLLM trees. Patch scripts import and edit the installed wheel
under `/opt/venv/lib/python3.12/site-packages/vllm`, which is used by
`/opt/venv/bin/vllm`. An interactive Python launched from the image's default
`/workspace/vllm` workdir can import that separate untouched tree. Always
record `vllm.__file__` when checking patch state.

The exact pinned model has a `-:.*mtp.*` dynamic exclusion. The unpatched
image already recognizes such exclusions and clears quantization while
constructing the draft. Therefore `patch_mtp_nightly.py` is statically
redundant for this model revision, although a runtime off/on A/B remains
necessary before omitting it from a reproduction recipe.
