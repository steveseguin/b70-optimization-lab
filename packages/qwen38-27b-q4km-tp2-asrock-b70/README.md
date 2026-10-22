# Qwen3.8 27B Q4_K_M TP2 candidate packet

Qwen3.8 27B in 4-bit GGUF form (`Q4_K_M`) on **two Intel Arc Pro B70 (32 GiB)**
cards, served by a patched llama.cpp SYCL build. One user, no draft model,
F16 KV cache. The measured one-user result is `49.717503 tok/s` conventional
decode, `173.574 ms` TTFT, 12/12 exact output hashes, and cache zero on every
request.

> **Candidate, not a beginner install guide.** The immutable model, complete
> source patch stack, build recipe, preflight, launcher, benchmark, and oracle
> are present. Platform installation, an in-guide model downloader, and a
> clean-host replay remain open.

The [full reproduction guide](../../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md)
is the technical source of truth. This page is the short path.

## Before you start

| Need | Tested with / required |
| --- | --- |
| Cards | Two Intel Arc Pro B70 32 GiB, not used by anything else. The preflight checks that the first two render devices are B70s. The launcher selects them with `ONEAPI_DEVICE_SELECTOR=level_zero:1,0` (the reference host's order) and `--device SYCL0,SYCL1`, equal split `1,1`. Confirm your enumeration before changing the selector. |
| OS and kernel | x86-64 Ubuntu 24.04 (the preflight refuses anything else). Kernel version: not recorded for this package. |
| GPU driver stack | Intel GPU driver with Level Zero access to both cards; your user must be in the `render` group. Driver versions: not recorded. Driver installation is not covered here and has not been tested from a clean host. |
| Runtime | Native build, no container: [mndodd/llama.cpp](https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization) commit `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`, plus the [full lab TP2 patch](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md) and the [Q4_K increment](../../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md). Built with Intel oneAPI DPC++/C++ `2026.1.1.20260724` (Release, BMG-G31 AOT). The launcher sources `/opt/intel/oneapi/{tbb/2023.1,compiler/2026.1,mkl/2026.1,umf/1.0}/env/vars.sh`, and the preflight needs `/opt/intel/oneapi/setvars.sh`. |
| Python | `python3` for the model verifier and the benchmark. Version: not recorded. |
| Host RAM | The retained 2K–32K run's host reported 16,326,594,560 bytes (about 15.2 GiB) of RAM. The launcher runs the server in a systemd user scope capped at 8 GiB soft / 10 GiB hard memory and 8 GiB swap. Never build while a model is loaded on a 15–16 GiB host. |
| Disk | The model file is 18,973,870,432 bytes (about 19 GB). Build tree size: not recorded. |
| Network / oneCCL | Hugging Face access for the download. The launcher sets no oneCCL variables. |
| Other tools | `git`, `cmake`, `base64`, `gzip`, `sha256sum`, `curl`, `huggingface-cli`, and a systemd user session (the launcher uses `systemd-run --user`). |

## Quick start

Run every command from the repository root after
`git clone https://github.com/steveseguin/b70-optimization-lab && cd b70-optimization-lab`.
Replace every `/path/to/...` with your own absolute directories. Set the three
paths once in each terminal you use:

```bash
export QWEN38_SOURCE_DIR=/path/to/llama.cpp-qwen38-q4km-tp2
export QWEN38_BUILD_DIR=/path/to/llama.cpp-qwen38-q4km-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1
export QWEN38_MODEL=/path/to/qwen3.8-27b-q4km/Qwen3.8-27B-Q4_K_M.gguf
```

### 1. Download and verify the model

This package has no download helper yet. Download the one pinned file, then
check it with direct and ordinary reads (both SHA-256 values must match):

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q4_K_M.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen3.8-27b-q4km
repro/qwen38-27b-q4km-tp1-b70/verify-model-direct.sh /path/to/qwen3.8-27b-q4km
```

The expected SHA-256 is
`31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`.

### 2. Get the runtime

Restore the pinned source, apply the full TP2 stack, then the Q4_K increment.
Each decoded patch hash must match before you apply it:

```bash
git clone https://github.com/mndodd/llama.cpp.git "$QWEN38_SOURCE_DIR"
git -C "$QWEN38_SOURCE_DIR" checkout 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126

base64 -d patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64 \
  | gzip -dc > /tmp/qwen36-q8-tp2.patch
sha256sum /tmp/qwen36-q8-tp2.patch   # f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998
git -C "$QWEN38_SOURCE_DIR" apply --check /tmp/qwen36-q8-tp2.patch
git -C "$QWEN38_SOURCE_DIR" apply /tmp/qwen36-q8-tp2.patch

base64 -d patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64 \
  | gzip -dc > /tmp/qwen38-q4k-glu-tp2.patch
sha256sum /tmp/qwen38-q4k-glu-tp2.patch   # 0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6
git -C "$QWEN38_SOURCE_DIR" apply --check /tmp/qwen38-q4k-glu-tp2.patch
git -C "$QWEN38_SOURCE_DIR" apply /tmp/qwen38-q4k-glu-tp2.patch
git -C "$QWEN38_SOURCE_DIR" diff --check
```

Build with the full-stack packet's Release/BMG-G31 configuration. Keep `-j2`
and an 8 GiB hard memory limit on a 15–16 GiB host, and do not build while a
model is loaded:

```bash
source /opt/intel/oneapi/setvars.sh
cmake -G "Unix Makefiles" -S "$QWEN38_SOURCE_DIR" -B "$QWEN38_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/usr/bin/cc \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  -DBUILD_SHARED_LIBS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_CURL=OFF \
  -DGGML_SYCL=ON \
  -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg_g31 \
  -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_GRAPH=OFF \
  -DGGML_SYCL_DNN=OFF \
  -DGGML_SYCL_HOST_MEM_FALLBACK=OFF \
  -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON
systemd-run --user --scope -p MemoryHigh=6G -p MemoryMax=8G \
  cmake --build "$QWEN38_BUILD_DIR" --target llama-bench llama-cli llama-server -j2
```

### 3. Start the server

Run the preflight once. It checks the OS, both B70s, the `render` group, the
source markers, both patch hashes, the binary hashes and the model (read
twice). Then start the server in the same terminal. It stays in the
foreground; leave this terminal open.

```bash
repro/qwen38-27b-q4km-tp2-asrock-b70/preflight.sh
repro/qwen38-27b-q4km-tp2-asrock-b70/run-server.sh
```

A fresh build almost never has the evidence binary hashes, so the preflight
stops with `binary hashes differ from the evidence build`. Rerun it as
`QWEN38_ALLOW_REBUILT_BINARIES=1 repro/qwen38-27b-q4km-tp2-asrock-b70/preflight.sh`.
That marks your build as a new binary identity: run the benchmark below and
require its 12/12 exact output gate before you compare your speed with the
headline. The launcher checks the model SHA-256 again before loading.

### 4. Wait until it is ready

In a second terminal, wait for the health endpoint:

```bash
until curl -fsS http://127.0.0.1:18087/health; do sleep 5; done
```

It prints `{"status":"ok"}` when the model is loaded.

### 5. Send a first request

The launcher starts llama-server with `--reasoning off` and sets no model
alias. The lab's benchmark sends the model name `qwen38-q4km-tp2-asrock-b70`,
used here too:

```bash
curl -s http://127.0.0.1:18087/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-q4km-tp2-asrock-b70","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

With the OpenAI Python client (`pip install openai`):

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18087/v1", api_key="unused").chat.completions.create(model="qwen38-q4km-tp2-asrock-b70", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

To check speed and exactness against the published result, run the fixed
cold suite (it fails unless all 12 output hashes match and every request is
cache-zero):

```bash
OUT=/path/to/result.json repro/qwen38-27b-q4km-tp2-asrock-b70/bench.sh
```

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18087/health
pgrep -af llama-server
```

### 7. Stop

Press Ctrl-C once in the server terminal and wait. Then check that nothing is
left:

```bash
pgrep -af llama-server   # must print nothing
```

## What you get

- **One user:** `49.717503 tok/s` conventional decode, `173.574 ms` TTFT,
  12/12 exact output hashes, cache zero on every request
  ([result](../../experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json);
  LocalMaxxing
  [`cmsy530c70cpwms01bl1sjk6g`](https://www.localmaxxing.com/en/runs/cmsy530c70cpwms01bl1sjk6g)).
  Target-only TP2, F16 KV, graph off, reasoning off, no draft model.
- **Context:** the shipped launcher serves 8,192 tokens with one slot. A
  separate 33,024-token configuration measured exact 2K→32K inputs; at exactly
  32K it measured `44.437281 tok/s`
  ([summary](../../experiments/qwen38-27b-b70/data/qwen38-q4km-tp2-http-depth-20260825-r1-attempt1/summary.json)).
  That fixture is repeated-token shape evidence, not natural prose.
- **Many users:** separate 64- and 96-slot server configurations, not the
  shipped one-user launcher. The 1→64-user curve reached `165.387 tok/s`
  aggregate at 64 ([structured result](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-r2-result.json)).
  The default-off exact F16 `ffn_down,ffn_gate` cache measured
  `175.623794 tok/s` at 64 users and a qualified **`192.341954 tok/s`** center
  at 96 users. These prove output isolation and aggregate capacity, not
  batch-invariant text. See [Measured profiles](#measured-profiles) below.
- **Prompt reading:** an optional large-batch mode improved a short prefill
  probe by `20.68%` and cost `0.28%` decode. It is not the headline setting.
- **Not measured yet:** tested platform installation; self-contained model
  download helper; clean-host replay; beginner recovery flow; active-context
  prefill and power profiles plus a full memory curve.

## If it fails

- **`PREFLIGHT FAIL: tested host is Ubuntu 24.04`**, **`current user is not in
  the render group`**, **`two DRM render devices are required`** or
  **`render device is not an Intel Arc Pro B70`**: the host is outside what
  was tested. Fix the host; the preflight has no override for these.
- **`source tree lacks pinned base revision`**, **`full TP2 patch marker is
  absent`** or **`Q4_K TP2 increment marker is absent`**: restore from commit
  `4302fb5…` and apply both patches in order. The increment does not apply to
  the clean fork by itself; its context is the full TP2 stack.
- **`binary hashes differ from the evidence build`**: expected for your own
  build. Use `QWEN38_ALLOW_REBUILT_BINARIES=1` and then require the full
  12/12 benchmark gate before comparing speed.
- **Model verification fails, or the launcher prints `Model SHA-256
  mismatch`**: stop. Download the file again; never work around a hash
  failure. The verifier exits 1 for a mismatch or missing file and 2 when it
  cannot read past the page cache.
- **`Refusing to start a second llama.cpp model workload on this low-RAM
  host`** or **`another llama-server is already running`**: stop the existing
  `llama-server` first.
- **`Missing executable`** or **`Missing model`**: `QWEN38_BUILD_DIR` or
  `QWEN38_MODEL` is not set in that terminal, or points at the wrong place.
- **The build runs out of memory**: keep `-j2`, the 8 GiB limit, and no loaded
  model during the build.
- **The benchmark prints `output hashes differ from the promoted Qwen3.8
  target-only oracle`** or **`realistic fresh-response gate failed`**: that run
  is not a valid result. Check the binary and model identities first.
- Never set any `*_POISON` variable; those are deliberately invalid test
  controls.

## Measured profiles

The packet retains the complete lab TP2 patch plus the Q4_K dense gate/up
SwiGLU increment. Both are default-off source paths with explicit runtime
doors and exact output gates. The model is the same pinned Qwen3.8 Q4_K_M
artifact as the one-card packet; the two-card result remains its own topology
and metric identity. The optional large-batch prefill mode is measured
separately and must not be confused with the decode headline.

Additional measured profiles cover exact 2K→32K native HTTP decode/TTFT
and output-audited 1→96-user HTTP aggregate decode. At exactly 32K the package
measured `44.437281 tok/s`; at 64 simultaneous users it measured
`175.623794 tok/s` aggregate with the default-off exact F16
`ffn_down,ffn_gate` cache. The two candidate servers measured `175.798577`
and `175.449010 tok/s`, each
matching the preregistered fixed-cohort token oracle 64/64 with prompt caching
disabled. Same-binary cache-off controls centered at `160.981046 tok/s`
(`+9.10%`); the result is `+4.45%` above the prior one-family cache record.

The later near-capacity c96 profile measured `192.350949` and `192.332958
tok/s`, for a qualified **`192.341954 tok/s`** center. Both fresh servers
matched a frozen same-shape c96 control-batch oracle 96/96. The requested 32K
pool was rounded by llama.cpp to 49,152 tokens (96x512), and peak used VRAM was
about 30.48/30.35 GiB per card. The separate sequential comparison was 50/96,
so this is candidate-vs-control identity and aggregate-capacity evidence—not a
batch-invariant-text claim.

The aggregate optimization retains the incumbent dequantized F16 bytes on each
device; the pair adds approximately 13 GiB of device memory per card and did not improve the
single-user MMVQ route. The `49.717503 tok/s` one-user headline therefore stays
unchanged. See the [qualified c64 result](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-pair-c64-result.md) and the
[qualified c96 result](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c96-result.md), including patches,
preregistrations, hashes, memory samples, and strict runner. The launch
settings for these aggregate profiles are in the
[reproduction guide](../../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md#output-audited-http-concurrency-profile).
