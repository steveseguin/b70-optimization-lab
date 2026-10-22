# Qwen3.8 27B Q4_K_M + MTP2 — one-B70 candidate package

Qwen3.8 27B Q4_K_M weights with a separate Q4_0 MTP draft at depth 2, on one
Intel Arc Pro B70, for one user. It runs a patched native llama.cpp SYCL build
that you compile from source; it is not a container. The draft guesses up to
two tokens ahead and the Q4_K_M target checks every guess.

**Strict headline: `42.636988 tok/s`.** Two fresh servers measured
`42.600910` and `42.673065` on the fixed twelve-prompt/six-class 512-cap
suite. Both attempts passed cache-zero and objective canary gates and matched
all 12 complete token arrays against each other and the same-build target-only
control. The control measured `27.375682 tok/s`, so MTP2 added **55.75%**.

> **Status: candidate.** The target, draft, patches, build, launch, strict
> suite and target-only control are pinned in this repository. A tested
> clean-host Intel driver and oneAPI installation, a clean-host build and
> endpoint replay, and a beginner recovery flow are still missing.

The [reproduction guide](../../repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md)
is the technical source of truth.

## Before you start

| Need | Tested with / required |
| --- | --- |
| OS | Linux on x86_64 (`preflight.sh` checks the architecture). Distribution and kernel version: not recorded. No fresh-install test yet. |
| Driver stack | Intel GPU kernel driver, Level Zero runtime and Intel oneAPI at `/opt/intel/oneapi` (`setvars.sh` must exist). Versions: not recorded. Your user needs access to the card's render device (often through the `render` group). |
| Runtime / build | Native build from source: [`mndodd/llama.cpp`](https://github.com/mndodd/llama.cpp) at `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` plus six lab patches, applied and checked by `restore-and-build.sh`. It defaults to the oneAPI 2026.0 compiler at `/opt/intel/oneapi/compiler/2026.0/bin/icpx`. |
| Tools | `git`, `cmake`, `make`, a C compiler at `/usr/bin/cc`, `curl`, `python3`, `huggingface-cli`, `sha256sum`, `base64`, `gzip`, and a systemd user session (the launcher uses `systemd-run --user --scope`). Python version: not recorded. |
| Disk | Target `Qwen3.8-27B-Q4_K_M.gguf` 18.97 GB plus draft `mtp-Qwen3.8-27B-Q4_0.gguf` 1.37 GB. Source and build size: not recorded. |
| Host RAM | At least 15 GiB of RAM and 24 GiB of RAM plus swap; `preflight.sh` refuses less. The tested small host had 16 GiB RAM plus swap. The launcher caps the server at 13 GiB RAM and 12 GiB swap. |
| GPU | One B70 with no other model running. Card 0 by default; `GPU_INDEX=N` picks another Level Zero card. |
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
  Qwen3.8-27B-Q4_K_M.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen38-target

huggingface-cli download unsloth/Qwen3.8-27B-GGUF \
  MTP/mtp-Qwen3.8-27B-Q4_0.gguf \
  --revision 4ca720788d1e01f1bff70c033e0d0028fd02e502 \
  --local-dir /path/to/qwen38-draft-root

TARGET_DIR=/path/to/qwen38-target DRAFT_DIR=/path/to/qwen38-draft-root/MTP \
  repro/qwen38-27b-q4km-mtp2-tp1-b70/verify-models.sh
```

The draft lands in an `MTP` folder; that folder is your `DRAFT_DIR`. The
verifier reads each file twice, once bypassing the page cache and once
normally, and both SHA-256 digests must match the pinned values. `preflight.sh`
runs the same check again before every launch.

### 2. Get the runtime

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-mtp2 \
  repro/qwen38-27b-q4km-mtp2-tp1-b70/restore-and-build.sh
```

`SOURCE_DIR` must not exist yet. The script clones the base commit, checks and
applies every patch, and builds with two jobs (`BUILD_JOBS=N` to change). It
ends by printing `BUILD COMPLETE` and the build directory,
`/path/to/new/llama.cpp-qwen38-mtp2/build-sycl-aot-bmg-g31`. Build time: not
recorded.

### 3. Start the server

In terminal 1:

```bash
export TARGET_DIR=/path/to/qwen38-target
export DRAFT_DIR=/path/to/qwen38-draft-root/MTP
export BUILD_DIR=/path/to/new/llama.cpp-qwen38-mtp2/build-sycl-aot-bmg-g31

repro/qwen38-27b-q4km-mtp2-tp1-b70/preflight.sh
repro/qwen38-27b-q4km-mtp2-tp1-b70/run-server.sh
```

The server stays in the foreground. It listens on `127.0.0.1:18139` with one
slot, 8,192 tokens of context, F16 KV, MTP depth 2, prompt caching off and
`--reasoning off`. `GPU_INDEX=N` selects another card. `run-server.sh` runs
`preflight.sh` itself, so the model files are hashed again before loading.

### 4. Wait until it is ready

In terminal 2:

```bash
until curl -fsS http://127.0.0.1:18139/health; do sleep 10; done
```

It answers once the model is loaded. Startup time: not recorded.

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18139/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-q4km-q4mtp-tp1-mtp2","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

From Python, with any OpenAI-compatible client (`pip install openai`):

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18139/v1", api_key="unused").chat.completions.create(model="qwen38-q4km-q4mtp-tp1-mtp2", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

Any other OpenAI-compatible app works the same way: base URL
`http://127.0.0.1:18139/v1`, model `qwen38-q4km-q4mtp-tp1-mtp2`, any API key.
The server holds one model, so the name is only a label; it is the one the
packaged benchmark sends. The headline was measured with raw `/completion`
requests, not chat requests.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18139/health
pgrep -ax llama-server
```

There is no separate status script. To measure the one-user speed against the
packaged oracle, run `OUT_DIR=/path/to/new-qwen38-mtp2-result repro/qwen38-27b-q4km-mtp2-tp1-b70/bench.sh`
from terminal 2.

### 7. Stop

Press `Ctrl-C` once in terminal 1 and wait for the server to exit. Then
`pgrep -x llama-server` must print nothing.

## What you get

- **Speed:** **`42.636988 tok/s`** for one user, the median of two fresh
  servers (`42.600910` / `42.673065`) on the fixed twelve-prompt/six-class
  suite with 512-token answers
  ([structured result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-strict-result.json),
  [result note](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-strict-result.md)).
  The same build without MTP measured `27.375682 tok/s`; MTP2 added 55.75%.
- **Quality:** both attempts were cache-zero, passed the objective canaries,
  and matched all 12 complete token arrays against each other and the
  target-only control. MTP2 is deliberate. MTP1 was slower (`38.320`), MTP3
  was slightly slower (`42.123`), and MTP5 changed all twelve target outputs
  and is rejected.
- **Context:** the launcher serves 8,192 tokens. A separate cache-zero
  exact-depth sweep used unrepeated technical prose, Python code, and
  structured documentation at 2K/4K/8K/16K/24K/32K. Each point is the median
  of two fresh-server class medians. The exact 32K result is
  `36.505065 tok/s` with `39.538 s` TTFT; all **36/36** MTP2 case outputs
  matched the fresh matched MTP0 oracle. This is Grade-B real-content
  context-shape evidence, not a natural retrieval/task suite. The older
  repeated-token diagnostic still diverged at 2K/token 23, so parity is not
  claimed universally. See the
  [structured mixed-content result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-result.json).
- **Many users:** the directly measured MTP2 HTTP service profile supports
  16 slots with 8K total context (512 nominal tokens per slot). Two fresh
  servers measured **68.341 aggregate tok/s at 16 concurrent users**; every
  throughput response returned 128 uncached token IDs and **256/256**
  separate concurrent exact-answer canaries passed. Multi-user greedy tokens
  remain batch-shape-dependent, so this is output-isolation-qualified rather
  than token-identical at every batch shape. The 32- and 64-slot profiles
  failed startup with device OOM and are not supported on one B70. See the
  [structured concurrency result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-r2-result.json).
- **Not measured yet:** a natural retrieval/task long-context HTTP suite
  beyond the measured raw-document continuation profile; a tested clean-host
  Intel driver and oneAPI installation; a clean-host source build and endpoint
  replay; a beginner recovery flow.

## If it fails

- **`PREFLIGHT FAIL: at least 15 GiB physical host RAM is required by the tested boundary`**
  or **`at least 24 GiB combined RAM plus swap is required`**: the host is
  below the memory this package was tested with.
- **`PREFLIGHT FAIL: another llama-server is running`** or
  **`Another llama-server is running`**: stop the other server first. The
  launcher refuses while any `llama-server` runs, on any card.
- **`PREFLIGHT FAIL: missing .../bin/llama-server`** or
  **`missing .../bin/libggml-sycl.so`**: `BUILD_DIR` must be the
  `build-sycl-aot-bmg-g31` directory that step 2 printed.
- **`PREFLIGHT FAIL: Intel oneAPI setvars.sh is missing`**: oneAPI is not
  installed at `/opt/intel/oneapi`.
- **`PREFLIGHT FAIL: tested only on x86_64 Linux`**: this package was not
  tested on other CPU architectures.
- **`IDENTITY MISMATCH on N file(s)`**: a model file is not the pinned file.
  Delete only the bad file, download it again, and re-run `verify-models.sh`.
  Never work around a checksum failure.
- **`CANNOT VERIFY: ...`** (exit code 2): the verifier could not read the file
  while bypassing the page cache, so it refuses to certify the bytes.
- **An error ending in `set TARGET_DIR`, `set DRAFT_DIR` or `set BUILD_DIR`**:
  export the three variables from step 3 in the same shell.
- **`Refusing to overwrite existing path`** from `restore-and-build.sh`:
  `SOURCE_DIR` must be a new directory. Start over in a new one after a failed
  or edited build.
- **`Missing compiler: /opt/intel/oneapi/compiler/2026.0/bin/icpx`** or
  **`Missing Intel oneAPI environment`**: the builder expects oneAPI 2026.0 at
  that path.
- **`Decoded patch identity mismatch`**: a patch file in your checkout is not
  the pinned one. Stop and re-clone this repository.
- **Device out of memory at startup** (`UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`):
  the lab saw this at 32 and 64 slots. Keep at most 16 slots and 8K total
  context.
- **`bench.sh` stops with `complete token arrays differ from the registered target-only oracle`**
  or another failed gate: the run is not a valid reproduction. A speed printed
  by a failed gate is not a result. `bench.sh` also refuses an `OUT_DIR` that
  already exists.

## Details

Patch list, measured binary hashes, the depth table and replay commands are in
the reproduction guide:

- [Source and patches](../../repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md#source-and-patches)
- [Why depth 2](../../repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md#why-depth-2)
- [Current boundary](../../repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md#current-boundary)
  (context sweep, concurrency profile and their replay commands)

This is a separate deployment from the no-MTP Q4_K_M package because it
requires the second 1.37 GB draft download.
