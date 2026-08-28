# Qwen3.8 Flash-Next FP8 TP4/MTP3 Grade-C foundation

> **Status: `pre-publication`; not a runnable guide.** This directory closes
> host-only model, source, and native-runtime identity checks. It deliberately
> refuses to launch, test, or stop a service until public runtime hosting,
> dependency installation, portable topology checks, and an artifact-only
> replay are complete. It is not registered in the guide or package catalogs.

This is the foundation for one narrowly defined four-card profile, not the full
Flash-Next matrix:

- model: `Qwen/Qwen3.8-Flash-Next-FP8` at
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- four Intel Arc Pro B70 32 GiB cards, TP4 and EP4;
- eager execution, graph off, publisher MTP with three speculative tokens;
- configured maximum length 4,352, one active sequence, 64 maximum batched
  tokens, `294195200` KV-cache bytes, 25 cache blocks, BLHNC KV layout;
- selective UVA placement of the PLE n-gram and input embeddings, measured as
  `13,117,911,040` host-resident/GPU-addressable bytes per rank;
- vLLM measured commit `1372c62d975c554f4b465c8299bc5f3295301ceb`
  (tree `31ebb7785df4686df1ef03b0f4ef56b660022a06`);
- exact loaded kernel-stage build head
  `2f829747503c77d4814834dffd0840fb1dd9f75a` (tree
  `d8c4318a0f0d71c3c36867253ad92b377906fec9`).

The later kernel checkout head `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`
was present on the origin host but was **not** the runtime stage loaded for the
measurement. It must not be substituted for the stage identity above.

## What Grade C means here

The historical lab result is
[`20260827-tp4-mtp3-4352-attempt1-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-4352-attempt1-result.json).
It established a healthy TP4 API, active MTP3 counters, exact parity with the
sealed MTP0 outputs at the tested depth, a complete exact-4K response, and no
prompt-cache reuse. It did not establish production readiness or a portable
install.

Keep these metrics separate:

| Historical workload | Metric | Result |
| --- | --- | ---: |
| p4096/o128 exact-depth fixture | conventional 99-interval decode | `4.669548248983529 tok/s` |
| p4096/o128 exact-depth fixture | TTFT | `266.08089533800376 s` |
| three p4096/o256 service screens | median decode after first text | `15.50156510641242 tok/s` |
| three p4096/o256 service screens | median wall output | `1.2462600034136797 tok/s` |
| three p4096/o256 service screens | median TTFT | `187.8991858829977 s` |

The `15.50 tok/s` value is an after-first-text service screen, not the
conventional 99-interval headline. Its TTFT and wall rate are mandatory context.
The MTP0 comparison used a different vLLM source tree, so its numerical deltas
are descriptive cross-run evidence, not a causal MTP-depth A/B.

The inherited direct-answer target passed five of seven strict cases in this
historical run; MTP3 matched all 26 sealed MTP0 comparisons and passed the exact
4K needle. That is exact-depth parity evidence, not full model-quality
qualification. A separate official-thinking MTP0 result cannot establish MTP3
thinking parity.

## Frozen model identity

[`model-contract.json`](model-contract.json) freezes 144 root files, 131 model
shards, `185,563,783,127` root bytes, the revision, Hugging Face tree metadata,
config, and index identities. The historical full-verification receipt hash is
recorded as evidence, but its origin-host path is not a public dependency.

Verify a candidate model tree offline and write a new receipt outside it:

```bash
python3 repro/qwen38-flash-next-fp8-tp4-mtp3-b70/verify-model.py \
  --model-root /path/to/Qwen3.8-Flash-Next-FP8 \
  --receipt /path/to/new-model-verification.json
```

This wrapper requires the JSON contract to agree exactly with the shared
full-tree verifier before hashing the 185 GB tree.

## Reconstruct the exact source trees

The source helper reuses the certified patch-series verifier. It needs local
Git repositories that contain the public bases, creates independent clones
without Git alternates, applies only the production series, and refuses an
existing output directory or receipt:

```bash
python3 repro/qwen38-flash-next-fp8-tp4-mtp3-b70/prepare-sources.py \
  --vllm-source /path/to/public-vllm \
  --kernel-source /path/to/public-vllm-xpu-kernels \
  --output-root /path/to/new-source-root \
  --receipt /path/to/new-source-receipt.json
```

The expected outputs are vLLM tree
`31ebb7785df4686df1ef03b0f4ef56b660022a06` and kernel tree
`d8c4318a0f0d71c3c36867253ad92b377906fec9`. This reconstructs source;
the patch series remains staged on each detached public base, and `git
write-tree` yields the recorded output identity. It does not claim to reproduce
the measured native bytes from a clean build.

## Verify and install the exact hybrid runtime

The native stage is an exact 18-file **hybrid certified staged runtime**. Only
`_moe_C.abi3.so` was freshly rebuilt at kernel commit `2f829747`; the other 17
files were retained unchanged from the prior known-loadable stage. The bytes
are certified and were loaded by the historical measurement. This is not a
claim that all 18 files were freshly built at that commit or that a clean build
will be byte-identical.

The uncompressed archive is `1,968,250,880` bytes and has SHA-256
`6bf1b547e3887c86007f5ef5ad7c67be365ce4888f0e2c0a1f360dde7a7b13c3`.
Its two exact parts are frozen in [`runtime-contract.json`](runtime-contract.json).
Their URL fields are deliberately null: the files have **not** been publicly
hosted or verified by public readback.

For an authorized local copy of both parts, the offline installer:

1. rejects missing or extra matching part filenames;
2. verifies each exact size and SHA-256 while concatenating in index order;
3. verifies the complete tar size and SHA-256;
4. rejects unsafe, duplicate, reordered, missing, or extra tar members and
   checks deterministic tar metadata;
5. verifies the embedded metadata and manifest;
6. extracts only the 18 declared files into
   `$KERNEL_STAGE/vllm_xpu_kernels`, rehashes them, and rejects any existing
   destination.

```bash
python3 repro/qwen38-flash-next-fp8-tp4-mtp3-b70/prepare-runtime.py \
  --parts-dir /path/containing/the-two-parts \
  --kernel-stage /path/to/new-kernel-stage \
  --work-dir /path/with-at-least-2GB-temporary-space \
  --receipt /path/to/new-runtime-install-receipt.json
```

The tool reads and hashes payload bytes but never imports native modules or
accesses a GPU. Installation is identity closure only, not runtime validation.

## Intentionally blocked commands

`preflight.sh`, `run-server.sh`, `quality.sh`, and `stop.sh` all exit nonzero.
They are visible placeholders so no catalog or downstream tooling can mistake
this directory for a runnable guide.

Before enabling them, the package still needs:

1. durable public URLs for both runtime parts and successful independent
   download/readback verification;
2. an exact, installable Python/native dependency lock (the historical host
   used Python 3.12.13, Torch `2.11.0+xpu`, Triton `3.7.0`, Intel SYCL runtime
   `2025.3.2`, and source-overlaid vLLM; installed distribution version strings
   alone do not identify the source);
3. portable four-B70/XCCL/topology, memory, shared-memory, filesystem, cache,
   and process-ownership checks without origin-host BDF or USB assumptions;
4. a fresh origin-host startup using only the reconstructed sources, newly
   installed runtime stage, pinned model, and prepared dependency environment;
5. health, model-list, smoke, cache-zero, deterministic quality, exact-4K
   needle, MTP3 engagement, fixed benchmark, and controlled-stop receipts;
6. a full run-identity diff against the historical result before interpreting
   speed. Any replay is additive evidence and must not overwrite the existing
   measurements.

Only after those gates should this become a cataloged `lab-replay` or
`candidate-portable-repro`. It is not a starter guide or deployment-ready
package.

## Host-only tests

The tiny-fixture tests use no model, native binary, network, or GPU:

```bash
python3 -m unittest \
  repro/qwen38-flash-next-fp8-tp4-mtp3-b70/test_prepare_runtime.py
```

They cover valid nested installation and fail-closed behavior for traversal,
extra members, missing members, part hash changes, reassembly mismatch, and
wrong archive layout.
