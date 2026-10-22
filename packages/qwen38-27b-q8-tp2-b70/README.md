# Qwen3.8 27B Q8_0 — two-B70 candidate package

This is the quality-conservative Qwen3.8 service package: Q8_0 target weights,
F16 KV, two B70s, no draft model, and no speculative decoding. It runs a
patched native llama.cpp SYCL build, not a container. The accepted strict
packaged result is **`36.726447 tok/s`**, the median of two fresh-server
class-balanced medians. Both full twelve-prompt/six-class attempts passed the
512-token workload, cache-zero, objective-canary, and 12/12 complete-token-
array equality gates.

> **Status: expert candidate; strict headline qualified.** The model and patch
> identities, source build, service launcher, benchmark, and semantic gates are
> documented. A tested platform installer, clean-host replay, and beginner
> recovery flow are still missing.

The [reproduction guide](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
is the technical source of truth.

## Before you start

| Need | Tested with / required |
| --- | --- |
| Cards | Two Intel Arc Pro B70 32 GiB cards (ASRock in the lab) with no other GPU work. The launcher's reference selector is `ONEAPI_DEVICE_SELECTOR=level_zero:1,0`, addressed by the server as `SYCL0,SYCL1`. Confirm the enumeration on your host; other selectors are untested. |
| OS and kernel | Linux. Distribution and kernel version: not recorded for this package. |
| GPU driver stack | Intel GPU kernel driver and Level Zero runtime; versions not recorded. The launcher pins the Unified Runtime Level Zero v2 adapter (`SYCL_UR_USE_LEVEL_ZERO_V2=1`). |
| Runtime | Native build, no container: [mndodd/llama.cpp](https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization) at `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` plus the three lab patches in the [patch packet](../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md), built with Intel oneAPI 2026.1.1 (the validated runtime). The launcher sources `/opt/intel/oneapi/compiler/2026.1`, `mkl/2026.1`, `tbb/2023.1` and `umf/1.0`, so those directories must exist. |
| Python | Python 3 for the verifier and benchmark scripts; version not recorded. |
| Host RAM | Minimum not recorded. The launcher runs the server in a systemd scope with `MemoryHigh=8G` / `MemoryMax=10G` (many-users profile: `11G` / `13G`). The lab builds with `-j2` inside a 6/8 GiB limit and never at the same time as a model on a 16 GiB-class host. |
| Disk | `Qwen3.8-27B-Q8_0.gguf` is 28,595,763,552 bytes (28.6 GB). Source and build size: not recorded. |
| Network / oneCCL | No oneCCL. The two cards exchange data through the patched SYCL backend. The server listens on loopback only (`127.0.0.1:18088`). |
| Other tools | `git`, `cmake`, `curl`, `sha256sum`, `base64`, `gzip`, and a systemd user session (the launcher uses `systemd-run --user --scope`). |

This package does not install or test GPU drivers or oneAPI; a tested platform
installation is still missing.

## Quick start

Run every command from the repository root after
`git clone https://github.com/steveseguin/b70-optimization-lab && cd b70-optimization-lab`.
Replace every `/path/to/...` with your own absolute directories.

### 1. Download and verify the model

```bash
mkdir -p /path/to/qwen3.8-27b-q8
curl -fL -o /path/to/qwen3.8-27b-q8/Qwen3.8-27B-Q8_0.gguf \
  https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF/resolve/0669b98607d47046c7c2b3f801011d54a08cfccf/Qwen3.8-27B-Q8_0.gguf
repro/qwen38-27b-q8-tp2-asrock-b70/verify-model-direct.sh /path/to/qwen3.8-27b-q8
```

The verifier reads the file twice, once bypassing the page cache and once
normally. Both SHA-256 digests must equal
`f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
(28,595,763,552 bytes).

### 2. Get the runtime

Check the lab patch files, restore the base source, and apply the three
patches (the [patch packet](../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md)
explains each one):

```bash
repro/qwen38-27b-q8-tp2-asrock-b70/verify-artifacts.sh
git clone https://github.com/mndodd/llama.cpp.git /path/to/llama.cpp-qwen38-q8-tp2
git -C /path/to/llama.cpp-qwen38-q8-tp2 checkout 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126
base64 -d patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64 \
  | gzip -dc > /path/to/qwen38-q8-tp2.patch
sha256sum /path/to/qwen38-q8-tp2.patch   # must print f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998
git -C /path/to/llama.cpp-qwen38-q8-tp2 apply --check /path/to/qwen38-q8-tp2.patch
git -C /path/to/llama.cpp-qwen38-q8-tp2 apply /path/to/qwen38-q8-tp2.patch
git -C /path/to/llama.cpp-qwen38-q8-tp2 apply "$PWD/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff"
git -C /path/to/llama.cpp-qwen38-q8-tp2 apply "$PWD/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg24-20260817.diff"
git -C /path/to/llama.cpp-qwen38-q8-tp2 diff --check
```

`verify-artifacts.sh` prints one success line when all three patch hashes and
the recorded quality gates match. Then build a Release BMG-G31 AOT binary with
the recorded flags (the lab's complete original configure line is not
recorded; see [Build](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md#build)):

```bash
for c in tbb/2023.1 compiler/2026.1 mkl/2026.1 umf/1.0; do source /opt/intel/oneapi/$c/env/vars.sh; done
cmake -S /path/to/llama.cpp-qwen38-q8-tp2 -B /path/to/llama.cpp-qwen38-q8-tp2/build-sycl-aot-bmg-g31 \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=icpx \
  -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL -DGGML_SYCL_DEVICE_ARCH=bmg_g31 -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_GRAPH=OFF -DGGML_SYCL_DNN=OFF -DGGML_SYCL_HOST_MEM_FALLBACK=OFF \
  -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON
systemd-run --user --scope -p MemoryHigh=6G -p MemoryMax=8G \
  cmake --build /path/to/llama.cpp-qwen38-q8-tp2/build-sycl-aot-bmg-g31 \
  --target llama-bench llama-cli llama-server -j2
```

### 3. Start the server

In terminal 1 (the server stays in the foreground):

```bash
QWEN38_SOURCE_DIR=/path/to/llama.cpp-qwen38-q8-tp2 \
QWEN38_BUILD_DIR=/path/to/llama.cpp-qwen38-q8-tp2/build-sycl-aot-bmg-g31 \
QWEN38_MODEL=/path/to/qwen3.8-27b-q8/Qwen3.8-27B-Q8_0.gguf \
  repro/qwen38-27b-q8-tp2-asrock-b70/run-server.sh
```

This is the one-user profile: one slot, 8,192 tokens of context, F16 KV,
`--reasoning off`, port 18088. For many users at once, run
`repro/qwen38-27b-q8-tp2-asrock-b70/run-throughput-server.sh` with the same
three variables instead (64 slots, 32,768 total context tokens).

### 4. Wait until it is ready

The launcher first hashes the 28.6 GB model file, then loads both cards. The
startup time is not recorded. In terminal 2:

```bash
until curl -fsS http://127.0.0.1:18088/health; do sleep 10; done
```

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18088/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-q8-tp2-asrock-b70","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

From Python, with any OpenAI-compatible client (`pip install openai`):

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18088/v1", api_key="unused").chat.completions.create(model="qwen38-q8-tp2-asrock-b70", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

The server holds one model, so the name is only a label; it is the one the
packaged benchmark sends. The launcher starts with `--reasoning off`. The
package [launch smoke](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp2-package-throughput-launch-smoke.json)
sent one real chat completion through the many-users launcher and got an
answer with no reasoning content.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18088/health
pgrep -ax llama-server
```

There is no separate status script. To measure the one-user speed against the
packaged oracle, run `OUT=/path/to/result.json repro/qwen38-27b-q8-tp2-asrock-b70/bench.sh`.

### 7. Stop

Press `Ctrl-C` **once** in terminal 1 and wait for cleanup to finish. Then
`pgrep -x llama-server` must print nothing. Do not signal both the systemd
scope and its child, and do not wrap the launcher in another timeout that
sends a second interrupt.

## What you get

- **One user:** **`36.726447 tok/s`** strict packaged result, the median of
  two fresh-server class-balanced medians
  ([result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.json),
  [note](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.md)).
  It used short prompts through raw untemplated `/completion` requests with
  `--reasoning off`. Do not relabel it as chat-template service throughput.
- **Quality:** complete generated token arrays matched 12/12 across the two
  servers, every request had zero cached tokens, and all objective canaries
  passed.
- **Context:** the one-user launcher serves 8,192 tokens by default. A separate
  one-slot campaign with 33,024-token capacity measured decode from `36.797`
  tok/s at 2,048 prompt tokens to `33.849` tok/s at 32,768, and server prompt
  evaluation from `1,032.33` to `915.09` tok/s
  ([table](#exact-active-context-profile)). That fixture is repeated-token
  shape evidence, not natural prose. A 512-token prompt-reading measurement is
  not published for this package.
- **Many users:** `run-throughput-server.sh` (64 slots, 32,768 total context
  tokens) measured **`163.644`** tok/s combined at 64 users, `2.557` per user.
  The c8-to-c16 drop is real and kept ([table](#output-audited-multi-user-profile)).
  These are aggregate batch-wall rates. Greedy output depends on batch shape;
  responses are isolated, not byte-identical to one-at-a-time answers.
- **Not measured yet:** tested platform installation; clean-host replay;
  beginner recovery flow; natural-prompt HTTP speed and TTFT context sweep
  beyond the qualified short-context headline; queued TTFT and per-request
  latency profile.

## If it fails

- **`Refusing to start a second llama.cpp model workload on this low-RAM host.`**
  Another `llama-server` is running. Stop it first; this launcher runs one
  model at a time.
- **`Missing executable: .../bin/llama-server`** or **`Missing model: ...`**:
  `QWEN38_BUILD_DIR` must be the build directory that contains
  `bin/llama-server`, and `QWEN38_MODEL` must be the `.gguf` file itself.
- **`Model SHA-256 mismatch`**: the file is not the pinned Q8_0 build. Download
  it again and rerun `verify-model-direct.sh`.
- **`verify-model-direct.sh` exits with code 2**: it could not read the file
  while bypassing the page cache, so it refuses to certify the bytes. Exit
  code 1 means a missing file or a hash mismatch.
- **A `source ... vars.sh` error at launch**: the launcher needs oneAPI at the
  fixed paths listed under [Before you start](#before-you-start).
- **The wrong cards or a device error at load**: the reference selector
  `level_zero:1,0` comes from the lab host. Confirm enumeration on your host
  before changing it; other selectors are untested.
- **An abort while stopping**: this runtime has a known host-allocator abort
  when cleanup gets a second interrupt, even after successful requests. Press
  `Ctrl-C` once and wait. A single-interrupt stop exited cleanly with both GPUs
  normal in the
  [package smoke](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp2-package-throughput-launch-smoke.json).
- **`bench.sh` reports `realistic fresh-response gate failed` or
  `output hashes differ from the promoted Qwen3.8 Q8 oracle`**: the run is not
  a valid reproduction. Keep the output file; do not quote its speed.
- **The strict replay script stops with `llama-server SHA-256 mismatch` or
  `SYCL backend SHA-256 mismatch`**: it accepts only the lab's accepted
  binaries. A new build with different hashes cannot reuse that script as is.

## Details

### Who built what

**neural.download lab — integrated:** Qwen3.8 transfer, the complete B70 TP2
stack, DP4A2 by SG24 optimization, semantic/repeat/needle gates, benchmarking,
and packaging. The matched Qwen3.8 transfer comparison measured `36.772932`
versus `31.353431 tok/s` (`+17.285%`) with all output hashes exact.

**mndodd — integrated runtime base:** supplied the optimized Intel SYCL
llama.cpp fork used as the starting runtime. A separate matched Qwen3.6 A/B
validated `+5.836%` for that base. That credit is deliberately scoped and does
not assign the lab's later Qwen3.8 result or patches to the base fork.

### Reproduce the strict headline

The quick start's `bench.sh` is a shorter service check. To reproduce the
strict headline contract, use two new create-only output directories. The
script accepts only a build whose `llama-server` and `libggml-sycl.so` hashes
equal the accepted DP4A2×SG24 build listed in the
[reproduction guide](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md#build):

```bash
ATTEMPT=my-q8-tp2-a \
MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/accepted-build \
OUT_DIR=/path/to/new-attempt-a \
  experiments/qwen38-27b-b70/scripts/run-20260827-qwen38-q8-tp2-strict-attempt.sh
```

Repeat as attempt B, then require the comparator to exit zero:

```bash
python3 scripts/compare-strict-attempt-outputs.py \
  /path/to/new-attempt-a /path/to/new-attempt-b \
  --output /path/to/new-comparison.json
```

The strict raw-completion outputs match the historical `36.772932 tok/s`
oracle 12/12 by complete response hash; the new paired result is 0.126% lower.
The launcher defaults to `--reasoning off`, while raw untemplated completion
prompts bypass the chat template. Always record reasoning and endpoint policy;
do not relabel this number as chat-template service throughput. See the
[strict result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.md).

### Output-audited multi-user profile

For throughput service, launch the separately qualified 64-slot, 32K-total
profile:

```bash
QWEN38_SOURCE_DIR=/path/to/llama.cpp-qwen38-q8-tp2 \
QWEN38_BUILD_DIR=/path/to/llama.cpp-qwen38-q8-tp2/build-sycl-aot-bmg-g31 \
QWEN38_MODEL=/path/to/qwen3.8-27b-q8/Qwen3.8-27B-Q8_0.gguf \
  repro/qwen38-27b-q8-tp2-asrock-b70/run-throughput-server.sh
```

| Simultaneous requests | Aggregate tok/s | Per-user tok/s |
| ---: | ---: | ---: |
| 1 | 32.487 | 32.487 |
| 2 | 51.601 | 25.801 |
| 4 | 85.595 | 21.399 |
| 8 | 125.414 | 15.677 |
| 16 | 84.329 | 5.271 |
| 32 | 125.832 | 3.932 |
| 64 | **163.644** | 2.557 |

Every point is the median of two preregistered fresh-server attempts; the
worst relative range was 1.46%. Each response returned 128 raw token IDs,
cached-token reuse was zero, and no output collided with another base task's
frozen oracle. Greedy output remains batch-shape-dependent. The reproduced
c8-to-c16 drop is deliberately not smoothed. These are aggregate batch-wall
rates, not queued TTFT or per-request latency. See the
[evidence](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp2-http-concurrency-r2-result.json).

### Exact active-context profile

The one-slot, reasoning-off HTTP service was also replayed at exact prompt
depths with a 33,024-token configured context. Each receipt returned 128 token
IDs with zero cache reuse, no truncation, and no context shift.
Server-reported prompt evaluation was captured directly; it is not estimated
from TTFT.

| Prompt tokens | Decode tok/s | Prefill tok/s | TTFT |
| ---: | ---: | ---: | ---: |
| 2,048 | 36.797 | 1,032.33 | 2.003 s |
| 4,096 | 36.553 | 1,038.62 | 3.957 s |
| 8,192 | 36.014 | 1,019.69 | 8.047 s |
| 16,384 | 35.085 | 983.52 | 16.681 s |
| 24,576 | 34.519 | 947.33 | 25.958 s |
| 32,768 | **33.849** | 915.09 | 35.832 s |

This is a grade-C repeated-token exact-shape fixture, not a natural-prose
latency claim. Every marker is measured; no interpolation or extrapolation is
used. See the [qualified replay](../../experiments/qwen38-27b-b70/data/qwen38-q8-tp2-http-depth-prefill-20260825-r3-attempt1/summary.json).
