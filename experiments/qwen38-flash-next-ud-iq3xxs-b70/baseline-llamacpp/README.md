# Pinned llama.cpp measurement baseline

This is a reference-runtime baseline for our own Intel Xe runtime to beat,
**not its code base**. It measures the separate **Qwen3.8 Flash-Next UD-IQ3_XXS
(Unsloth), quantized compressed version**. No fit, speed or output result has
been measured here. CPU-reference arithmetic parity remains unverified even
if the future two repeats agree.

Upstream `ggml-org/llama.cpp` is pinned to
**`23b0202a189c44a54625aadcb37a946dd1d6278d`**, fetched as upstream HEAD on
2026-10-10 (commit time 2026-10-10 19:25:38 UTC). The stored GGUF architecture is
`qwen4exp`: see the retained first-shard header and `qwen4exp.ple.*` metadata in
[packet 1c](../../own-xpu-runtime/stage2/packet1c/ud-census.json).
Upstream registers that exact name in
[`src/llama-arch.cpp`](https://github.com/ggml-org/llama.cpp/blob/23b0202a189c44a54625aadcb37a946dd1d6278d/src/llama-arch.cpp#L44)
and implements its loader, PLE, hyperconnections, recurrent layers and attention
in [`src/models/qwen4exp.cpp`](https://github.com/ggml-org/llama.cpp/blob/23b0202a189c44a54625aadcb37a946dd1d6278d/src/models/qwen4exp.cpp).
This establishes architecture support in source, not qualification of every
operation on SYCL. The mixed IQ2_S/IQ3_S/IQ4_NL expert grids are unchanged.

## Build and CPU evidence

[build-receipt.json](build-receipt.json) records the actual result, complete
CMake options, source/toolchain identities, log hashes, binary and library
SHA256s, and smoke results. [build.sh](build.sh) recreates the unmodified source
checkout and build under `/home/steve/build/flash-next-iq3-baseline-20261010/`.
That directory is outside the lab Git tree; source and binaries are deliberately
retained for the window and are not committed. It is a build artifact directory,
not temporary scratch. No secondary worktree or lab branch is used.

```bash
bash experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/build.sh
```

Builds use nice 19, eight jobs maximum and `OMP_NUM_THREADS=2`. Compiler, MKL
and IntelSYCL resolve to 2026.0; TBB resolves to 2023.0. These are explicit
versioned paths, never `compiler/latest` or an inherited source root.
The initial configure failed because the MKL package could not find TBB;
adding its versioned CMake directory fixed configuration without a source patch.

The requested [Laguna](../../../results/laguna-s-2.1-int4-b70/README.md) and
[MiniMax](../../../results/minimax-m27-int4-autoround-b70/README.md) result
indexes describe vLLM builds. They are not mislabeled as llama.cpp receipts.
Applicable llama.cpp build precedents are the
[Gemma upstream Ninja recipe](../../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/scripts/00-build-llama-cpp-record-stack.sh)
and [Qwen B70 flag recipe](../../../repro/qwen38-27b-q4km-tp1-b70/restore-and-build.sh).
Only build configuration is reused; neither their forks nor patches are used.
The current upstream supports the `bmg_g31` AOT target spelling.

Explicit deviations: `GGML_SYCL_F16=OFF` preserves upstream's F32 arithmetic
path instead of inheriting the older recipes' optional FP16 shortcut; graph,
oneDNN and host-memory fallback are OFF; Level Zero allocation support is ON.
The window also pins dynamic precision to F32. FP16 **KV** is independently
selected at runtime. This is a conservative reference identity, not a claim
that any alternate kernel has passed our CPU arithmetic gate.

The [Laguna SYCL library trap](../../laguna-s-2.1-xpu-b70/notes/2026-07-31-exact-decode-mainloop-specialization-component-result.md)
and [wrong-source build trap](../../laguna-s-2.1-xpu-b70/notes/2026-08-03-int4-tile-record-replacement-design.md)
inform the explicit `-S`, `-B`, compiler/library pins and ELF inspection.
Current CMake resolves IntelSYCL directly; old `OCL_LIBRARY`/FindSYCLToolkit
knobs are not blindly passed as unused settings.

## First native window

[run-identity.md](run-identity.md) fixes the admission requirements, exact
command, all 24 fresh processes, timing definition, comparisons and stop rules.
[prepare-prompts.py](prepare-prompts.py) only renders the retained publisher
GGUF template with Jinja on CPU; [prompt-receipt.json](prompt-receipt.json)
binds the complete fixed 12-prompt suite and rendered bytes. This also avoids
an upstream `llama-completion` chat path that does not pass the thinking switch
to its template input. Its raw-prompt mode receives the already-rendered chat.

Use `llama-completion` for inference. Current `llama-cli` starts an internal
HTTP server, so only its early `--help`/`--version` paths are smoked here.
No server, health probe, device enumeration, systemd operation, port access,
weight download, model-tree write or host-setting change is part of preparation.
The incomplete download prevents the live GGUF-dump check; it is recorded as
skipped, not passed. All native findings remain pending.
