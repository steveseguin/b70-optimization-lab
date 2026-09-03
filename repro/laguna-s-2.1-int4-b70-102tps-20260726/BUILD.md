# Laguna source and runtime reconstruction

This packet separates three claims that must not be blurred:

1. **Sealed-evidence audit** is portable and performs no GPU work. The tracked
   record evidence, source bundles, model manifest, token/text oracles,
   accounting, graph evidence, cleanup, and LocalMaxxing receipt can all be
   verified from Git.
2. **Artifact-exact lab replay** uses the originating host's byte-identical
   virtual environment and native libraries. `run.sh --preflight` hashes every
   direct and transitively loaded native object and checks its actual loader
   origin before a service can start.
3. **Source-equivalent rebuild** restores all source and model revisions but is
   a new environment. Compiler and linker output is not promised to be
   byte-identical. It must pass the same 13/13 token/text, cache-zero, 146/145
   topology, treatment, cleanup, and explicit performance-floor gates before
   it is called a reproduction.

The historical build was a mixed native stack assembled during an optimization
campaign. The original single monolithic build command was not sealed, so this
file does not invent one.

## Restore all source provenance

```bash
cd /path/to/b70-optimization-lab
repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-sources.sh \
  /mnt/fast-ai/laguna-repro-sources
```

The command restores five clean worktrees:

| tree | commit | role in the measured native stack |
| --- | --- | --- |
| vLLM record | `e596ef1543466ae1a05e5bb8091f58872e2b18ba` | Python/runtime record source |
| kernel record | `6f9dd3c3a7b1b677a992ca4f431a968408f9c816` | final router/workspace source and `_moe_C` |
| attention runtime | `906190641d708b8028018c5dde653e265c835348` | `_vllm_fa2_C` and `libattn_kernels_xe_2.so` build source |
| native base | `4772f727590c51b72add79350b913d098cf67872` | `_C`, `_xpu_C`, grouped GEMM, and their helper DSOs |
| xpumem source | `18a44f440ca3ac2006d5ba19cd12ccca0a0c9982` | `xpumem_allocator` build source |

The supplemental attention bundle matters. The measured
`_vllm_fa2_C.abi3.so` had an absolute RUNPATH into its old build tree. Earlier
repro code hashed a sibling attention DSO without proving that it was the file
actually loaded. The hardened launcher puts the pinned kernel package first in
`LD_LIBRARY_PATH`, imports all extensions, and verifies `/proc/self/maps`.

## Restore and verify model payloads

The tracked manifest contains only the 32 release payload files. Hugging Face
cache locks, metadata, and incomplete downloads are intentionally excluded.

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-models.sh \
  --download /mnt/fast-ai/llm-models/laguna-s-2.1
```

The downloader reads the token from
`/home/steve/.config/huggingface/token`, requests these immutable revisions,
and then hashes the complete payload:

- `poolside/Laguna-S-2.1-INT4` at
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- `poolside/Laguna-S-2.1-DFlash-INT4` at
  `5e07c246915c86dc6920fead03d019989224f2ba`.

For an existing copy, use `restore-models.sh --verify`.

## Observed toolchain

- Ubuntu `24.04.4 LTS`, kernel `7.0.0-28-generic`, x86-64;
- Python `3.12.13`;
- Intel oneAPI DPC++/C++ `2025.3.3`;
- `CC=/opt/intel/oneapi/compiler/2025.3/bin/icx`;
- `CXX=/opt/intel/oneapi/compiler/2025.3/bin/icpx`;
- CMake `Release`;
- PyTorch `2.12.0+xpu`, Triton XPU `3.7.1`, oneCCL `2021.17.2`;
- default paged-decode and chunk-prefill configs for the attention build.

The complete observed package listing is
`manifests/pip-freeze-observed.txt`. Its editable vLLM and kernel metadata is
stale and path-specific, so it is evidence, not an installable lock file.
`manifests/runtime-lock.json`, Git HEADs, module origins, hashes, and loaded
DSO maps are authoritative.

## Source-equivalent native rebuild

Start with a Python 3.12 environment containing the exact package versions in
`manifests/runtime-lock.json`, source the versioned oneAPI 2025.3 environment,
and build with isolation disabled. The package's standard full-build entry
point is:

```bash
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
export CC=/opt/intel/oneapi/compiler/2025.3/bin/icx
export CXX=/opt/intel/oneapi/compiler/2025.3/bin/icpx
export CMAKE_BUILD_TYPE=Release
export MAX_JOBS=1
python setup.py build_ext --inplace
```

For the attention-runtime tree, also set:

```bash
export VLLM_PAGED_DECODE_CONFIG=paged_decode_default.conf
export VLLM_CHUNK_PREFILL_CONFIG=chunk_prefill_default.conf
```

Build each module from the source commit named in the provenance table, then
place the resulting modules and helper DSOs together under one
`vllm_xpu_kernels/` directory. Do not reuse the historical absolute RUNPATH as
a dependency mechanism. Put that directory first in `LD_LIBRARY_PATH`.

Because this is reconstructed rather than the missing original build
invocation, its hashes are expected to differ. Record a new runtime lock and
run the full semantic gate. Never substitute new hashes into the sealed
artifact-exact lane and call it the same environment.
