# Qwen3.8 27B Q4_K_M on one Intel Arc Pro B70

> **Certification: `candidate-portable-repro`, not a starter guide.** This
> packet closes the model, source, patch, build, launch, and validation
> identities. It has not yet been replayed from a clean Ubuntu installation,
> so it does not install or alter the Intel driver or oneAPI toolchain.

This is the repository's current one-card Qwen3.8 path. It runs the target
model directly in llama.cpp/SYCL with no draft model, MTP, response reuse, or
speculative decoding. The final lab captures reached `27.813629` and
`27.824790 tok/s`; all 24 outputs matched the registered oracle, all requests
were cache-zero, and the separate semantic battery passed every canary, 8/8
repeat stability, and the long-context needle.

The current headline re-aggregates final-J as a median of per-input-class
medians: **`27.825726 tok/s`**. `27.824790` remains the all-prompt median and
the older exact capture value; no benchmark row was discarded or replaced.

The result was measured on one B70 selected from a four-B70, 125 GiB host.
That proves one-card execution, not portability to every one-card PC. This
candidate therefore conservatively requires Ubuntu 24.04 and 64 GiB host RAM
until a smaller clean host is validated.

## Exact dependency closure

| Component | Exact source of truth |
| --- | --- |
| Model | [`model-direct.json`](model-direct.json): `ggml-org/Qwen3.8-27B-GGUF` revision `0669b98607d47046c7c2b3f801011d54a08cfccf`, Q4_K_M SHA-256 `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`. |
| Runtime base | `mndodd/llama.cpp` commit `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`. |
| Lab patches | Full Qwen3.6 stack, Qwen3.8 Q4 increment, then the four TP1 artifacts enumerated and verified by [`restore-and-build.sh`](restore-and-build.sh). The authoritative patch explanation is [`patches/qwen38-27b-q4km-tp1-b70s/README.md`](../../patches/qwen38-27b-q4km-tp1-b70s/README.md). |
| Build | Release, shared libraries, Intel SYCL, BMG-G31 AOT, graph, oneDNN, and embedded/prebuilt Web UI paths off; exact CMake command is in `restore-and-build.sh`. The script builds only the server and two benchmark programs used by this packet. |
| Launch | [`run-server.sh`](run-server.sh): one visible Level Zero device, 8K context, F16 KV, one slot, cache RAM zero, exact accepted fusion doors. |
| Validation | [`bench.sh`](bench.sh) requires fresh responses, zero cached tokens, and 12/12 exact hashes against the registered TP1 oracle. The full quality result is [recorded here](../../experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-quality-battery-result.md). |

The final source includes the `q8out-rejected-memo320` artifact because its
memo-table hardening remained in the shipping binary. The rejected Q8 output
door is unset by the launcher and is not part of this lane.

Required patch artifacts, in application order:

1. [Full lab TP2 stack](../../patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64) — decoded SHA-256 `f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998`.
2. [Qwen3.8 Q4_K_M increment](../../patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64) — `0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`.
3. [TP1 GDN state-I/O widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-gdn-state-io-widen-20260821.diff.gz.b64) — `1377fd89ea595f4d6e0654ce07387f9e0c2438f6677360c4c94cd99072ce6272`.
4. [TP1 convolution/QK widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-conv-qk-widen-20260821.diff.gz.b64) — `5b0141e3ef6be67365e638ef796247e25280b1bf1e7c11e61c77aba0657fcb7b`.
5. [TP1 QK source-shape widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-qk-norm-rope-src-widen-20260821.diff.gz.b64) — `8299e77c2186bc2d024c1a9030ed69aafcad26442296a68523dde1a1b6d46c7e`.
6. [Rejected Q8-output experiment plus retained memo hardening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-q8out-rejected-memo320-20260821.diff.gz.b64) — `717bc1cc3eda198ded7df4e2a0046fd1ce88434c47e702feecaf4dff258142d0`.

`restore-and-build.sh` decodes and verifies those identities before touching
the new source checkout.

## 1. Download the exact model

Install the current Hugging Face CLI, choose a storage location with at least
20 GB free, and download only the required GGUF:

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q4_K_M.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen3.8-27b-q4km
```

The weights remain distributed by the publisher. This repository stores the
immutable identity and the code needed to reject a partial or corrupted copy.

## 2. Restore and build our exact source stack

The script refuses to overwrite an existing path, checks every decoded patch
before applying it, and defaults to a conservative two build jobs:

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-tp1 \
  repro/qwen38-27b-q4km-tp1-b70/restore-and-build.sh
```

It defaults to the observed Intel oneAPI 2026.0 compiler path. The script
initializes `/opt/intel/oneapi/setvars.sh` so CMake can resolve IntelSYCL, MKL,
and their runtime libraries; naming `icpx` alone is insufficient in a fresh
shell. This dependency is intentionally not auto-installed while the
clean-host platform recipe is still unverified.

For an explicitly separate experimental identity, another installed compiler
can be selected without editing the recipe:

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-tp1 \
CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  repro/qwen38-27b-q4km-tp1-b70/restore-and-build.sh
```

Do not pool results from an override with the 2026.0.0 package headline. A
2026.1.1 reconstruction completed under a 10 GiB build cap on 2026-08-25 and
exposed the missing oneAPI initialization and unwanted UI download that this
revision fixes; it remains a different compiler identity.

## 3. Preflight

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q4km \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q4km-tp1-b70/preflight.sh
```

Preflight is non-mutating. It checks the tested OS boundary, memory, render
access, runtime files, absence of a competing server, and model identity.
Model verification reads 18.97 GB through `O_DIRECT` (or a direct-I/O
fallback) and then again through the ordinary path. Both must match.

## 4. Launch and validate

In the serving terminal:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q4km \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-tp1/build-sycl-aot-bmg-g31 \
GPU_INDEX=0 \
  repro/qwen38-27b-q4km-tp1-b70/run-server.sh
```

The launcher verifies the model again immediately before loading it. From a
second terminal:

```bash
curl -fsS http://127.0.0.1:18088/health

OUT=/path/to/qwen38-q4km-tp1-result.json \
  repro/qwen38-27b-q4km-tp1-b70/bench.sh
```

Success requires `cached_tokens_all_zero=true`,
`output_hashes_exact=12/12`, and `realistic_final_gate_passed=true`. Speed is
informational until those gates pass. Stop the foreground server with
`Ctrl-C`; then confirm `pgrep -x llama-server` returns no process.

### Qualified HTTP depth and TTFT

The separate pinned oneAPI 2026.1.1 audit ran the same realistic suite and a
one-slot exact-token HTTP sweep through 32K active context. The realistic
suite passed 12/12 registered outputs at `27.785930 tok/s` median decode and
`262.869 ms` median TTFT. The exact 32,768-token receipt passed cache,
truncation, token-count, and returned-token gates at `24.488129 tok/s` and
`50,266.550 ms` TTFT. The depth fixture is synthetic grade C and is kept
separate from natural-prompt evidence. Use the retained
[preregistration](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-depth-r1-prereg.json),
[runner](../../experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-http-depth.sh),
and [result](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-depth-r1-result.json)
to repeat that exact research profile; do not silently change the context,
KV type, slot count, compiler identity, or metric.

### Concurrent-serving boundary

The promoted launcher deliberately remains a one-slot, 8K context profile.
A separately identified oneAPI 2026.1.1 research build proved that a 64-slot
server with 32K total context (`512` tokens/slot) can load and complete on one
B70, but it used `32281.7 / 32656 MiB` and failed exact batch-shape output
identity plus point-order stability. Do not turn its `86.28 / 85.97 tok/s`
64-way diagnostic into a deployment promise. The retained
[result](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-result.md),
[preregistration](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-prereg.json),
and [runner](../../experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-http-smallctx.sh)
make the rejected publication boundary auditable.

The corrected r2 harness uses native HTTP raw token IDs, disables prompt
caching and slot similarity at the server, and restarts between retained
attempts. The preregistered r3 confirmation measured
`24.64, 36.55, 49.32, 56.12, 54.97, 65.80, 83.80` aggregate tok/s at 1→64
users; fresh-attempt relative range was at most 2.03%.
All responses contained 128 raw IDs and none collided with a different base
task's oracle. Exact sequential greedy identity nevertheless becomes
batch-shape-dependent in multi-user serving. Treat the
[r3 curve](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-http-concurrency-r3-result.md)
as measured service capacity with that output warning, not deterministic
serving. The retained [runner](../../experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-http-concurrency-r3.sh)
reproduces the exact cache-off profile.

## Beginner recovery checklist

This checklist is safe to use on an existing installation; it does not claim
that the Intel stack has been clean-host certified yet.

For an actual fresh installation, follow the fail-closed
[clean-host certification runbook](CLEAN-HOST.md). It links Intel's current
primary driver/oneAPI instructions and defines the platform, build, model,
endpoint, and repeat receipts required before the badge may change.

1. **The compiler or IntelSYCL package is missing.** Confirm that
   `/opt/intel/oneapi/setvars.sh` exists, then start a new shell and run
   `source /opt/intel/oneapi/setvars.sh --force`. Check `command -v icpx` and
   `icpx --version` before rebuilding. Do not mix objects from two compiler
   versions; use a new `SOURCE_DIR` for an override.
2. **No SYCL GPU appears.** Run `sycl-ls`, `ls -l /dev/dri`, `id`, and
   `xpu-smi discovery`. The user must have access to the render device (often
   via the `render` group). Log out and back in after a group change. Do not
   work around permissions with world-writable device nodes.
3. **Model verification fails.** Stop. Re-run
   `verify-model-direct.sh /path/to/Qwen3.8-27B-Q4_K_M.gguf`. A cached read is
   not enough: both direct and ordinary SHA-256 checks must equal the identity
   in `model-direct.json`. Delete and download only the bad file; never patch
   around a checksum failure.
4. **The build tries to download a Web UI or runs out of memory.** Use only
   `restore-and-build.sh`; this revision disables those unused paths and
   defaults to two jobs. Start from a new source directory after a failed or
   manually modified build. Lower `BUILD_JOBS=1` on a small host.
5. **The server cannot allocate the model or KV cache.** Ensure no other model
   process is active with `pgrep -af 'llama-(server|bench)|vllm'`. Start with
   the supplied one-slot 8K launcher. Do not copy the research 64-slot flags;
   that profile nearly filled the card and failed output-stability gates.
6. **Health works but validation fails.** Preserve the JSON and server log.
   A nonzero cache count, stale response, or output-hash mismatch invalidates
   the speed. Stop the server, verify the exact binary/model identities, and
   repeat once from a fresh process; do not average a failed attempt into a
   passing one.

For a useful issue report, attach the preflight output, `icpx --version`,
`sycl-ls`, `xpu-smi discovery`, the exact failing command, the server log,
and the benchmark JSON. Remove usernames and unrelated environment secrets.

## Evidence and remaining gates

- [Final quality and performance result](../../experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-quality-battery-result.md)
- [Final capture I](../../experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-final-i.json) and [capture J](../../experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-final-j.json)
- [Quality battery JSON](../../experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-quality-battery.json)
- [2026-08-22 direct-I/O model verification](model-verification-20260822.json)
- [2026-08-25 qualified realistic HTTP and exact-depth result](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-http-depth-r1-result.md)

Still open: a tested clean-host driver/oneAPI installation, a clean-host
source build plus endpoint replay, and batch-shape-invariant greedy output in
multi-user serving.
Until those are closed, call this a candidate—not a one-click installer.
