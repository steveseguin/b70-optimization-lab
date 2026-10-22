# Qwen3.8 27B Q4_K_M + Q4_0 MTP2 on two Arc Pro B70s

> **Lab-validated candidate package.** Two fresh MTP2 servers measured
> `64.180644` and `64.293959 tok/s`; their median is **`64.237301 tok/s`**.
> The matched TP2/MTP0 oracle measured `49.787366 tok/s`, a **29.02%** gain.
> All 24/24 complete candidate arrays matched the unchanged target oracle.
> Clean-host Intel/oneAPI installation and source-build replay remain pending.

Qwen3.8 27B as a 4-bit GGUF (Q4_K_M), served by a patched llama.cpp SYCL build
on two B70 cards, with a small Q4_0 draft model (MTP depth 2) that guesses two
tokens ahead. The full target model checks every guessed token, so answers are
the same as without the draft. One user at a time, 8,192-token context.

This is a separate deployment from both the
[two-card target-only package](../qwen38-27b-q4km-tp2-asrock-b70/README.md)
and the [one-card MTP2 package](../qwen38-27b-q4km-mtp2-tp1-b70/README.md).
Its target is split equally across two B70s; the 1.37 GB draft remains on the
first card. Do not transfer context or concurrency values between those
profiles.

## Before you start

| Need | Tested with / required |
| --- | --- |
| Cards | Two Intel Arc Pro B70 32 GiB, with no other GPU work on them. The launcher fixes `ONEAPI_DEVICE_SELECTOR=level_zero:1,0`, which the measured host enumerated as `SYCL0,SYCL1`. The target is split 1:1 over `SYCL0,SYCL1`; the draft runs on `SYCL0`. Check `sycl-ls` on your machine: another host may enumerate its cards differently. |
| OS and kernel | x86_64 Linux (preflight refuses anything else). Distribution and kernel version: not recorded. |
| GPU driver stack | Level Zero GPU driver: version not recorded. Driver installation is not covered here and has not been tested on a clean host. |
| Runtime | Native build, no container. [mndodd/llama.cpp](https://github.com/mndodd/llama.cpp) at `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` plus six lab patches (listed under [Source and required patches](#source-and-required-patches)). Intel oneAPI must be installed at `/opt/intel/oneapi`. The builder's default compiler is `/opt/intel/oneapi/compiler/2026.0/bin/icpx` (override with `CXX_COMPILER`). The measured servers loaded oneAPI 2026.1 compiler and MKL runtime libraries. |
| Python | `python3` for the model verifier and the benchmark; version not recorded. |
| Host RAM | Preflight requires at least 15 GiB of RAM and at least 24 GiB of RAM plus swap. The tested 16 GiB host used swap. The launcher caps the server at 13 GiB of RAM (`MemoryMax=13G`). |
| Disk | Target 18,973,870,432 bytes plus draft 1,369,590,656 bytes (about 20.3 GB together). Source and build size: not recorded. |
| Network / oneCCL | No oneCCL settings: the launcher uses llama.cpp's own two-card SYCL split. |
| Other tools | `git`, `cmake`, `/usr/bin/cc`, `base64` and `gzip` for the build; `huggingface-cli` for the download; a systemd user session (the launcher uses `systemd-run --user --scope`); `flock`, `pgrep` and `curl`. |

## Quick start

Run every command from the repository root after
`git clone https://github.com/steveseguin/b70-optimization-lab && cd b70-optimization-lab`.
Replace every `/path/to/...` with your own absolute directories.

### 1. Download and verify the model

Two files from two pinned repositories; both are required.

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q4_K_M.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/target

huggingface-cli download unsloth/Qwen3.8-27B-GGUF \
  MTP/mtp-Qwen3.8-27B-Q4_0.gguf \
  --revision 4ca720788d1e01f1bff70c033e0d0028fd02e502 \
  --local-dir /path/to/draft

TARGET_DIR=/path/to/target DRAFT_DIR=/path/to/draft/MTP \
  repro/qwen38-27b-q4km-mtp2-tp1-b70/verify-models.sh
```

The verifier reads each file twice (direct and ordinary reads) and checks its
size and SHA-256. The expected hashes are in [`manifest.sha256`](manifest.sha256).

### 2. Get the runtime

This package ships no prebuilt binary. Build the patched llama.cpp into a new
directory (the builder refuses to overwrite an existing one):

```bash
SOURCE_DIR=/path/to/llama.cpp-src \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/restore-and-build.sh
```

It prints `BUILD COMPLETE` and the build directory,
`/path/to/llama.cpp-src/build-sycl-aot-bmg-g31`. `BUILD_JOBS` sets parallel
compile jobs (default 2). Then check the host, the cards, both model files and
the binaries:

```bash
export TARGET_DIR=/path/to/target
export DRAFT_DIR=/path/to/draft/MTP
export BUILD_DIR=/path/to/llama.cpp-src/build-sycl-aot-bmg-g31
repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/preflight.sh
```

Preflight compares `llama-server` and `libggml-sycl.so` with the measured
binaries' hashes. Whether a fresh build reproduces those hashes has not been
tested (the clean-host source build is still on the missing list). If preflight
stops with `llama-server differs from the measured binary`, you can still run
your own build with `export ALLOW_REBUILT_BINARIES=1`. That is a new runtime
identity: it is not the measured package until it passes the
[paired check](#check-the-result-yourself-paired-replay).

### 3. Start the server

In terminal 1, with the three variables from step 2 still exported:

```bash
MTP_DEPTH=2 repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
```

The server runs in the foreground. The launcher runs preflight again first,
including the two-pass model check, so startup takes a while. It serves on
`127.0.0.1:18142` with an 8,192-token context and one slot.

Run identity note: the two measured MTP2 servers (and the MTP0 oracle) ran with
`GGML_SYCL_FUSE_EXT=31`, as their runtime-environment receipts in the
[evidence archive](../../experiments/qwen38-27b-b70/data/qwen38-q4km-q4mtp-tp2-mtp2-20260830/manifest.json)
show. Later the same day (commit `19ef150ed`) the launcher default became
`15`, because fusion bit 4 is experimental and a separate target-only control
with bit 4 on and batch 2048 failed its output check. The current default has
not been measured for this MTP2 package. To start the exact measured
configuration instead, add `FUSE_EXT_OVERRIDE=31` to the command above.

### 4. Wait until it is ready

Terminal 1 prints `llama_server: listening on http://127.0.0.1:18142` once the
model is loaded. In terminal 2, this succeeds when the server is ready:

```bash
curl -fsS http://127.0.0.1:18142/health
```

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18142/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-q4km-q4mtp-tp2-mtp2","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

With the OpenAI Python client (`pip install openai` once):

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18142/v1", api_key="unused").chat.completions.create(model="qwen38-q4km-q4mtp-tp2-mtp2", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

The launcher sets no model alias; `qwen38-q4km-q4mtp-tp2-mtp2` is the name the
lab's own checks send. The server starts with reasoning off
(`--reasoning off`). Send one request at a time: the server has one slot.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18142/health
pgrep -a -x llama-server
```

### 7. Stop

Press Ctrl-C once in terminal 1 and wait. Then `pgrep -x llama-server` must
print nothing.

## What you get

- **Speed (one user):** two fresh MTP2 servers measured `64.180644` and
  `64.293959 tok/s`; the median is **`64.237301 tok/s`**, against
  `49.787366 tok/s` for the matched TP2 target-only oracle (+29.02%). All 24/24
  complete answers matched the target-only oracle. The workload is the fixed
  12-prompt, six-class suite with a 512-token answer cap and zero cached tokens.
  These runs used `GGML_SYCL_FUSE_EXT=31` (see step 3).
  [Result note](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promoted-result.md),
  [promotion attestation](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promotion-attestation.json).
- **Context:** 8,192 tokens configured. This is short-context evidence only.
- **Many users at once:** not measured for this exact profile; the server has one slot.
- **Not measured yet:**
  - measured 32K active-context profile for this exact MTP2 deployment
  - output-qualified HTTP concurrency profile for this exact MTP2 deployment
  - standard 512-token prompt TTFT and prefill measurement
  - tested clean-host Intel driver and oneAPI installation
  - clean-host source build and endpoint replay
  - beginner recovery replay

## If it fails

- **Preflight or launch stops on a hash** (`llama-server differs from the
  measured binary`, `libggml-sycl.so differs from the measured backend`, or an
  `IDENTITY MISMATCH` from the model verifier): never bypass a model hash
  failure; download the file again. A binary mismatch means your build is a new
  identity; see step 2.
- **`Intel oneAPI setvars.sh is missing`** or **`Missing compiler: ...icpx`**:
  install oneAPI under `/opt/intel/oneapi`, or point `CXX_COMPILER` at your
  `icpx` for the build.
- **`Refusing to overwrite existing path`** from the builder: give
  `SOURCE_DIR` a directory that does not exist yet.
- **`the measured selector did not enumerate two Level Zero GPUs`:** the fixed
  `level_zero:1,0` selector did not find two cards. Check `sycl-ls`. Another
  enumeration is a separately validated topology, not this package.
- **`at least 15 GiB physical host RAM ...`** or **`at least 24 GiB combined RAM
  plus swap is required`:** the host is below the tested memory boundary.
- **`Another llama-server is running`**, **`Another model campaign owns the host
  lock`**, **`GPU 0 is locked`** or **`GPU 1 is locked`:** stop the other model
  server or campaign first. Do not compile while the model is loaded.
- **Launch fails for another reason:** stop the foreground scope, verify both
  B70s are idle with `xpu-smi`, confirm no `llama-server` remains, and rerun
  preflight.

## Details

### Source and required patches

The builder pins the mndodd base at
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` and verifies/applies the complete
measured stack in order:

1. [Full Intel SYCL lab TP2/DP4A2 stack](../../patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64).
2. [Qwen3.8 Q4_K_M TP2 increment](../../patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64).
3. [GDN state-I/O widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-gdn-state-io-widen-20260821.diff.gz.b64).
4. [Convolution/QK widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-conv-qk-widen-20260821.diff.gz.b64).
5. [QK source-shape widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-qk-norm-rope-src-widen-20260821.diff.gz.b64).
6. [Memo hardening artifact](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-q8out-rejected-memo320-20260821.diff.gz.b64); its rejected door remains disabled.

The measured `llama-server` and `libggml-sycl.so` hashes are enforced by
default. A clean rebuild may set `ALLOW_REBUILT_BINARIES=1`, but that is a new
runtime identity and must pass the complete paired validation below before its
speed is compared with this package. The exact target, draft, server, and
SYCL-backend hashes are in [`manifest.sha256`](manifest.sha256).

To check the retained evidence archive and promotion attestation without
starting a server:

```bash
repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/verify-evidence.sh
```

### Check the result yourself (paired replay)

Use the same exported `TARGET_DIR`, `DRAFT_DIR` and `BUILD_DIR` as in the
quick start. Run a fresh target-only oracle:

```bash
MTP_DEPTH=0 PORT=18142 \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
```

In another terminal, run the complete suite once:

```bash
MTP_DEPTH=0 BASE_URL=http://127.0.0.1:18142 \
OUT_DIR=/path/to/fresh-tp2-mtp0 \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/bench.sh
```

Stop the oracle with Ctrl-C and confirm `pgrep -x llama-server` is empty.
Start a new MTP2 server:

```bash
MTP_DEPTH=2 PORT=18142 \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
```

Then validate MTP2 against the fresh oracle:

```bash
MTP_DEPTH=2 BASE_URL=http://127.0.0.1:18142 \
OUT_DIR=/path/to/fresh-tp2-mtp2 \
ORACLE_JSON=/path/to/fresh-tp2-mtp0/performance.json \
  repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/bench.sh
```

`OUT_DIR` must be a new directory each time. To replay the measured identity,
start both servers with `FUSE_EXT_OVERRIDE=31` (see the run identity note in
step 3).

Success requires the complete 12-prompt/six-class 512-cap suite, every cache
count zero, all four objective canaries, and `target_arrays_exact=12/12`.
Model residency and compiled kernels are valid steady state. Prompt/KV/
response caching, learned drafting, repeated fixtures, subsets, and warmed
continuations are not permitted. A speed printed by a failed gate is not a
result.

### Measured result

| deployment | fresh run | strict tok/s | exact to MTP0 |
| --- | ---: | ---: | ---: |
| TP2 Q4_K_M, no MTP | R1 | 49.787366 | oracle |
| TP2 Q4_K_M + Q4_0 draft, MTP2 | R1 | 64.180644 | 12/12 |
| TP2 Q4_K_M + Q4_0 draft, MTP2 | R2 | 64.293959 | 12/12 |

The primary metric is the median within each of six prompt classes and then
the median across class medians, measured over the 99 intervals between output
events 1–100 after TTFT. Both candidates also matched each other on all 12
complete arrays; candidate rate drift was 0.18%. See the
[result note](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promoted-result.md),
[R1 comparison](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-screen-r1-result.json),
[R2 comparison](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-replication-r2-result.json),
and [promotion attestation](../../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promotion-attestation.json).

### Boundaries

- This is short-context, single-user evidence with 8K configured context. No
  32K or multi-user value has been measured for this exact MTP2 profile.
- MTP depths above 2 are not authorized by this campaign.
- The tested 16 GiB host used a 13 GiB process cap and swap. Stop competing
  model processes before launch; do not compile while the model is loaded.
- Never bypass a model or binary hash failure to recover a headline result.
- A clean-host Intel driver/oneAPI installation, source build, and beginner
  recovery replay remain pending, so package status remains candidate.
