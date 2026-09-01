# Qwen3.8 Flash-Next FP8 TP4/MTP3 Grade-C foundation

> **Status: `research-status` / runtime hosted; not a runnable guide.** This directory closes
> host-only model, source, and native-runtime identity checks. It deliberately
> refuses to launch, test, or stop a service until dependency installation,
> portable topology checks, and an artifact-only replay are complete. The
> exact runtime is now publicly hosted and independently read back. This is
> registered only as research status in the guide
> catalog and has no model-package entry.

This is the foundation for one narrowly defined four-card profile, not the full
Flash-Next matrix:

For a concise, dated map of the fastest retained short screen, the preferred
exact-4K profile, and every reconstruction dependency, see the
[`2026-08-31 experimental snapshot`](EXPERIMENTAL-SNAPSHOT-20260831.md).

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

The separate configured-512 MTP4 research screen reached `20.727176 tok/s`
after first text, but it used a narrow repetitive workload and remains Grade C.
It is not a conventional realistic-suite headline and does not support a
`>30 tok/s` Flash-Next claim. Its exact identity and LocalMaxxing-withheld
disposition are recorded in the dated snapshot above.

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
Git repositories that contain the public bases, fetches each exact base at
depth one into an independent repository without Git alternates, applies only
the production series, and refuses an existing output directory or receipt:

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

This command was replayed from the two current local source repositories on
2026-08-27 and reproduced both recorded trees. The local-only receipt is
`/mnt/fast-ai/qwen38-runtime-publication/qwen38-flash-next-source-restore-replay-20260827.json`
(SHA-256
`d1490380ccdeda04e0a5732d8fc51a16b2f3b0d0f65e7e508defde2c9a692882`);
that path is evidence from the origin host, not a public dependency.

## Verify and install the exact hybrid runtime

The native stage is an exact 18-file **hybrid certified staged runtime**. Only
`_moe_C.abi3.so` was freshly rebuilt at kernel commit `2f829747`; the other 17
files were retained unchanged from the prior known-loadable stage. The bytes
are certified and were loaded by the historical measurement. This is not a
claim that all 18 files were freshly built at that commit or that a clean build
will be byte-identical.

The uncompressed archive is `1,968,250,880` bytes and has SHA-256
`6bf1b547e3887c86007f5ef5ad7c67be365ce4888f0e2c0a1f360dde7a7b13c3`.
Its two exact parts and immutable release URLs are frozen in
[`runtime-contract.json`](runtime-contract.json). The assets are published in
the [research prerelease](https://github.com/steveseguin/b70-optimization-lab/releases/tag/qwen38-flash-next-runtime-2f829747-20260827).
Both parts, the manifest, and the packaging receipt were downloaded without
authentication, rehashed, reassembled, and installed into a fresh directory.
The machine-readable evidence is
[`publication-readback.json`](publication-readback.json).

Download the two parts into a new directory using the exact URLs in the
contract. For example:

```bash
curl --fail --location --remote-name \
  https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-flash-next-runtime-2f829747-20260827/qwen38-flash-next-runtime-stage-2f829747.tar.part-0000
curl --fail --location --remote-name \
  https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-flash-next-runtime-2f829747-20260827/qwen38-flash-next-runtime-stage-2f829747.tar.part-0001
```

Then the offline installer:

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

The work filesystem needs about 2 GB for reassembly, while the kernel-stage
filesystem simultaneously needs about 2 GB for extraction (about 4 GB free if
both paths share one filesystem), plus small filesystem overhead.

The tool reads and hashes payload bytes but never imports native modules or
accesses a GPU. Installation is identity closure only, not runtime validation.
The production command was replayed first against the origin-host split parts,
then against authenticated draft downloads, and finally against a completely
unauthenticated public readback on 2026-08-28. Every replay installed and
rehashed all 18 files. The public readback's local install receipt had SHA-256
`9ce34cf054134b1f5146d72a23eb467cbf276e1c3c7cf6b9f599b5f1321a959e`;
the tracked publication receipt contains the durable evidence and no local
path is required by consumers.

## Observed dependency state (not installable)

[`dependency-contract.json`](dependency-contract.json) and
[`pip-freeze-observed.txt`](pip-freeze-observed.txt) now record the Python side
of the measured hybrid environment. The freeze is a read-only snapshot taken
from the reused lab virtualenv after the measurement, not an atomic
launch-time receipt. It is useful provenance, but it cannot establish that a
clean host will resolve the same environment.

The important distinction is explicit:

- the measured process used Python `3.12.13`, Torch `2.11.0+xpu`,
  `triton-xpu` `3.7.0`, Transformers `5.10.2`, the Intel `2025.3.2` runtime
  wheels, and oneCCL `2021.17.2`;
- `PYTHONPATH` put the reconstructed vLLM source and newly installed native
  stage ahead of site-packages;
- installed vLLM metadata still names an older editable checkout and therefore
  does not identify the code that actually ran;
- the measured versions conflict with several requirements at the measured
  source commit. Installing that checkout's current requirements would drift
  to a different Torch/Transformers/runtime stack, so this packet forbids that
  as a reconstruction shortcut.

[`requirements-runtime.lock`](requirements-runtime.lock) is the 177-entry
non-editable exact-version candidate extracted from the 180-entry observed
freeze. It deliberately contains no direct URLs, VCS inputs, editables, or
hashes yet. [`wheelhouse-contract.json`](wheelhouse-contract.json) therefore
has status `wheelhouse-unavailable`, with zero verified wheels. The packet
remains `dependency-observed`, not `dependency-installable`.

[`prepare-dependencies.py`](prepare-dependencies.py) is the fail-closed offline
installer for the eventual completed contract. It accepts only one exact
binary wheel per locked distribution, verifies file sizes and SHA-256 hashes,
rejects inventory differences, uses pip with networking disabled, creates only
a new virtualenv, verifies installed versions, and writes a receipt. With the
tracked observed-only contracts it exits before creating the output, by
design:

```bash
python3 repro/qwen38-flash-next-fp8-tp4-mtp3-b70/prepare-dependencies.py \
  --wheelhouse /path/to/exact-wheelhouse \
  --output-venv /path/to/new-vllm-xpu-venv \
  --receipt /path/to/new-dependency-install-receipt.json
```

The dependency status can advance only after every candidate line has one
verified platform wheel and hash, followed by a fresh CPU-only offline install
and then the separately gated artifact-only runtime replay. The preparer never
modifies the historical lab virtualenv, installs a source checkout, imports a
native extension, or probes an accelerator.

## Intentionally blocked commands

`preflight.sh`, `run-server.sh`, `quality.sh`, and `stop.sh` all exit nonzero.
They are visible placeholders so no catalog or downstream tooling can mistake
this directory for a runnable guide.

Before enabling them, the package still needs:

1. promote the observed 177-entry candidate into an exact hash-addressed
   binary lock and complete one fresh offline install; installed distribution
   version strings alone do not identify the overlaid source;
2. portable four-B70/XCCL/topology, memory, shared-memory, filesystem, cache,
   and process-ownership checks without origin-host BDF or USB assumptions;
3. a fresh origin-host startup using only the reconstructed sources, newly
   installed runtime stage, pinned model, and prepared dependency environment;
4. health, model-list, smoke, cache-zero, deterministic quality, exact-4K
   needle, MTP3 engagement, fixed benchmark, and controlled-stop receipts;
5. a full run-identity diff against the historical result before interpreting
   speed. Any replay is additive evidence and must not overwrite the existing
   measurements.

Only after those gates should this become a cataloged `lab-replay` or
`candidate-portable-repro`. It is not a starter guide or deployment-ready
package.

## Host-only tests

The tiny-fixture tests use no model, native binary, network, or GPU. The
dependency tests build one tiny pure-Python wheel locally and perform one fresh
offline install to exercise the completed-contract path; they do not claim the
real 177-entry environment is closed:

```bash
python3 -m unittest \
  repro/qwen38-flash-next-fp8-tp4-mtp3-b70/test_prepare_dependencies.py \
  repro/qwen38-flash-next-fp8-tp4-mtp3-b70/test_prepare_runtime.py
```

They cover a valid offline dependency install, observed-only refusal, mutable
lock input, wheel hash and inventory differences, plus valid nested runtime
installation and fail-closed behavior for traversal, extra members, missing
members, part hash changes, reassembly mismatch, and wrong archive layout.
