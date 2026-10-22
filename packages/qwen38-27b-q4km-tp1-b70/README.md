# Qwen3.8 27B Q4_K_M — one-B70 candidate package

This is the user-facing front door for our validated one-card Qwen3.8 lane:
`27.825726 tok/s` class-balanced (`27.824790` all-prompt), target-only,
cache-zero, and exact against the registered
12-prompt oracle. The full semantic/repeat/needle battery also passed.
It runs a patched native llama.cpp SYCL build on one B70, not a container,
with no draft model or MTP.

> **Status: candidate, not a beginner install guide.** Model, source, patch,
> build, launch, and result identities are present. The Intel driver and
> oneAPI installation have not yet been rebuilt and tested from a clean OS.

The [reproduction guide](../../repro/qwen38-27b-q4km-tp1-b70/README.md) is the
technical source of truth. It includes every required repository patch and
its decoded SHA-256, rather than sending users to a detached recipe.

## Before you start

| Need | Tested with / required |
| --- | --- |
| OS | Ubuntu 24.04 on x86_64. `preflight.sh` refuses anything else. Kernel version: not recorded. A clean OS install has not been tested. |
| Driver stack | Intel GPU kernel driver plus Intel's client GPU compute packages (Level Zero, OpenCL, and `intel-ocloc` for the AOT build). Versions used: not recorded. The [clean-host runbook](../../repro/qwen38-27b-q4km-tp1-b70/CLEAN-HOST.md) links Intel's install pages and lists the packages. Your user must be in the `render` group, with read/write access to `/dev/dri/renderD*`. |
| Runtime/Build | Native build, no container. `restore-and-build.sh` clones [mndodd/llama.cpp](https://github.com/mndodd/llama.cpp) at `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`, applies six hash-checked lab patches and builds with the Intel oneAPI 2026.0 compiler from `/opt/intel/oneapi` (the measured identity). The script does not install oneAPI. |
| Tools | `git`, `cmake`, `make`, a C compiler at `/usr/bin/cc`, `base64`, `gzip`, `sha256sum`, `curl`, Python 3 (version not recorded), the Hugging Face CLI, and a systemd user session (`run-server.sh` uses `systemd-run --user --scope`). |
| Disk | 18,973,870,432 bytes (18.97 GB) for the model; the guide asks for at least 20 GB free for it. Source and build size: not recorded. |
| Host RAM | `preflight.sh` requires at least 64 GiB (`MemTotal`). That is conservative: the result was measured on one B70 of a four-B70, 125 GiB host, and a smaller host has not been validated. `run-server.sh` caps the server at `MemoryHigh=48G`, `MemoryMax=64G` and no swap. |
| GPU | One B70. `GPU_INDEX` (default 0) picks the card: the launcher sets `ONEAPI_DEVICE_SELECTOR=level_zero:N`. It refuses to start while any other `llama-server` runs. |
| Card memory | The run receipts do not record the card's ECC setting. With ECC on, a B70 shows about 28 GB instead of 32 GB, and this recipe was not tested that way. See [B70 ECC and usable VRAM](https://neural.download/learn/b70-ecc-and-vram.html). |

Background reading: [runtimes](https://neural.download/learn/runtimes.html),
[KV cache precision](https://neural.download/learn/kv-cache-precision.html) (why
this package keeps F16 KV) and [context length](https://neural.download/learn/context-length.html).

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
  --local-dir /path/to/qwen3.8-27b-q4km
repro/qwen38-27b-q4km-tp1-b70/verify-model-direct.sh /path/to/qwen3.8-27b-q4km
```

The verifier reads the file twice: once bypassing the page cache and once
normally. Both SHA-256 digests must equal
`31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`. On success
it prints `model revision and all recorded file identities verified`.

### 2. Get the runtime

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-tp1 \
  repro/qwen38-27b-q4km-tp1-b70/restore-and-build.sh
```

`SOURCE_DIR` must not exist yet. The script initializes the oneAPI environment,
verifies every decoded patch before applying it, disables the unused Web
UI/download path, and builds the server plus `llama-bench` and
`llama-batched-bench` with two jobs (`BUILD_JOBS=1` on a small host). It ends
with `BUILD COMPLETE` and the build directory. Build time: not recorded.
`CXX_COMPILER` may select another installed compiler only as a clearly separate
experimental identity; it does not reproduce the 2026.0.0 headline by
implication.

### 3. Start the server

In terminal 1 (the server stays in the foreground):

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q4km \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q4km-tp1-b70/preflight.sh

MODEL_DIR=/path/to/qwen3.8-27b-q4km \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-tp1/build-sycl-aot-bmg-g31 \
GPU_INDEX=0 \
  repro/qwen38-27b-q4km-tp1-b70/run-server.sh
```

Preflight changes nothing; it checks the OS, memory, render access, the build
and the model, then prints `PREFLIGHT PASS`. The server is the measured
one-user profile: one slot, 8,192 tokens of context, F16 KV, `--reasoning off`,
listening on `127.0.0.1:18088`.

### 4. Wait until it is ready

`run-server.sh` first hashes the 18.97 GB model again (direct and ordinary
reads), then loads it. The startup time is not recorded. In terminal 2:

```bash
until curl -fsS http://127.0.0.1:18088/health; do sleep 10; done
```

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18088/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-q4km-tp1-b70","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

From Python, after `pip install openai`:

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18088/v1", api_key="unused").chat.completions.create(model="qwen38-q4km-tp1-b70", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

Any other OpenAI-compatible app works the same way: base URL
`http://127.0.0.1:18088/v1`, model `qwen38-q4km-tp1-b70`, any API key. The
server holds one model, so the name is only a label; it is the one `bench.sh`
sends. The launcher starts with `--reasoning off`.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18088/health
pgrep -ax llama-server
```

To check speed and exact outputs against the registered oracle, run
`OUT=/path/to/qwen38-q4km-tp1-result.json repro/qwen38-27b-q4km-tp1-b70/bench.sh`
from terminal 2. Success prints `cached_tokens_all_zero=true`,
`output_hashes_exact=12/12` and `realistic_final_gate_passed=true`. Do not
compare or publish the speed unless those gates pass.

### 7. Stop

Press `Ctrl-C` once in terminal 1. Then `pgrep -x llama-server` must print
nothing.

## What you get

- **Speed:** **`27.825726 tok/s`** for one user: the median of per-input-class
  medians on the fixed cold 12-prompt suite, target-only, cache-zero
  ([capture J](../../experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-final-j.json),
  [capture I](../../experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-final-i.json)).
  `27.824790` is the all-prompt median. The separate pinned oneAPI 2026.1.1
  reconstruction measured `27.785930 tok/s` and `262.869 ms` median TTFT; it is
  a different compiler identity. Graphs are on the
  [details page](https://neural.download/models/qwen38-27b-q4km-tp1-b70.html).
- **Quality:** all outputs matched the registered oracle; the separate
  semantic battery passed every canary, 8/8 repeat stability and the
  long-context needle ([result](../../experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-quality-battery-result.md)).
- **Context:** the launcher serves 8,192 tokens. A separate one-slot
  exact-token HTTP sweep measured `24.4881 tok/s` and `50.267 s` TTFT at 32K
  ([table](#qualified-http-speed-and-ttft-measured-2026-08-25)); its prompt
  repeats registered tokens, so it is grade-C context-shape evidence, not 32K
  of natural prose.
- **Many users:** a separate output-audited native HTTP run measured
  `83.80 tok/s` combined at 64 users, `1.31 tok/s` each
  ([table](#multiple-users-measured-http-capacity-output-varies-by-batch-shape)).
  Multi-user token choices vary with batch shape, so this is service capacity,
  not deterministic serving. The shipped launcher stays one slot.
- **Not measured yet:** tested clean-host Intel driver and oneAPI
  installation; clean-host source build and endpoint replay;
  batch-shape-invariant greedy output for multi-user serving.

## If it fails

The scripts stop on the first problem and print one of these messages. Fix one
layer at a time.

- **`PREFLIGHT FAIL: tested host is Ubuntu 24.04; found ...`** or
  **`this candidate was tested only on x86_64`**: the candidate is limited to
  the tested OS boundary. Other systems are untested.
- **`PREFLIGHT FAIL: candidate preflight conservatively requires 64 GiB host RAM`**:
  preflight reads `MemTotal` from `/proc/meminfo`. The limit stays until a
  smaller clean host is validated.
- **`Intel oneAPI setvars.sh is missing`**, **`Missing Intel oneAPI environment`**
  or **`Missing compiler: ...`**: confirm that `/opt/intel/oneapi/setvars.sh`
  exists, then start a new shell and run
  `source /opt/intel/oneapi/setvars.sh --force`. Check `command -v icpx` and
  `icpx --version` before rebuilding. Do not mix objects from two compiler
  versions; use a new `SOURCE_DIR` for an override.
- **`current user is not in the render group`**, **`one DRM render device is required`**,
  **`render device is not readable/writable`**, or no SYCL GPU appears: run
  `sycl-ls`, `ls -l /dev/dri`, `id`, and `xpu-smi discovery`. The user must
  have access to the render device (often via the `render` group). Log out and
  back in after a group change. Do not work around permissions with
  world-writable device nodes.
- **`IDENTITY MISMATCH`** (verifier exit code 1) or **`CANNOT VERIFY`** (exit
  code 2, the file could not be read while bypassing the page cache): stop.
  Re-run `verify-model-direct.sh /path/to/qwen3.8-27b-q4km`. A cached read is
  not enough: both direct and ordinary SHA-256 checks must equal the identity
  in `model-direct.json`. Delete and download only the bad file; never patch
  around a checksum failure.
- **`Refusing to overwrite existing path`**, the build tries to download a Web
  UI, or it runs out of memory: use only `restore-and-build.sh`, which disables
  those unused paths and defaults to two jobs. Start from a new source
  directory after a failed or manually modified build. Use `BUILD_JOBS=1` on a
  small host.
- **`Decoded patch identity mismatch`**: a patch file in your checkout does not
  match its recorded SHA-256. Use an unmodified clone of this repository.
- **`another llama-server is already running`** or
  **`Refusing to start while another llama-server is running`**: stop the other
  server first; this launcher runs one model at a time.
- **The server cannot allocate the model or KV cache**: ensure no other model
  process is active with `pgrep -af 'llama-(server|bench)|vllm'`. Start with
  the supplied one-slot 8K launcher. Do not copy the research 64-slot flags;
  that profile nearly filled the card and failed output-stability gates.
- **`bench.sh` stops with `fresh, cache-zero benchmark gate failed` or
  `output hashes differ from the registered TP1 oracle`**: preserve the JSON
  and server log. A nonzero cache count, stale response, or output-hash
  mismatch invalidates the speed. Stop the server, verify the exact
  binary/model identities, and repeat once from a fresh process; do not
  average a failed attempt into a passing one.

For a useful issue report, attach the preflight output, `icpx --version`,
`sycl-ls`, `xpu-smi discovery`, the exact failing command, the server log,
and the benchmark JSON. Remove usernames and unrelated environment secrets.
For an actual fresh installation, follow the fail-closed
[clean-host certification runbook](../../repro/qwen38-27b-q4km-tp1-b70/CLEAN-HOST.md).

## Details

### Context length and KV-cache dtype (measured 2026-08-22)

A single-card `llama-bench` sweep (raw-engine tg128/pp2048, flash-attn on,
5 reps; different metric from the `27.82` headline) maps how this lane behaves
as context grows and whether to use an 8-bit KV cache:

| context | decode KV f16 | decode KV q8_0 | prefill KV f16 |
| ---: | ---: | ---: | ---: |
| 0 | 24.81 | 24.27 | 825 |
| 8K | 23.83 | 18.68 | 851 |
| 16K | 23.10 | 14.86 | 780 |
| 32K | 21.77 | **10.66** | 668 |

**Keep the KV cache at f16 for speed.** Decode with f16 KV stays nearly flat
out to 32K (−12%), but the q8_0-KV decode penalty grows with context (~2% at
0 → **−51% at 32K**) because per-token KV dequant scales with cached length.
Prefill is unaffected by KV dtype (<1.5%). Use q8_0 KV only to fit longer
context into 32 GiB. Full data:
[sweep JSON](../../experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.json),
[chart](../../experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.svg).

### Qualified HTTP speed and TTFT (measured 2026-08-25)

The pinned oneAPI 2026.1.1 reconstruction also passed the package's cold,
cache-zero 12-prompt HTTP suite: 12/12 registered outputs, **27.785930 tok/s**
median conventional 99-interval decode, and **262.869 ms** median TTFT.

A separate exact-token HTTP sweep used a one-slot, 33,024-token F16-KV
service. Every row passed exact prompt accounting, zero cache reuse, no
truncation/context shift, and 128 returned token IDs:

| active prompt | decode | TTFT |
| ---: | ---: | ---: |
| 2K | 27.2616 tok/s | 2.775 s |
| 8K | 26.8651 tok/s | 11.343 s |
| 16K | 25.9976 tok/s | 23.473 s |
| 24K | 25.2353 tok/s | 36.440 s |
| 32K | **24.4881 tok/s** | **50.267 s** |

The exact-depth prompt deliberately repeats registered tokens, so this is a
grade-C context-shape measurement—not a claim about 32K of natural prose.
Nothing between the displayed markers is inferred. See the
[result note](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-http-depth-r1-result.md)
and [compact evidence](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-depth-r1-result.json).

### Multiple users: measured HTTP capacity, output varies by batch shape

A separate oneAPI 2026.1.1 reconstruction audit loaded this model on one B70
with 64 HTTP server slots and 32K total F16 KV context (`512` nominal tokens
per slot). It completed all 318 requests; every request returned the full 128
tokens with `cached_tokens=0`. Peak observed GPU memory was
`32281.7 / 32656 MiB`, leaving very little safety margin.

That audit is **not a validated concurrency-speed curve**. Greedy outputs were
shape-dependent (only `23/64` matched their sequential oracle at each 64-way
repeat), and the second pass showed large 2–32-user order/state hysteresis.
The observed 64-way diagnostics (`86.28` and `85.97 tok/s`) remain evidence,
not a package headline or user guarantee. See the
[result note](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-result.md)
and [structured closeout](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-summary.json).
That first pass was replaced by an output-audited native HTTP run. Two fresh,
cache-off server attempts agreed within 2.03% at every point:

| users | aggregate decode | per user |
| ---: | ---: | ---: |
| 1 | 24.64 tok/s | 24.64 tok/s |
| 4 | 49.32 tok/s | 12.33 tok/s |
| 8 | 56.12 tok/s | 7.01 tok/s |
| 16 | 54.97 tok/s | 3.44 tok/s |
| 32 | 65.80 tok/s | 2.06 tok/s |
| 64 | **83.80 tok/s** | 1.31 tok/s |

Every request returned 128 raw token IDs; prompt caching and slot similarity
were disabled; no output matched an oracle from a different base task.
However, exact sequential greedy identity held in both attempts only at one
user. Multi-user token choices vary with batch shape. This is an honest HTTP
capacity curve, not a deterministic-serving promise. See the
[r3 result](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-http-concurrency-r3-result.md).

### Who built what

- **neural.download lab — integrated:** Qwen3.8 Q4_K_M bring-up, the complete
  lab kernel stack, TP1 fusion increments, packaging, and validation. The
  matched TP1 ladder moved `26.047863/26.068073` to
  `27.813629/27.824790 tok/s` (`+6.8%` to `+7.0%`) with 24/24 oracle-exact
  outputs and the full quality battery passing. See the
  [TP1 patch evidence](../../patches/qwen38-27b-q4km-tp1-b70s/README.md).
- **[mndodd](https://github.com/mndodd) — integrated:** optimized Intel SYCL
  llama.cpp fork used as the pinned runtime base beneath our Qwen3.8 patches.
  Its separately matched Qwen3.6 Q8 TP2 control measured `31.338765` versus
  `29.610651 tok/s` (`+5.836%`). That exact contribution is credited here;
  the later Qwen3.8 package result remains our separately measured lane. See
  the [lab validation](../../community/mndodd-qwen36-27b-llamacpp-sycl/STATUS.md).
