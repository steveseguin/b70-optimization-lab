# Gemma 4 26B A4B Q8 on one B70, 122.16 tok/s

> **Certification: `candidate-portable-repro`, not a starter guide.** Install,
> restore, launch, and validation material is closed for the lab's own hosts;
> clean-host certification is still pending. The open items are listed under
> this guide's `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json).

**New to this? Start with the [package guide](../../packages/gemma4-26b-a4b-q8-b70/README.md#before-you-start):**
prerequisites, a seven-step [quick start](../../packages/gemma4-26b-a4b-q8-b70/README.md#quick-start)
(download, runtime, start, ready, first request, status, stop) and
[fixes for common errors](../../packages/gemma4-26b-a4b-q8-b70/README.md#if-it-fails).
This package runs a benchmark gate; it has no packaged command that keeps a
server running for chat.

This is the standalone promoted reproduction packet for the current Gemma 4
26B A4B Q8/INT8-quality short-decode record on one Intel Arc Pro B70.

> **Reconstruction status (2026-08-22):** the exact aggregate source snapshot
> now applies cleanly to its pinned base, but the historical server binary hash
> and local Q4_0 draft hash were not retained. This packet is therefore a
> source-verified reconstruction candidate, not yet a clean-host beginner
> install or a byte-identical historical replay.

The scripts and records this packet uses:

- [record gate runner](../gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh)
  (`run.sh` below calls it);
- [realistic suite](../gemma4-26b-a4b-q8-b70/realistic-suite-v1.json);
- [full result packet](../../results/gemma4-26b-a4b-q8-b70/README.md);
- detailed reproduction notes:
  `../../results/gemma4-26b-a4b-q8-b70/reproduce.md`
- [canonical aggregate patch and verification receipt](../../patches/gemma4-26b-a4b-q8-b70/README.md);
- [pinned model identities](model-manifest.json).

## Headline Result

- Primary metric: **`122.16035656735696 tok/s`**, median within each input
  class, then median across the six class medians, using 99 inter-token
  intervals between generated tokens 1 and 100 after TTFT.
- Suite: fixed realistic cold prompt suite, 12 unique prompts, each prompt run
  once.
- Output length: `MAX_TOKENS=512`.
- Context limit: `CTX_SIZE=32768`.
- Cache policy: `cached_tokens=0` on every request; no prompt/KV/context
  checkpoint/response reuse, no n-gram or history acceleration.
- Quality lane: UD-Q8_K_XL target/verifier with Q4_0 MTP draft; all accepted
  speculative tokens are verified by the Q8 target.
- Canary: `512/512` chat canary rows passed.
- LocalMaxxing ID: `cmr1u77na01k2ld01kalwzs1e`.
- Evidence:
  [`summary.json`](../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json).

Record metrics from the evidence JSON:

| Metric | Value |
| --- | ---: |
| class-balanced median, 99 intervals (headline) | `122.16035656735696` |
| all-prompt median, 99 intervals (secondary) | `123.72736943965284` |
| historical 100-event compatibility median | `124.97714084813418` |
| historical 100-event compatibility p10 | `103.83610041293295` |
| historical 100-event compatibility mean | `122.4743547166875` |
| median TTFT | `178.6938319564797 ms` |
| median full512 after-TTFT tok/s | `114.87107033590775` |
| median wall full512 tok/s | `108.58112847853889` |

The packet directory retains its historical `125tps` name; that does not
change the current metric. The older support/replay figures below retain
their original accounting and must not be substituted for the headline.

Same-family historical support rows include `123.67689864739785`,
`121.59076340768573`, `121.41411987308553`, `119.94842631460949`,
`119.26425148518223`, and `113.63257982764395 tok/s`. This lane has several
percent run-to-run variance, so close comparisons require same-window controls.

Latest reproducibility check while creating this packet:

- run:
  `../../data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`;
- validity: `realistic_final_gate.passed=true`,
  `fresh_response_validity.valid=true`, `cached_tokens=0` on all 12 prompts,
  `512/512` canary rows passed;
- metric: `120.92334534956485 tok/s` median generated-token throughput for
  tokens 1-100 after TTFT, p10 `105.95927439380908`, mean
  `118.86003674156144`, median full512 after-TTFT `112.61378328154639`,
  median wall full512 `107.50910206155777`, median TTFT
  `177.91116051375866 ms`;
- interpretation: valid same-recipe support run, not a new record. It
  reproduces the promoted path and validity gate, while landing within the
  known several-percent run-to-run spread below the `124.977` high.

Clean-rebuild replays on the lab host (2026-09-07, one B70, same gate):

| build | run | median tok/s 1-100 after TTFT | class-balanced median | p10 | median TTFT | gates |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| oneAPI 2026.1.1 host compatibility build (`26fc4868…`) | `data/gemma4-q8-gpu0-125repro-compat2026.1-20260907T040139Z/summary.json` | `115.288` | `115.785` | `104.013` | `192.3 ms` | realistic gate passed, fresh valid, cache zero, canary 512/512 |
| pinned oneAPI 2026.0 container (`ae45b2f0…`, image `e22b500d…`) | `data/gemma4-q8-gpu0-125repro-container2026.0-20260907T040615Z/summary.json` | `111.197` | `112.046` | `102.253` | `192.8 ms` | realistic gate passed, fresh valid, cache zero, canary 512/512 |
| pinned oneAPI 2026.0 container, second run | `data/gemma4-q8-gpu0-125repro-container2026.0-run2-20260907T041051Z/summary.json` | `116.346` | `115.526` | `103.405` | `193.1 ms` | realistic gate passed, fresh valid, cache zero, canary 512/512 |

Both are valid same-recipe support runs, not new records: they reproduce the
promoted path and validity gate from source with the reconstructed draft
(`1f6706e4…` from both quantizers). The container's first run trailed the host
build by about 3.5%, and its second run matched it, so the container carries no
measurable overhead.

They do **not** land within ordinary run-to-run variance of the `124.977` high,
and an earlier version of this section said they did. Five further replays at
the record's own settings put the six-sample mean at `111.819 tok/s` with a
`2.394%` coefficient of variation - matching this lane's documented `2.324%`,
so the host is not unusually noisy - which leaves the record about eleven
standard errors away and the best single run still `6.91%` short. The reason is
that the comparison is cross-host: the record-era Gemma runs used four GPU
indices (`420` runs on `gpu2`, `404` on `gpu3`), and this host has two B70s
addressable only as 0 and 1, so that research ran on the four-B70 measuring
host. Replaying here is not a way to check the record. See
[`experiments/gemma4-26b-a4b-q8-b70/notes/2026-09-07-replay-shortfall-is-cross-host-and-threads-are-oversubscribed.md`](../../experiments/gemma4-26b-a4b-q8-b70/notes/2026-09-07-replay-shortfall-is-cross-host-and-threads-are-oversubscribed.md).

One further finding from that work applies to anyone replaying on a two-card
host, and one candidate did not survive checking. The candidate first: the
record's `--spec-draft-threads 32` is oversubscribed on this machine's
8-core/16-thread CPU, and at two samples 16 threads looked `3.06%` faster with a
much tighter spread. Six samples per arm put it at `+1.72%` with heavily
overlapping ranges (Welch `t = 1.40`, about `p = 0.19`), so it is **not
established** and the recipe's setting is unchanged. The finding that does hold
is that the lane does not reproduce its own answers - four fresh servers with identical
settings, greedy decoding and identical prompts returned `0/12` matching outputs,
diverging as early as character 26. The lane's gates never covered output
identity, so that is a newly measured property rather than a broken claim. It is
attributed: two further servers with every `--spec-draft` argument removed score
`0/12` against each other as well, so the nondeterminism is in the target's own
decode path, not in the draft. Speculation is worth about `1.47x` on this lane
and is not what costs it reproducibility.

## Runtime Identity

This is the lab's historical record identity. The checkout, build and model
paths below existed only on the lab's record host; they are kept as evidence.
Do not create them. The quick start uses your own paths.

- Host: one Intel Arc Pro B70 32 GB replica per run; the lab has four B70s and
  used them for parallel same-window A/B screens and cross-over checks.
- Source: llama.cpp `c926ad098` plus the local Gemma record stack.
- Active source checkout:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`.
- Record build:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`.
- Target model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.
- Draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`.
- KV cache: `f16` target and draft.
- FlashAttention: on.
- VMM: on.
- Speculation: draft-MTP, `n_max=3`, `n_min=2`, `p_min=0.0475`.

## Restore The Record Source

The old lab checkout paths below document history; new users should not create
or edit those paths. Restore a new source directory from the in-repository
aggregate instead:

```bash
cd /path/to/b70-optimization-lab
SOURCE_DIR=/path/to/new/llama.cpp-gemma4-record \
  repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh
```

The helper clones official llama.cpp tag `b9769`, verifies full base commit
`c926ad09857517978575d6a74d225b463f7417a0`, decodes and hash-checks our
canonical aggregate patch, applies it, runs `git diff --check`, and builds with
the record's VDR2 compile definition. The embedded browser UI and its remote
prebuilt-asset fetch are disabled so a changed web bundle cannot break or
silently alter the API-server reconstruction; the record workload used the
HTTP API, not that UI. The helper refuses to overwrite an existing source
directory and defaults to the historical oneAPI 2026.0 compiler paths.

The downloadable target and F16 MTP source are pinned in
`model-manifest.json`. Download them from revision
`3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a` of
`unsloth/gemma-4-26B-A4B-it-GGUF`, verify their manifest hashes, then reconstruct
the local record draft:

- [UD-Q8_K_XL target/verifier](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf?download=true)
- [F16 MTP draft source](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf?download=true)

Both are large-file objects; use a resumable downloader and keep the exact
filenames. `preflight.sh` checks the target SHA-256, while `prepare-draft.sh`
checks the F16 source SHA-256 before quantizing it.

```bash
F16_DRAFT=/models/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf \
MTP_DRAFT_MODEL=/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
LLAMA_QUANTIZE=/path/to/new/llama.cpp-gemma4-record/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-quantize \
  repro/gemma4-26b-a4b-q8-b70-125tps-20260701/prepare-draft.sh
```

Save the printed `DRAFT_SHA256`. It pins the reconstructed draft for a run,
but it does not retroactively prove byte identity with the lost historical
local draft. The 2026.1.1 compatibility build produced a repeat-stable
reference (`3/3` byte-identical quantizations): `321126560` bytes,
SHA-256 `1f6706e4a09524c7aa83cea45eec637cd3e2aa7ccfa80c2dbef7a092ec0fddbd`.
The helper reports whether a new output matches that reference.

Important flags:

```text
GGML_SYCL_ENABLE_VMM=1
FLASH_ATTN=on
CTX_SIZE=32768
UBATCH_SIZE=1024
LLAMA_SYCL_F16_P021_SMALL_NCOLS=1
LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1
LLAMA_MTP_DRAFT_FAST_ARGMAX=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
```

## Container Build Path (pinned oneAPI 2026.0)

The host that set the record no longer carries the oneAPI 2026.0 compiler (it
has 2025.3 and 2026.1), and a beginner's clean host has none of the stack. The
`docker/` directory therefore packages the record toolchain as an image so the
rebuild does not depend on what is installed on the host:

```bash
cd /path/to/b70-optimization-lab/repro/gemma4-26b-a4b-q8-b70-125tps-20260701/docker
docker build --network=host -f Dockerfile.record-build-oneapi-2026.0 \
  -t gemma4-26b-q8-record:oneapi-2026.0-b9769 .
```

The Dockerfile starts from `ubuntu:24.04`, adds Intel's GPU (`noble/intel-omix/0.3
unified`) and oneAPI apt repositories, installs the 2026.0 DPC++ compiler,
oneMKL and oneDNN plus the Level Zero/OpenCL runtime and `ocloc`, clones
official llama.cpp tag `b9769`, verifies the base commit, decodes and
hash-checks the same aggregate patch that `restore-and-build.sh` uses, and
builds `llama-server` and `llama-quantize` with the record cmake definition
(`-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2`, AOT `bmg-g31`, SYCL graph, oneDNN).
The build writes the same `b70-gemma4-record-source.json` receipt that
`preflight.sh` validates, with the binary digests added. The image entrypoint
sources `setvars.sh` and execs the tool named by `LLAMA_TOOL`
(default `llama-server`).

The host side needs only the Intel GPU kernel driver (`xe`), Docker, and
`/opt/intel/oneapi/setvars.sh` for the harness's own environment step (any
oneAPI version; the container uses its own). Materialise a shim build
directory so the unchanged guide commands work:

```bash
docker/install-container-build-dir.sh /path/to/gemma4-record-container
# prints LLAMA_SERVER=/path/to/gemma4-record-container/bin/llama-server
#        LLAMA_QUANTIZE=/path/to/gemma4-record-container/bin/llama-quantize
```

`bin/llama-server` there is `llama-server-docker-shim.sh`: it forwards the
harness's arguments verbatim, passes through only the `GGML_*`, `LLAMA_*`,
`ONEAPI_DEVICE_SELECTOR`, `ZE_*`, `SYCL_*`, `OMP_*` variables, mounts the model
directories read-only at their host paths (`GEMMA4_MOUNT_DIRS`, default
`/home/steve/llm-models /mnt/fast-ai/llm-models`), exposes `/dev/dri` with the
`render`/`video` groups, and stays in the foreground so the harness's kill of
the shim stops the container. Use the printed paths as `LLAMA_QUANTIZE` for
`prepare-draft.sh` and `LLAMA_SERVER` for `run.sh` exactly as documented above.

### Beginner recovery flow (clean Ubuntu 24.04 host, one B70)

The step-by-step flow for this container path now lives in one place: the
package's [quick start](../../packages/gemma4-26b-a4b-q8-b70/README.md#quick-start)
and [fixes for common errors](../../packages/gemma4-26b-a4b-q8-b70/README.md#if-it-fails).
It was written on 2026-09-06 and has not yet been exercised end to end on a
freshly installed host, so treat it as the intended order of operations rather
than a tested transcript.

Status (2026-09-06, verified on the lab host): the image built from this
Dockerfile (id `e22b500d1672…`, 11.6 GB) reports `version: 1 (c926ad0)`,
`built with IntelLLVM 2026.0.0`, enumerates both B70s through the shim
(`SYCL0`/`SYCL1`, 32656 MiB), and its receipt carries `llama-server`
SHA-256 `ae45b2f0dfa650f330979e600e585c28571227ec0ae269aaaff7d00c994c93bb` and
`llama-quantize` SHA-256
`c16bd2ec76e4dc6544fb5fd0f2ab2a0faec6c14ff203f7ecb91175ddc1fa89a8`. Two
details the build surfaced, both handled by the image's entrypoint: the
2026.0 oneDNN package pulls in the 2026.1 DPC++ runtime as a dependency and
`setvars.sh` would put that runtime first on the library path, so the
entrypoint sources the `umf/1.1`, `tbb/2023.0`, `compiler/2026.0`,
`mkl/2026.0` and `dnnl/2026.0` component environments explicitly (the binary
then resolves `libsycl.so.9` from `compiler/2026.0`); and those `vars.sh`
scripts consume the shell's positional parameters when sourced, so the
entrypoint saves its arguments first. The build took about 10 minutes of
compile on eight cores after the package fetch. A separately labelled
compatibility rebuild with the host's oneAPI 2026.1.1 compiler (`llama-server`
SHA-256 `26fc4868e496ebdb93724b64f0e228c75bb6317129eaf5b942a281673f1b8fb4`)
also enumerates both cards. The record gate replays for both binaries are in the "Headline Result"
section above (2026-09-07).

## Reproduce

The wrapper below runs the strict final gate. Pick a free GPU/port pair.

```bash
cd /path/to/b70-optimization-lab
LLAMA_SERVER=/path/to/build/bin/llama-server \
MODEL=/models/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
MTP_DRAFT_MODEL=/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
DRAFT_SHA256=<sha256-printed-by-prepare-draft> \
GPU_INDEX=0 PORT=19350 \
  CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1 \
  CANARY_REPEATS=128 MAX_TOKENS=512 \
  REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
  LABEL=gemma4-q8-gpu0-125repro-$(date -u +%Y%m%dT%H%M%SZ) \
  bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Equivalent local helper:

```bash
LLAMA_SERVER=/path/to/build/bin/llama-server \
MODEL=/models/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
MTP_DRAFT_MODEL=/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
DRAFT_SHA256=<sha256-printed-by-prepare-draft> \
GPU_INDEX=0 PORT=19350 \
  bash repro/gemma4-26b-a4b-q8-b70-125tps-20260701/run.sh
```

The run writes:

- `data/<LABEL>/summary.json`
- `data/<LABEL>/realistic-suite.json`
- `data/<LABEL>/chat-canary.json`
- the server log under `SERVER_OUT_DIR`. The harness default is the lab's
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/`, and the server
  launcher also creates `OUT_DIR` with the same default, so on any other
  machine set both to a folder you can write.

Only promote or submit results when `realistic_final_gate.passed=true`,
`fresh_response_validity.valid=true`, and all `cached_tokens` values are zero.

## What Worked

- Use UD-Q8_K_XL as the target/verifier. The switch to `Q8_0` was not the
  quality-preserving headline lane.
- Keep the Q4_0 draft only as a verified MTP draft source. The Q8 target still
  verifies accepted tokens.
- Keep one full Gemma replica per B70 for research. Four independent GPUs were
  more useful than tensor-parallel PCIe sharing for this model.
- Reordered-Q8 VDR2 plus selected-down fused weighted-sum was the major
  target-side source win.
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, bulk sampled-ID verifier host read,
  FA-on 32K/VMM, and final post-norm residual fusion each contributed to the
  promoted family.
- Use same-window A/B or cross-over runs for small changes. The record family
  has enough variance that single-run micro-claims are unreliable.

## What Did Not Count As Headline Throughput

- Synthetic filled-long rows, even when `cached_tokens=0`, are diagnostic only.
- Repeated-prompt or warmed n-gram/history rows are not fresh-response
  throughput.
- Prompt-processing and long-context service wins are separate from the short
  LocalMaxxing headline. They must pass their own exact long-context gates and
  then rerun the short guard to prove no decode regression.

## Variance And Fairness

The current reliability protocol measured same-GPU full512 repeats under
temperature telemetry and found several-percent natural spread without thermal
throttling. Active core stayed around `77-78 C`, memory around `86-90 C`, and
frequency stayed near max. The no-spec calibration workflow measured a p90
same-identity pairwise spread around `4.4%`; use the no-spec calibration
workflow or a four-GPU same-window A/B when a candidate lands inside that
range.

See:

- `../../results/gemma4-26b-a4b-q8-b70/reliability-protocol.md`
- `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`
- `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-lmhead1col-subgroups.md`

## Prompt Processing And 32K Context

The short record uses `CTX_SIZE=32768`, `FLASH_ATTN=on`, and VMM, but it is
still a short-decode headline. The validated service/prompt-processing recipe
is tracked separately:

- `../gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`
- `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-current-service-context-ladder.md`
- `../../data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json`

That service recipe uses `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
SWA left-bound, KQ register/broadcast, phase prefill ubatch `2048`, 32K
context, FA on, and VMM. It passed exact long-context JSON validation with
`cached_tokens=0`, but it is not a short-decode record replacement.

### October 10: actual lengths in the 16K-slot sweep

The [draft-3 sweep](../../data/profiles/2026-10-10/gemma-sweep/single-16k-draft3.json)
and [no-draft sweep](../../data/profiles/2026-10-10/gemma-sweep/single-16k-draft0.json)
use actual server prompt counts on the graph's x axis. Earlier graphs used
requested lengths; the values below correct those coordinates without
changing any measured rates. Requested counts remain metadata in the package.

| Requested input tokens | Actual input tokens | Prefill, draft 3 (tok/s) | Prefill, no draft (tok/s) | Samples per setting |
| ---: | ---: | ---: | ---: | ---: |
| 300 | 292 | 933.9 | 937.4 | 3 |
| 512 | 509 | 1,323.8 | 1,327.8 | 3 |
| 2,048 | 2,042 | 2,061.5 | 2,050.1 | 3 |
| 8,192 | 8,185 | 1,697.7 | 1,705.1 | 2 |
| 15,800 | 15,793 | 1,488.3 | 1,495.2 | 2 |

These are median server prompt-counter rates with deterministic oneDNN,
prefill micro-batch 2048, f16 KV, one 16K slot and 256-token response caps.
Each request disables prompt reuse and records zero cached tokens. The
509-token result is not relabeled as a measured 512-token result.

### October 15: production prompt-reading profile

The package also includes a separate measured curve for the production
compatibility build with deterministic oneDNN, prefill micro-batch 1024,
no draft, f16 KV, and one 32,768-token slot. It ran on card 1 of the
two-B70 host while the LAN service used card 0. These controls differ from
the July curve and October 10 16K-slot sweep; their points are kept separate.

| Actual input tokens | Mean prefill (tok/s) | Observed range (tok/s) | Samples |
| ---: | ---: | ---: | ---: |
| 1,867 | 1,307.54 | 1,305.68–1,310.50 | 4 |
| 7,623 | 1,167.81 | 1,167.49–1,168.01 | 4 |
| 29,400 | 909.27 | 909.07–909.40 | 4 |

Each point averages two timings on each of two fresh servers. The rate is
the server's `prompt_n * 1000 / prompt_ms`, from full-precision JSON receipts,
not prompt length divided by time to first token. The same diagnostic long
prompts were repeated with `cache_prompt=false`, `--cache-ram 0`, and
`--ctx-checkpoints 0`; timed requests asked for one generated token after
the suite and long-output checks. This is a prompt-reading diagnostic,
not the varied cold-suite decode headline. A 512-token prefill point was
not measured under these controls.

The [derived evidence summary](../../experiments/gemma4-26b-a4b-q8-b70/data/2026-10-15-prefill-reorder/publication-summary.json)
retains every timing, its source hash, and the aggregation. Check it locally
without loading a model:

```bash
python3 experiments/gemma4-26b-a4b-q8-b70/scripts/summarize-prefill-reorder.py
```

### October 15 coalesced conversion: measured, not shipped

The separately built conversion kernel read the same prompts **21.49%,
19.23%, and 13.20% faster**, respectively. The retained JSONs reproduce
12/12 suite token matches for new-a versus production-a, and 3/3 long-prompt
token matches for production-b, new-a, new-b and verification versus
production-a. The log records the remaining suite comparisons and 524,288
byte-compared conversion calls with no mismatches. These are scoped
experimental results; the package runtime and its decode headline do not
include this change.

The [conversion delta](../../experiments/gemma4-26b-a4b-q8-b70/data/2026-10-15-prefill-reorder/convert-change-vs-production.diff)
and [preregistered experiment/results](../../experiments/gemma4-26b-a4b-q8-b70/notes/2026-10-15-prefill-reorder-check.md)
are retained. The latter pins only abbreviated test-build binary hashes
(`c2bddf55…` server, `8f416c95…` shared library). An exact compatibility
source/build receipt, full binary/library digests and tracked long-prompt
inputs are still missing. A delta against an unidentified production tree
does not close a public build. The historical runner also moves and restores
host services; it is evidence, not a current replay command.

Before publishing the faster profile, close those inputs and the patched
build, then retain a clean rebuild and full quality/performance replay under
that separately declared identity. The first attempt's `speed-check-*`
files used different settings and cannot supply this curve. Neither service
adoption nor changing a flag alone satisfies the missing build/replay gates.
