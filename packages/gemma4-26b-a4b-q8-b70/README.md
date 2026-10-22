# Gemma 4 26B A4B Q8 — one-B70 reconstruction package

Gemma 4 26B A4B (UD-Q8_K_XL weights) on one Intel Arc Pro B70, for one user,
with a small Q4_0 MTP draft that guesses up to three tokens ahead; the Q8 model
checks every guess. It runs a patched llama.cpp SYCL build that you compile
yourself, either inside a pinned oneAPI 2026.0 container or natively. The
measured headline is **`122.160357 tok/s`** writing speed.

> **Status: source-verified reconstruction candidate, not a beginner install.**
> The exact aggregate source stack now applies cleanly from its pinned base.
> The original record binary hash and historical local Q4_0 draft hash were not
> retained. Source rebuilds passed the lab-host gates on September 7; a fresh
> OS installation and byte-identical historical replay remain unverified.
> Every new build must pass the full canary and cold-suite gates.

The [reproduction guide](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
is the technical source of truth.

## Before you start

| Need | Tested with / required |
| --- | --- |
| OS | Linux. The guide's beginner route targets a clean Ubuntu 24.04 host with the HWE kernel, and the build image is based on `ubuntu:24.04`, but that route has not been run end to end on a freshly installed host. Distribution and kernel of the measuring hosts: not recorded. |
| Driver stack | The Intel GPU kernel driver (`xe`): `ls /dev/dri/renderD*` should show one node per card, and your user must be in the `render` and `video` groups. The host also needs a oneAPI installation that provides `/opt/intel/oneapi/setvars.sh` (`preflight.sh` refuses without it; any version for the container route). Driver and firmware versions: not recorded. |
| Runtime / build | **Container route (the guide's beginner route):** build the pinned image from `docker/Dockerfile.record-build-oneapi-2026.0`; it carries the record's oneAPI 2026.0 compiler. **Native route:** `restore-and-build.sh`, which needs oneAPI 2026.0 at `/opt/intel/oneapi/compiler/2026.0`. Both apply the same patch to llama.cpp tag `b9769` (`c926ad0`). No prebuilt image or binary is published. |
| Tools | `docker` usable without `sudo` (container route), `git`, `jq` (`preflight.sh` reads the build receipt with it), `curl`, `python3` (the test scripts use only the standard library), `sha256sum`, and `aria2c` for the download. The native route also needs `cmake` and `ninja`. |
| Disk | Target 27.6 GB, F16 draft 0.86 GB, reconstructed Q4_0 draft 321,126,560 bytes. The image is 11.6 GB, and building it downloads about 2 GB of Intel packages. Native build size: not recorded. |
| Host RAM | Minimum not recorded. For the image build on a 16 GB host, the guide passes `--build-arg BUILD_JOBS=4`. |
| GPU | One B70 with no other model running. `GPU_INDEX` picks the card (`run.sh` default 0). The record ran on GPU 0 of the lab's four-B70 host. |
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

**Read this first.** This package is a benchmark recipe. Its start command
(`run.sh`) starts its own server, runs the full quality and speed gate, writes
the results, and stops the server again. No packaged command keeps the server
running for chat yet (see step 5). The steps follow the guide's container
route, written on 2026-09-06. The image build and two gate replays were
verified on the lab host, but the whole route has not been run end to end on a
freshly installed host, so treat it as the intended order of operations rather
than a tested transcript. The native route is under
[Restore The Record Source](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md#restore-the-record-source).

### 1. Download and verify the model

```bash
mkdir -p /path/to/models/MTP
aria2c -c -x 8 -s 8 -d /path/to/models -o gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
  'https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf?download=true'
aria2c -c -x 8 -s 8 -d /path/to/models/MTP -o gemma-4-26B-A4B-it-F16-MTP.gguf \
  'https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf?download=true'

echo '50e180d69641e017d7e08a6f602988effde8232ff6bc0231e839636fdcc03d8f  /path/to/models/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf' | sha256sum -c -
echo '36bf2f6710cf06ff1a5d026cca49ba88bd3451d8588a484ca5a79c5e30aa45f2  /path/to/models/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf' | sha256sum -c -
```

These are `unsloth/gemma-4-26B-A4B-it-GGUF` at revision
`3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`. Keep the exact file names and the
`MTP/` folder. The sizes and hashes are in the
[model manifest](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/model-manifest.json).
`preflight.sh` checks the target again before every run, and `prepare-draft.sh`
checks the F16 draft before it quantizes it.

### 2. Get the runtime

Build the pinned image, then make a small host folder whose `bin/llama-server`
and `bin/llama-quantize` run that image:

```bash
cd repro/gemma4-26b-a4b-q8-b70-125tps-20260701/docker
docker build --network=host -f Dockerfile.record-build-oneapi-2026.0 \
  -t gemma4-26b-q8-record:oneapi-2026.0-b9769 .
./install-container-build-dir.sh /path/to/gemma4-record-container
cd ../../..
```

The build fetches about 2 GB of Intel packages, then compiles for about
10 minutes on eight cores; on a 16 GB host add `--build-arg BUILD_JOBS=4`.
`install-container-build-dir.sh` refuses a folder that already exists, and it
prints the `LLAMA_SERVER` and `LLAMA_QUANTIZE` paths used below.

The container sees only the folders you list. `GEMMA4_MOUNT_DIRS` is mounted
read-only (its default is the lab's own model folders), and `GEMMA4_RW_DIRS` is
mounted writable for the draft that `llama-quantize` writes. Then make the Q4_0
draft from the F16 file:

```bash
export GEMMA4_MOUNT_DIRS=/path/to/models
GEMMA4_RW_DIRS=/path/to/models/MTP \
F16_DRAFT=/path/to/models/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf \
MTP_DRAFT_MODEL=/path/to/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
LLAMA_QUANTIZE=/path/to/gemma4-record-container/bin/llama-quantize \
  repro/gemma4-26b-a4b-q8-b70-125tps-20260701/prepare-draft.sh
```

Save the printed `DRAFT_SHA256`; step 3 needs it. It pins this draft for your
runs, but it does not prove byte identity with the lost historical draft.
`RECONSTRUCTED_REFERENCE_MATCH=true` (the repeat-stable `1f6706e4…` reference)
is expected but not required.

### 3. Start the server

This runs the full gate on one card. In terminal 1:

```bash
export GEMMA4_MOUNT_DIRS=/path/to/models
export SERVER_OUT_DIR=/path/to/gemma4-logs OUT_DIR=/path/to/gemma4-logs
LLAMA_SERVER=/path/to/gemma4-record-container/bin/llama-server \
MODEL=/path/to/models/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
MTP_DRAFT_MODEL=/path/to/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
DRAFT_SHA256=<sha256-printed-by-prepare-draft> \
GPU_INDEX=0 PORT=19350 \
  bash repro/gemma4-26b-a4b-q8-b70-125tps-20260701/run.sh
```

`run.sh` runs `preflight.sh` first and stops if any hash, receipt or
`setvars.sh` check fails; a failure there is a setup problem, not a
measurement. It then starts the record configuration: 32,768 tokens of
context, flash attention on, F16 KV, MTP draft up to 3 tokens, one slot.
`SERVER_OUT_DIR` and `OUT_DIR` are where the harness writes the server log;
both default to the lab's `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers`,
so set them to a folder you can write.

### 4. Wait until it is ready

There is nothing to do in another terminal. The harness polls the server and
prints `[gemma4-baseline] server ready` once it answers; it gives up after
900 seconds (`READINESS_TIMEOUT_S`). It then runs the 512-row chat canary and
the 12-prompt cold suite in the same terminal. Startup and total run time: not
recorded.

### 5. Send a first request

This package has no command that keeps a server running for chat. `run.sh`
starts the server on `127.0.0.1:19350` (model name `gemma4-26b-a4b-q8`), sends
its own chat requests (the canary and the 12-prompt suite), then stops it. Not
packaged yet. Do not send your own requests to it while the gate runs; they
would change the measurement.

### 6. Check status

The run writes `data/<LABEL>/summary.json`, `realistic-suite.json` and
`chat-canary.json` inside this checkout (`LABEL` defaults to
`gemma4-q8-gpu<GPU_INDEX>-125repro-<UTC time>`):

```bash
jq '{gate: .realistic_final_gate.passed, fresh: .fresh_response_validity.valid, cache_zero: .realistic_final_gate.cached_tokens_all_zero, canary: .canary_pass_all}' data/<LABEL>/summary.json
```

A result counts only if all four are `true`. The headline metric, the
class-balanced writing speed, is in `data/<LABEL>/realistic-suite.json` under
`summary.class_balanced_tok_s_1_100_intervals_after_ttft.median`;
`summary.json`'s `bench_summary` holds the older all-prompt figures.

### 7. Stop

`run.sh` stops its server when the gate finishes or fails. To stop it early,
press `Ctrl-C` once in terminal 1; its cleanup stops the server. Then
`pgrep -x llama-server` must print nothing, and `docker ps` must list no
`gemma4-record-*` container.

## What you get

- **Speed:** **`122.160357 tok/s`** writing speed for one user, under the
  2026-08-27 class-balanced publication rule: the median within each input
  class, then the median across the six class medians, using
  99 intervals between generated tokens 1 and 100 after the first token. The
  fixed realistic cold suite has 12 unique prompts, each run once, with
  512-token answers and 32,768 tokens of context
  ([record summary](../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json)).
  `123.727369` is the secondary all-prompt 99-interval median and `124.977141`
  is the historical 100-event compatibility figure; neither is the current
  headline. The directory name says `125tps` for that historical figure; it
  does not change the headline.
- **Quality:** the Q8 target verifies every accepted draft token; all 512 chat
  canary rows passed; every request had `cached_tokens=0`, with no prompt, KV
  or response reuse. The lane does not reproduce its own answers: four fresh
  servers with identical settings and greedy decoding returned 0/12 matching
  outputs, and the cause is in the target's own decode path, not the draft
  ([guide](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md#headline-result)).
- **Context:** the record uses a 32,768-token context. Separate measured
  profiles cover a July long-context service recipe and October prompt-reading
  sweeps; see [Performance over context](#performance-over-context) and
  [Latest prompt-reading measurements](#latest-prompt-reading-measurements).
  They use different settings from the headline.
- **Rebuilds on another host:** clean rebuilds replayed on the lab's two-B70
  host on September 7 passed every gate at `112.046`–`115.785 tok/s`
  class-balanced, below the record. The lab traced the gap to the change of
  host, not to the rebuild, so a lower number on your machine is not by itself
  a failure.
- **Not measured yet:**
  - the historical llama-server binary SHA-256;
  - the historical locally quantized Q4_0 MTP draft SHA-256 and byte size (the
    reconstructed draft is repeat-stable at `1f6706e4…` across three builds);
  - the beginner recovery flow exercised end to end on a fresh host (the
    pinned oneAPI 2026.0 container path and two clean-rebuild gate replays
    were verified on the lab host on 2026-09-07);
  - the October 15 coalesced-prefill candidate: full build and library
    digests, an exact compatibility source/build receipt, tracked long prompt
    inputs, and a clean rebuild and full-gate replay. Its 13–22% measured gains
    are not in this package's runtime or published profiles.

## If it fails

- **`PREFLIGHT FAIL: target model byte-size mismatch`** or **`target model
  SHA-256 mismatch`**: the target is not the pinned file. Download it again
  (step 1).
- **`PREFLIGHT FAIL: local draft SHA-256 mismatch`**: `DRAFT_SHA256` must be
  the value `prepare-draft.sh` printed for this exact draft file.
- **`PREFLIGHT FAIL: missing build receipt`**: `LLAMA_SERVER` must be the
  `bin/llama-server` inside the folder made by `install-container-build-dir.sh`
  (or by `restore-and-build.sh`); the receipt sits one level above `bin/`.
- **`PREFLIGHT FAIL: build base commit mismatch`** or **`build aggregate patch
  mismatch`**: the build is not this recipe's source. Rebuild it.
- **`PREFLIGHT FAIL: jq is required ...`** or **`Intel oneAPI setvars.sh is
  missing`**: install `jq`, or a oneAPI base toolkit on the host (any version
  for the container route).
- **`PREFLIGHT FAIL: another llama-server is already running`**: stop it first.
  This includes a server inside a `gemma4-record-*` container.
- **`F16 draft byte-size mismatch.`** or **`F16 draft SHA-256 mismatch.`**:
  download the F16 draft again.
- **`Refusing to overwrite: ...`** (`prepare-draft.sh`) or **`Refusing to
  overwrite existing path: ...`** (`install-container-build-dir.sh`,
  `restore-and-build.sh`): choose a new path.
- **An error that names `/mnt/fast-ai/...` or `/home/steve/...`**: those are
  the lab's own defaults. Set `SERVER_OUT_DIR`, `OUT_DIR` and
  `GEMMA4_MOUNT_DIRS` as in step 3. The container can only open model files
  inside the folders listed in `GEMMA4_MOUNT_DIRS` and `GEMMA4_RW_DIRS`.
- **`[gemma4-baseline] server exited before readiness`** or **`server did not
  become ready after 900s`**: the harness prints the last 80 lines of the
  server log; the full log is in `SERVER_OUT_DIR`.
- **`The record toolchain was oneAPI 2026.0 ...`** (native route): install the
  2026.0 compiler or use the container route. Setting `ICX`/`ICPX` makes a
  separately labelled compatibility build, not the record toolchain.
- **`Base commit mismatch after clone.`** or **`Decoded aggregate patch hash
  mismatch.`** (native route): stop. Do not edit around a hash check.
- **The gate does not pass** (any of the four `summary.json` checks in step 6
  is `false`): the run is not a valid result. Keep the files; do not quote its
  speed.
- **If you change the image:** keep its entrypoint. The 2026.0 oneDNN package
  pulls in the 2026.1 compiler runtime, and a plain `setvars.sh` would put that
  runtime first; the entrypoint sources the 2026.0 components explicitly.

## Details

### Project files

Every required project artifact is linked inside our repository:

- [canonical aggregate patch](../../patches/gemma4-26b-a4b-q8-b70/README.md);
- [source restore/build helper](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh);
- [pinned model manifest](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/model-manifest.json);
- [record evidence](../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json);
- [full result packet](../../results/gemma4-26b-a4b-q8-b70/README.md).

### Who built what

**neural.download lab — integrated:** Gemma 4 B70 bring-up, llama.cpp/SYCL and
MoE optimization, target-verified MTP work, source reconstruction, and package
validation. The roughly `15.55 tok/s` early one-card Q8 starting point and the
`124.977 tok/s` high use different configurations, so they document this
lab's development history and are not presented as one like-for-like boost.
The exact identities and matched increments remain in the
[result packet](../../results/gemma4-26b-a4b-q8-b70/README.md).

### Performance over context

The guide library graphs the validated one-card service sweep below. Each
point is the arithmetic mean of four independent B70 lanes. Every prompt was
unique and cache-zero, and every exact JSON retrieval gate passed.

| Actual prompt/context tokens | Decode after TTFT | Approx. prefill | TTFT |
| ---: | ---: | ---: | ---: |
| 741 | 161.90 tok/s | 847.96 tok/s | 0.874 s |
| 2,806 | 144.87 tok/s | 1,401.02 tok/s | 2.003 s |
| 5,643 | 141.11 tok/s | 1,469.44 tok/s | 3.841 s |
| 10,976 | 135.93 tok/s | 1,330.39 tok/s | 8.251 s |
| 16,213 | 127.64 tok/s | 1,256.95 tok/s | 12.899 s |
| 22,730 | 120.48 tok/s | 1,128.98 tok/s | 20.134 s |
| 30,400 | 114.00 tok/s | 1,028.20 tok/s | 29.568 s |
| 32,571 | 114.85 tok/s | 1,001.69 tok/s | 32.517 s |

This uses the long-context service profile and a 128-token output ceiling; it
is not the same operating identity as the short-context `122.160 tok/s`
headline. Prefill is approximated as actual prompt tokens divided by TTFT.
See the [compact profile](../../data/gemma4-26b-a4b-q8-b70-context-performance-profile-20260702.json)
and [all 32 source rows](../../data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json).

### Latest prompt-reading measurements

The October 10 16K-slot sweep now plots actual input tokens instead of the
requested lengths. The request for 512 tokens produced **509 tokens**:
prefill was **1,323.8 tok/s with draft 3** or **1,327.8 tok/s without a
draft** (median of three timings per setting). That is a measured 509-token
result, not a measured 512-token result. The five actual graph coordinates
are 292, 509, 2,042, 8,185 and 15,793; requested counts remain annotations.
See the [draft-3 receipts](../../data/profiles/2026-10-10/gemma-sweep/single-16k-draft3.json)
and [no-draft receipts](../../data/profiles/2026-10-10/gemma-sweep/single-16k-draft0.json).

A separate October 15 production profile measures **1,307.54 / 1,167.81 /
909.27 tok/s** at **1,867 / 7,623 / 29,400 actual input tokens**, respectively.
Each point averages four timings on two servers. It uses one 32K slot, no
draft, f16 KV, deterministic oneDNN, and prefill micro-batch 1024. Timings
come directly from the server's prompt counters, with prompt caching
disabled. The diagnostic prompts repeat; this is not the cold-suite decode
headline or the July curve's TTFT approximation.

The [guide's exact table and method](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md#october-15-production-prompt-reading-profile)
and [source-linked timing summary](../../experiments/gemma4-26b-a4b-q8-b70/data/2026-10-15-prefill-reorder/publication-summary.json)
keep the complete precision and observed ranges.

The October 15 experimental coalesced conversion measured 13–22% faster
prefill with tested token parity, but **has not shipped in this package**.
Full build/library identities, tracked prompt inputs and clean-rebuild
replay remain open. Its gain is not silently applied to the package curves
or the decode headline. The guide links the retained patch and exact gates.

The remaining baseline packaging gate is an end-to-end fresh-host install
with retained source/model/binary receipts; the documented September 7
lab-host rebuild is already complete. The historical binary and draft
identity gaps remain explicit.
