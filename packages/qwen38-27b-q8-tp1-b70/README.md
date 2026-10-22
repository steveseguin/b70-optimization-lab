# Qwen3.8 27B Q8_0 — one-B70 candidate package

This is the quality-conservative one-card Qwen3.8 option: Q8_0 weights, F16
KV, target-only decoding, and no speculative helper. It runs a patched native
llama.cpp SYCL build on one B70, not a container.

> **Strict package headline: `19.619240 tok/s`.** This is the median of two
> fresh-server class-balanced medians from the complete twelve-prompt,
> six-class, 512-cap raw HTTP suite. Both attempts were cache-zero, passed the
> objective canaries, and matched 12/12 complete TP1 token arrays.

> **Status: candidate; strict headline qualified.** The model, source patches, build, launch, depth
> benchmark, quality checks, and output-audited HTTP concurrency are closed in
> this repository. A clean Ubuntu host installation/replay, beginner recovery
> path, and realistic-prompt HTTP TTFT/depth remain open.

The [complete reproduction guide](../../repro/qwen38-27b-q8-tp1-b70/README.md)
is the technical source of truth. It includes the pinned download, direct-read
verification, specific patch links and decoded hashes, relative build entry
point, launch command, quality battery, and exact context sweep.

## Before you start

| Need | Tested with / required |
| --- | --- |
| OS | Ubuntu 24.04 on x86_64. `preflight.sh` refuses anything else. Kernel version: not recorded. A clean OS install has not been tested. |
| Driver stack | Intel GPU kernel driver and Intel's GPU compute runtime (Level Zero), plus Intel oneAPI at `/opt/intel/oneapi`. Versions used: not recorded. Intel's install pages: [client GPU packages](https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html) and [oneAPI APT installation](https://www.intel.com/content/www/us/en/docs/oneapi-toolkit/installation-guide-linux/latest/install-oneapi-toolkit-with-apt.html). Your user must be in the `render` group, with read/write access to `/dev/dri/renderD*`. |
| Runtime/Build | Native build, no container. `restore-and-build.sh` hands off to the shared, hash-verifying Qwen3.8 TP1 builder: [mndodd/llama.cpp](https://github.com/mndodd/llama.cpp) at `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` plus six lab patches. Tested compiler identity: Intel oneAPI 2026.1.1, selected with `CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx`. The script does not install oneAPI. |
| Tools | `git`, `cmake`, `make`, a C compiler at `/usr/bin/cc`, `base64`, `gzip`, `sha256sum`, `curl`, Python 3 (version not recorded), the Hugging Face CLI, and a systemd user session (`run-server.sh` uses `systemd-run --user --scope`). The optional quality battery also needs `transformers==5.10.2` in a virtual environment. |
| Disk | 28,595,763,552 bytes (28.60 GB) for the model. Source and build size: not recorded. |
| Host RAM | `preflight.sh` requires at least 15 GiB of RAM (`MemTotal`) and at least 30 GiB of RAM plus swap; the package manifest lists 16 GiB and 32 GiB. The tested small host had 16 GB nominal RAM plus swap. `run-server.sh` caps the server at `MemoryHigh=11G`, `MemoryMax=13G` and 12 GiB of swap. A 32 GB or larger host is simpler. Model weights reside primarily in B70 VRAM. |
| GPU | One B70. `GPU_INDEX` (default 0) picks the card: the launcher sets `ONEAPI_DEVICE_SELECTOR=level_zero:N`. It refuses to start while any other `llama-server` runs. |
| Card memory | The run receipts do not record the card's ECC setting. With ECC on, a B70 shows about 28 GB instead of 32 GB, and this recipe was not tested that way. See [B70 ECC and usable VRAM](https://neural.download/learn/b70-ecc-and-vram.html). |

Background reading: [runtimes](https://neural.download/learn/runtimes.html),
[quantization and speed](https://neural.download/learn/quantization-and-speed.html),
[context length](https://neural.download/learn/context-length.html) and
[one card, many people at once](https://neural.download/learn/multi-user.html).

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
  --local-dir /path/to/qwen3.8-27b-q8
repro/qwen38-27b-q8-tp1-b70/verify-model-direct.sh /path/to/qwen3.8-27b-q8
```

The verifier reads the 28.60 GB file twice: once bypassing the page cache and
once normally. Both SHA-256 digests must equal
`f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`. On success
it prints `model revision and all recorded file identities verified`.

### 2. Get the runtime

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1 \
CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  repro/qwen38-27b-q8-tp1-b70/restore-and-build.sh
```

`SOURCE_DIR` must not exist yet. The builder initializes oneAPI, decodes,
hashes and applies the six patches in order, and builds `llama-server`,
`llama-bench` and `llama-batched-bench` with two jobs (`BUILD_JOBS=1` on a
small host). It ends with `BUILD COMPLETE` and the build directory. Build
time: not recorded.

### 3. Start the server

In terminal 1 (the server stays in the foreground):

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-tp1-b70/preflight.sh

MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
GPU_INDEX=0 repro/qwen38-27b-q8-tp1-b70/run-server.sh
```

Preflight changes nothing; it checks the OS, memory, render access, the build
and the model, then prints `PREFLIGHT PASS`. This is the one-user profile: one
slot, 8,192 tokens of context, F16 KV, `--reasoning off`, listening on
`127.0.0.1:18088`. For many users at once, start
`repro/qwen38-27b-q8-tp1-b70/run-throughput-server.sh` with the same three
variables instead: eight active slots and 4,096 total context tokens, with
further requests waiting in the server queue.

### 4. Wait until it is ready

`run-server.sh` first hashes the 28.60 GB model again (direct and ordinary
reads), then loads it. The startup time is not recorded. In terminal 2:

```bash
until curl -fsS http://127.0.0.1:18088/health; do sleep 10; done
```

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18088/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-q8-tp1-b70","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

From Python, after `pip install openai`:

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18088/v1", api_key="unused").chat.completions.create(model="qwen38-q8-tp1-b70", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

Any other OpenAI-compatible app works the same way: base URL
`http://127.0.0.1:18088/v1`, model `qwen38-q8-tp1-b70`, any API key. The server
holds one model, so the name is only a label; it is the one the package's
`quality.sh` sends. The launcher starts with `--reasoning off`.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18088/health
pgrep -ax llama-server
```

There is no separate status script. The promotion gate is the guide's
`quality.sh` (it needs the pinned tokenizer files; see the
[guide](../../repro/qwen38-27b-q8-tp1-b70/README.md#launch-and-quality-validation)).
Success prints `service_quality_passed=true` and `cached_tokens_all_zero=true`.

### 7. Stop

Press `Ctrl-C` once in terminal 1. Then `pgrep -x llama-server` must print
nothing.

## What you get

- **Speed:** **`19.619240 tok/s`** for one user, the strict package headline
  above ([receipt](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-tp1-strict-reasoningoff-native-r1-result.json),
  [strict result note](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp1-strict-reasoningoff-native-r1-result.md)).
  Graphs are on the
  [details page](https://neural.download/models/qwen38-27b-q8-tp1-b70.html).
- **Quality:** the matching OpenAI-compatible service separately passed 7/7
  semantic canaries, 8/8 repeat stability, a 7,617-token needle, and explicit
  zero cached tokens on all 16 requests
  ([quality qualification](../../experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-service-quality-20260825-r1/qualification.json)).
- **Context:** the launcher serves 8,192 tokens. The exact raw-engine tg128
  curve measured `19.662501 tok/s` at depth zero and `18.023689 tok/s` at 32K;
  prefill pp2048 measured `996.891020` and `719.144647 tok/s` at those same
  depths ([table](#measured-context-behavior)). Every displayed marker is a
  five-repetition measurement. These are direct `llama-bench` rates, not HTTP
  or realistic-prompt speed; `repro/qwen38-27b-q8-tp1-b70/bench-depth.sh`
  reproduces them when no server is running.
- **Many users:** `run-throughput-server.sh` measured **`68.556`** tok/s
  combined at 64 simultaneous HTTP requests, `1.071` per user
  ([table](#measured-queued-http-throughput)). Greedy output is
  batch-shape-dependent; this is aggregate batch wall throughput, not queued
  TTFT or per-request latency.
- **Not measured yet:** tested clean-host Intel driver and oneAPI
  installation; clean-host source build and endpoint replay; beginner recovery
  flow; realistic-prompt HTTP speed and TTFT context sweep beyond the qualified
  short-context headline; queued TTFT and per-request latency profile.

## If it fails

The scripts stop on the first problem and print one of these messages. This
list is not the beginner recovery flow, which is still missing.

- **`PREFLIGHT FAIL: tested host is Ubuntu 24.04; found ...`** or
  **`this candidate was tested only on x86_64`**: the candidate is limited to
  the tested OS boundary. Other systems are untested.
- **`candidate requires at least 15 GiB usable host RAM (16 GB nominal)`** or
  **`candidate requires at least 30 GiB combined RAM and swap`**: preflight
  reads `MemTotal` and `SwapTotal` from `/proc/meminfo`.
- **`Intel oneAPI setvars.sh is missing`**, **`Missing Intel oneAPI environment`**
  or **`Missing compiler: ...`**: oneAPI is not installed where the scripts
  look (`/opt/intel/oneapi`), or the 2026.1 compiler path given in
  `CXX_COMPILER` does not exist.
- **`current user is not in the render group`**, **`one DRM render device is required`**
  or **`render device is not readable/writable`**: give your user access to the
  card's render device, then log in again.
- **`llama-server or llama-bench is missing`** or **`libggml-sycl.so is missing`**:
  `BUILD_DIR` must be the `build-sycl-aot-bmg-g31` directory that step 2
  printed.
- **`IDENTITY MISMATCH`** (verifier exit code 1) or **`CANNOT VERIFY`** (exit
  code 2, the file could not be read while bypassing the page cache): the bytes
  are not certified. Delete the bad file, download it again and re-run the
  verifier.
- **`Refusing to overwrite existing path`** or **`Decoded patch identity mismatch`**
  (build): use a new `SOURCE_DIR`, and an unmodified clone of this repository.
- **`another llama-server is already running`** or
  **`Another llama-server is running.`**: stop the other server first; this
  launcher runs one model at a time.
- **Startup fails with a device allocation error after raising slots or
  context**: the guide records that the p64/32K and p32/16K F16-KV profiles
  failed device allocation on one B70. Use the two supplied launchers as they
  are.
- **`quality.sh` prints `tokenizer.json identity mismatch`** (or the same for
  `tokenizer_config.json` / `config.json`): download the exact tokenizer
  revision the guide names.
- **The strict attempt runner stops with `llama-server SHA-256 mismatch` or
  `SYCL backend SHA-256 mismatch`**: it accepts only the lab's accepted
  binaries. A new build with different hashes cannot reuse that script as is.

## Details

### Measured context behavior

| existing context | raw tg128 | raw pp2048 |
| ---: | ---: | ---: |
| 0 | 19.662501 | 996.891020 |
| 8K | 19.293993 | 914.062353 |
| 16K | 18.838870 | 837.512717 |
| 32K | 18.023689 | 719.144647 |

Decode declines only 8.3% from 0 to 32K with F16 KV; prefill declines 27.9%.
Those are measured endpoint comparisons, not an interpolated curve. See the
[full evidence](../../experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json)
and [quality qualification](../../experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-service-quality-20260825-r1/qualification.json).

### Measured queued HTTP throughput

The qualified throughput profile keeps **eight active inference slots** and
4,096 total F16-KV context tokens while the server queues incoming requests
above eight. This avoids the measured p16 batch-shape collapse without
pretending that 64 full GPU slots fit.

| simultaneous HTTP requests | aggregate tok/s | batch-wall tok/s per user |
| ---: | ---: | ---: |
| 1 | 18.071 | 18.071 |
| 2 | 29.148 | 14.574 |
| 4 | 47.518 | 11.879 |
| 8 | 67.073 | 8.384 |
| 16 | 68.128 | 4.258 |
| 32 | 68.311 | 2.135 |
| 64 | **68.556** | 1.071 |

Every marker is the median of two preregistered fresh-server attempts; the
worst relative range was 0.96%. All responses returned 128 raw token IDs,
cached-token counts stayed zero, and no response collided with another base
task's oracle. Greedy output is batch-shape-dependent. This is aggregate batch
wall throughput, not queued TTFT or per-request latency, and no point is
interpolated or extrapolated. The exact p64/32K and p32/16K profiles failed
device allocation. P16/8K fits, but measured only 43.603 tok/s at 16 users;
queued p8 improves that point by 56.24%.

Evidence: [qualified aggregate](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp1-http-p8-queue-concurrency-r5-result.json)
and [fit/optimization note](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q8-tp1-http-p16-qualified-and-p8-queue-prereg.md).

### Strict headline and TP2 comparison

The [guide](../../repro/qwen38-27b-q8-tp1-b70/README.md#launch-and-quality-validation)
has the create-only two-attempt commands and the comparator for the strict
headline.

TP1 is exact 12/12 across its two fresh servers but differs from the TP2 raw
oracle 12/12, with first divergences at generated tokens 59-444. It is a
separately quality-gated arithmetic identity, not a cross-card-count byte-
equivalence claim. See the [strict result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp1-strict-reasoningoff-native-r1-result.md).
