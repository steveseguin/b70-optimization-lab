# Qwen3.8 27B Q8_0 + MTP2 — one-B70 candidate package

Qwen3.8 27B Q8_0 weights with a separate Q4_0 MTP draft at depth 2, on one
Intel Arc Pro B70, for one user and short prompts: the measured server holds
**1,024 tokens** of context. It runs a patched native llama.cpp SYCL build that
you compile from source; it is not a container. The draft guesses up to two
tokens ahead and the Q8_0 target checks every guess.

This package keeps the quality-conservative Q8_0 target and adds the pinned
Q4_0 MTP draft at depth 2. Two fresh servers measured a strict
**37.062028 tok/s** class-balanced median versus **19.582597 tok/s** for the
configuration-matched MTP0 control: **+89.26%**. All **24/24** speculative
output arrays were exact to control, every prompt reported cache zero, and all
objective canaries passed.

> **Status: candidate.** The exact artifacts, patch stack, launch, strict
> suite, target oracle, and fresh-server repeat are closed in this repository.
> Clean-host installation/replay and beginner recovery remain open. The
> packaged launcher only starts the exact measured binary; see
> [If it fails](#if-it-fails).

The [reproduction guide](../../repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/README.md)
is the technical source of truth.

## Before you start

| Need | Tested with / required |
| --- | --- |
| OS | Linux. Distribution, kernel version and CPU architecture checks: not recorded for this package. No fresh-install test yet. |
| Driver stack | Intel GPU kernel driver, Level Zero runtime and Intel oneAPI at `/opt/intel/oneapi`. Versions: not recorded. Your user needs access to the card's render device (often through the `render` group). |
| Runtime / build | Native build from source: [`mndodd/llama.cpp`](https://github.com/mndodd/llama.cpp) at `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` plus six lab patches, applied and checked by `restore-and-build.sh`, built with `CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx` as the guide shows. **The launcher refuses any `llama-server` or `libggml-sycl.so` whose SHA-256 differs from the measured binary** (`35f2d2327f05…` / `0e7789313ac5…`). |
| Tools | `git`, `cmake`, `make`, a C compiler at `/usr/bin/cc`, `curl`, `python3`, `huggingface-cli`, `sha256sum`, `base64`, `gzip`, and a systemd user session (the launcher uses `systemd-run --user --scope`). Python version: not recorded. |
| Disk | Target `Qwen3.8-27B-Q8_0.gguf` 28.60 GB plus draft `mtp-Qwen3.8-27B-Q4_0.gguf` 1.37 GB. Source and build size: not recorded. |
| Host RAM | 16 GiB of RAM and 24 GiB of RAM plus swap (package manifest). The launcher caps the server at 13 GiB RAM and 12 GiB swap. `preflight.sh` does not check memory. |
| GPU | One B70 with no other model running. **Card 0 only:** `run-server.sh` fixes `ONEAPI_DEVICE_SELECTOR=level_zero:0` and has no card option. |
| Card memory | The run receipts do not record the card's ECC setting. With ECC on, a B70 shows about 28 GB instead of 32 GB, and this recipe was not tested that way. See [B70 ECC and usable VRAM](https://neural.download/learn/b70-ecc-and-vram.html). |

Background reading: [the MTP ladder](https://neural.download/learn/mtp-ladder.html)
(what the draft depth does), [speculative methods](https://neural.download/learn/speculative-methods.html)
and [runtimes](https://neural.download/learn/runtimes.html).

## Quick start

Clone this repository and run every command below from its root. Replace every
`/path/to/...` with your own absolute directories.

```bash
git clone https://github.com/steveseguin/b70-optimization-lab.git
cd b70-optimization-lab
```

### 1. Download and verify the model

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q8_0.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen38-q8

huggingface-cli download unsloth/Qwen3.8-27B-GGUF \
  MTP/mtp-Qwen3.8-27B-Q4_0.gguf \
  --revision 4ca720788d1e01f1bff70c033e0d0028fd02e502 \
  --local-dir /path/to/qwen38-draft

TARGET_DIR=/path/to/qwen38-q8 DRAFT_DIR=/path/to/qwen38-draft/MTP \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/verify-models.sh
```

The draft lands in an `MTP` folder; that folder is your `DRAFT_DIR`. The
verifier reads each file twice, once bypassing the page cache and once
normally, and both SHA-256 digests must match the pinned values. `preflight.sh`
runs the same check again before every launch.

### 2. Get the runtime

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2 \
CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/restore-and-build.sh

sha256sum /path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31/bin/llama-server \
  /path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31/bin/libggml-sycl.so
```

`SOURCE_DIR` must not exist yet. The script clones the base commit, checks and
applies every patch, and builds with two jobs (`BUILD_JOBS=N` to change). It
ends by printing `BUILD COMPLETE` and the build directory. Build time: not
recorded.

The `sha256sum` line shows whether your build is the measured one. The
launcher in step 3 only starts `llama-server`
`35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545` with
`libggml-sycl.so`
`0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154`.
Whether a fresh rebuild reproduces these bytes is not recorded.

### 3. Start the server

In terminal 1:

```bash
export TARGET_DIR=/path/to/qwen38-q8
export DRAFT_DIR=/path/to/qwen38-draft/MTP
export BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31

repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/preflight.sh
repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/run-server.sh
```

The server stays in the foreground on card 0. It listens on `127.0.0.1:18141`
with one slot, **1,024 tokens of context**, F16 target and draft KV, graph off,
MTP depth 2, prompt cache off and `--reasoning off`. `run-server.sh` runs
`preflight.sh` itself, so the binary and model hashes are checked again before
loading.

### 4. Wait until it is ready

In terminal 2:

```bash
until curl -fsS http://127.0.0.1:18141/health; do sleep 10; done
```

It answers once the model is loaded. Startup time: not recorded.

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18141/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-q8-q4mtp-tp1-mtp2","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

From Python, with any OpenAI-compatible client (`pip install openai`):

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18141/v1", api_key="unused").chat.completions.create(model="qwen38-q8-q4mtp-tp1-mtp2", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

Any other OpenAI-compatible app works the same way: base URL
`http://127.0.0.1:18141/v1`, model `qwen38-q8-q4mtp-tp1-mtp2`, any API key.
The server holds one model, so the name is only a label; it is the one the
packaged benchmark sends. The prompt, chat history and answer together must
fit in 1,024 tokens. The headline was measured with raw native completions,
not chat requests.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18141/health
pgrep -ax llama-server
```

There is no separate status script.

### 7. Stop

Press `Ctrl-C` once in terminal 1 and wait for the server to exit. Then
`pgrep -x llama-server` must print nothing.

## What you get

- **Speed:** **`37.062028 tok/s`** for one user, the median of two fresh
  servers (`36.848184`, `37.275873`) on the fixed twelve-prompt suite
  ([strict aggregate](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.json),
  [result note](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.md)).
  The configuration-matched MTP0 control measured `19.582597 tok/s`, so MTP2
  added 89.26%. MTP1 also passed at `30.260758 tok/s`, but MTP2 was faster.
- **Quality:** all 24/24 MTP2 output arrays matched the control exactly. Prompt
  caching, context checkpoints, response reuse, and learned drafting were
  disabled; every prompt reported cache zero and all objective canaries passed.
- **Context:** 1,024 configured tokens. That is the measured configuration.
  No 32K or longer-context value has been measured for this exact Q8+MTP2
  deployment; do not copy values from the target-only or Q4+MTP2 packages.
- **Many users:** not measured. The launcher has one slot.
- **Not measured yet:** Q8 plus MTP2 realistic-content HTTP speed and TTFT
  from 2K through 32K; Q8 plus MTP2 output-qualified concurrency; a tested
  clean-host Intel driver and oneAPI installation; a clean-host source build
  and endpoint replay; a beginner recovery flow.

## If it fails

- **`llama-server hash mismatch.`** or **`SYCL backend hash mismatch.`**:
  your build is not byte-identical to the measured binary, and `preflight.sh`
  (which `run-server.sh` runs first) refuses it. This package documents no
  other launch path for a different build.
- **`Missing Q8 target.`** or **`Missing Q4 MTP draft.`**: `TARGET_DIR` must
  contain `Qwen3.8-27B-Q8_0.gguf`, and `DRAFT_DIR` must be the `MTP` folder
  that contains `mtp-Qwen3.8-27B-Q4_0.gguf`.
- **`Missing built runtime.`**: `BUILD_DIR` must be the
  `build-sycl-aot-bmg-g31` directory with `bin/llama-server` and
  `bin/libggml-sycl.so`.
- **An error ending in `set TARGET_DIR`, `set DRAFT_DIR` or `set BUILD_DIR`**:
  export the three variables from step 3 in the same shell.
- **`IDENTITY MISMATCH on N file(s)`**: a model file is not the pinned file.
  Delete only the bad file, download it again, and re-run `verify-models.sh`.
  Never work around a checksum failure.
- **`CANNOT VERIFY: ...`** (exit code 2): the verifier could not read the file
  while bypassing the page cache, so it refuses to certify the bytes.
- **`Another llama-server is running.`**: stop the other server first. The
  launcher refuses while any `llama-server` runs, on any card.
- **`Refusing to overwrite existing path`** from `restore-and-build.sh`:
  `SOURCE_DIR` must be a new directory. Start over in a new one after a failed
  or edited build.
- **`Missing compiler: ...`** or **`Missing Intel oneAPI environment`**: the
  compiler named by `CXX_COMPILER` or `/opt/intel/oneapi/setvars.sh` is not
  installed.
- **`Decoded patch identity mismatch`**: a patch file in your checkout is not
  the pinned one. Stop and re-clone this repository.
- **The strict benchmark stops with `FAIL: repository must be clean`,
  `FAIL: campaign must run from main` or `FAIL: main must be pushed before execution`**:
  the benchmark runner only runs from a clean, pushed `main` checkout of this
  repository. It also stops on `FAIL: llama-server SHA-256 mismatch`,
  `FAIL: refusing to overwrite ...` for an existing `OUT_DIR`, and
  `FAIL: another model process is running`.

## Details

The patch list, re-run commands for the strict benchmark and all evidence are
in the reproduction guide:

- [Restore and build the exact source stack](../../repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/README.md#restore-and-build-the-exact-source-stack)
- [Re-run the strict benchmark](../../repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/README.md#re-run-the-strict-benchmark)
  (stop any server first; it starts its own)

Evidence: [strict aggregate](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.json).
