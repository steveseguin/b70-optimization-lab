# Run Qwen3.8 27B AutoRound INT4 on two B70s

devan-carlin's AutoRound INT4 copy of Qwen3.8-27B, served by vLLM XPU in Docker on **two Intel Arc Pro B70 (32 GiB)**
cards. The model's own MTP draft guesses four tokens ahead and the full model checks every guess. On the lab's fixed
12-prompt test the answers were identical to running without drafting. This is a 4-bit quantized model, not the
official FP8 release.

> **Status: candidate.** The model, image, launcher and evidence are pinned. The recipe remains a candidate with
> clean-host replay pending.

## Before you start

| Need | Tested with / required |
| --- | --- |
| Cards | Two Intel Arc Pro B70 32 GiB with nothing else running on them. The launcher uses cards 0 and 1 (`XPU_DEVICE_MASK=0,1`; inside the container that becomes `ZE_AFFINITY_MASK=0,1` and `ONEAPI_DEVICE_SELECTOR=level_zero:0,1`). It does not check whether another program is using the cards. |
| OS and kernel | Linux. The exact OS, kernel and driver versions of the R304 runs are not recorded in this package's evidence. |
| GPU driver stack | An Intel GPU kernel driver (`xe` or `i915`) exposing `/dev/dri` render nodes; versions not recorded. The container brings its own user-space runtime (vLLM 0.29.0). |
| Runtime | Docker image `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2` (R304). |
| Python | `python3` on the host for the download, relabel and verify scripts (standard library only); version not recorded. |
| Host RAM | At least 15 GiB (16,106,127,360 bytes) and 20 GiB of RAM plus swap (package manifest). The launcher caps the container at 12 GiB of memory and 16 GiB of memory plus swap. |
| Disk | 19,016,930,167 bytes (about 19 GB) for the model. The relabel folder is hard links, so it adds almost nothing. Image and compile-cache sizes: not recorded. |
| Network / oneCCL | Internet access to Hugging Face and GitHub Container Registry for steps 1 and 2 (`HF_TOKEN` is used if set). Between the cards the launcher sets oneCCL over loopback TCP inside the container (`CCL_ATL_TRANSPORT=ofi`, `FI_PROVIDER=tcp`, `FI_TCP_IFACE=lo`, `CCL_ZE_IPC_EXCHANGE=pidfd`, `CCL_TOPO_P2P_ACCESS=1`). |
| Other tools | Docker that your user can run, and `curl`. `aria2c` is used for large downloads when installed. |

This package does not install host drivers or Docker, and their installation has not been replayed on a clean host.
To check the machine first, run `PROFILE=two-gpu packages/qwen38-27b-int4-fixed-k-tp2-b70/scripts/preflight.sh`
(GPUs, driver, RAM, storage, image). That check also requires the Docker Compose plugin.

## Quick start

Run every command from the repository root after
`git clone https://github.com/steveseguin/b70-optimization-lab && cd b70-optimization-lab`. Replace every
`/path/to/...` with your own absolute directories.

### 1. Download and verify the model

```bash
packages/qwen38-27b-int4-fixed-k-tp2-b70/scripts/download-model.sh \
  /path/to/qwen3.8-27b-int4-autoround /path/to/qwen3.8-27b-int4-autoround-gptq-relabel
MODEL_DIR=/path/to/qwen3.8-27b-int4-autoround-gptq-relabel packages/qwen38-27b-int4-fixed-k-tp2-b70/scripts/verify.sh
```

The first command downloads `devan-carlin/Qwen3.8-27B-int4-AutoRound` at revision
`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`. It then builds the **relabel** folder: the same tensor files as hard
links, with `config.json` and `quantization_config.json` rewritten so vLLM uses the oneDNN INT4 kernel path this
recipe was measured on (see [What makes it exact](#what-makes-it-exact)). Hard links need both folders on the same
filesystem. The second command checks the revision, every file size and every SHA-256. Serve the relabel folder, not
the download folder.

### 2. Get the runtime

```bash
docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2
docker tag ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2 \
  neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304
IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304 \
EXPECTED_XPU_EXTENSION_SHA256=bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932 \
EXPECTED_XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 \
EXPECTED_LAYERNORM_SHA256=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh mtp1-serial-fa-split-gdn \
  neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304
```

The launcher looks for the local tag, so the `docker tag` line is required. The contract check prints
`IMAGE CONTRACT PASS` when the installed files match the published image. These lines are the package's `preflight`
command without its last part, the relabel, which step 1 already ran (re-running it is safe).

### 3. Start the server

```bash
PORT=18134 MTP_DEPTH=4 XPU_GRAPH=1 DRAFT_HEAD_INT4=1 CLASSPAD=0 \
DRAFT_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
MODEL_DIR=/path/to/qwen3.8-27b-int4-autoround-gptq-relabel VLLM_CACHE_DIR=/path/to/new-runtime-cache \
  repro/qwen38-27b-autoround-int4-b70/scripts/run-fixed-k-mtp-server.sh
```

The server runs in the foreground; leave this terminal open. Before it starts, the launcher checks the model files
again and the image identity. The container is named `qwen38-int4-fixed-k-mtp4` and serves the model name
`qwen38-int4-fixed-k-mtp4` (both follow `MTP_DEPTH`).

Context: with no `MAX_MODEL_LEN` set, the shared launcher allows **256 tokens per request** (prompt plus answer) and
up to 128 requests at once. The single-user record ran with `MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1`; put those in front
of the command to match it. Long inputs up to 32,768 tokens were measured with one request at a time
(`MAX_MODEL_LEN=33024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=4096`) on the earlier R256 image (R260b, below).

### 4. Wait until it is ready

```bash
until curl -fsS http://127.0.0.1:18134/health; do sleep 10; done; echo ready
```

Startup loads the weights, compiles and captures XPU graphs. Its duration is not recorded for this profile.

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18134/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-int4-fixed-k-mtp4","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64,"chat_template_kwargs":{"enable_thinking":false}}'
```

With the OpenAI Python client (`pip install openai`):

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18134/v1", api_key="unused").chat.completions.create(model="qwen38-int4-fixed-k-mtp4", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64, extra_body={"chat_template_kwargs": {"enable_thinking": False}}); print(r.choices[0].message.content)'
```

Any OpenAI-compatible client works with base URL `http://127.0.0.1:18134/v1` and model `qwen38-int4-fixed-k-mtp4`.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18134/health && echo healthy
docker ps --filter name=qwen38-int4-fixed-k-mtp4
```

### 7. Stop

```bash
docker stop -t 30 qwen38-int4-fixed-k-mtp4
```

Run it from another terminal. The container was started with `--rm`, so Docker removes it after it stops. The
compile cache in `VLLM_CACHE_DIR` stays.

## What you get

- **Speed, one user, two cards:** the best qualified two-card MTP4 shortlist record is **117.528 tok/s** (R299 on
  R294b, strict pair 117.46/117.59; approved LocalMaxxing
  [`cmtyqbeu40aqgps011wl4mljo`](https://www.localmaxxing.com/runs/cmtyqbeu40aqgps011wl4mljo)). The current R304 /
  vLLM v0.29.0 recipe revalidates at **117.24/116.95** on two cards, G1/G2/G3 12/12. These are class-balanced
  writing speeds on the fixed 12-prompt, six-class suite with a 512-token answer cap and zero cached tokens
  ([evidence](../../experiments/qwen38-27b-b70/data/2026-09-05-qwen38-int4-graph-capture-tp2-mtp4-r247-result.json)).
- **Reading a prompt, two cards:** a September 13 diagnostic screen on the R304 image (TP2, MTP4, one user, 1,024-token
  capacity, average of two control arms) measured **2,198 input tokens/s** server prefill at 512 input tokens and
  247.81 ms HTTP time to first token. It is not a promoted measurement; see the [short-prefill note](../../experiments/qwen38-27b-b70/notes/2026-09-13-short-prefill-results.md).
- **Long inputs:** context depth (R260b, 2026-09-06, R256 image): exact real-content active context 2K-32K, one slot:
  MTP0 50.0 -> 42.8 tok/s, MTP depth 4 120.6 -> 100.3 tok/s (medians of three content classes), every MTP4 array
  equal to the MTP0 oracle (18/18)
  ([evidence](../../experiments/qwen38-27b-b70/data/2026-09-06-qwen38-int4-r256-real-content-depth-r260b-result.json)).
- **Many users:** concurrency has separate gates: on R304, TP1 MTP4 is exact through eight users in both passes
  (272.7 tok/s warm); TP1 MTP0 is exact through 64 users, with its best measured aggregate at 32 (513.2 tok/s warm).
  TP2 MTP4 has mismatches at some rungs; TP2 MTP0 is exact through 32 in both passes. The historical R299 shortlist
  profile was exact through 16 with MTP4. See the exact two-pass profiles in the
  [model page](https://neural.download/models/qwen38-27b-autoround-int4-b70.html#profiles). A strict single-user
  pass does not imply arbitrary concurrent equality.
- **One card:** the same image measures **81.17/81.16** tok/s on one card, G1/G2/G3 12/12; the one-card pair center
  is 81.163 tok/s (`TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 GPU_MEMORY_UTILIZATION=0.96`).
- **Not measured yet:** clean-host replay.

## If it fails

- **`image is missing: neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304`:** run step 2. The launcher
  needs the local tag, not only the pulled digest.
- **`image identity mismatch` or `image does not contain the required mixed-batch XPU kernel`:** the local tag points
  at a different image. Pull by digest and tag it again (step 2).
- **`container already exists: qwen38-int4-fixed-k-mtp4`:** an older server with that name is still present. Stop it
  (step 7) before starting a new one.
- **`IDENTITY MISMATCH on N file(s)`** from the model check: a file differs from the pinned revision. Re-run step 1
  and point `MODEL_DIR` at the relabel folder, not the download folder.
- **`CANNOT VERIFY`** from the model check: the verifier must read the files while bypassing the page cache and
  refuses to continue when the filesystem does not allow that (it was added after a fuseblk/NTFS-3G mount served
  corrupted cached bytes on 2026-08-20). Keep the model on a filesystem that supports direct reads.
- **Everything works but single-user speed is low:** vLLM 0.29.0 defaults to its V2 model runner, which skips the
  INT4 draft head (on the Qwen3.5 4B lane this gave 128 instead of 172 tok/s). The launcher pins
  `VLLM_USE_V2_MODEL_RUNNER=0`; do not override it
  ([R304 section](../../repro/qwen38-27b-autoround-int4-b70/README.md#rebased-onto-stock-vllm-xpu-v0290-with-three-upstream-fixes-r304-2026-09-13-11704--11709)).
- **The server refuses to boot with `VLLM_BATCH_INVARIANT=1`:** vLLM rejects that switch for the GDN attention
  backend. Leave it at `0`, as the launcher sets it.
- **The first two-request batch is slow:** it pays about 1.05 s of one-time recompilation. Send one two-user warm-up
  request after boot before measuring.
- **A GPU fault while the weights load** (`xe ... Fault response` or a device coredump in the kernel log, and a server
  that never becomes healthy): the lab saw weight-load faults and one copy-engine reset on this lane. It recorded them
  and rebooted before starting more servers. Do not restart in a loop
  ([R294 section](../../repro/qwen38-27b-autoround-int4-b70/README.md#the-draft-head-scores-a-shortlist-r294-r299r300-2026-09-12)).
- **Low host memory:** do not swap in the stock `intel/llm-scaler-vllm:0.21.0-b3.1` image. On a 16 GB host a 9 GiB
  container limit killed a worker during warmup and triggered a copy-engine reset
  ([historical open items](../../repro/qwen38-27b-autoround-int4-b70/README.md#open-items-from-the-august-2026-lane-historical)).

## All measured configurations

The matrix below preserves earlier configurations. The recipe remains a candidate with clean-host replay pending.

<!-- replication-matrix:begin (generated by tools/build-qwen38-int4-replication-matrix.py; do not edit by hand) -->

**Replication matrix (class-balanced median decode tok/s at one request, strict 12-prompt six-class suite, 512-token completion cap; identity ladder = c1-c64 exactness vs a sequential oracle, 128 tokens per request):**

| image | TP | MTP depth | XPU graph | draft head | strict pair (tok/s) | gates | identity ladder | run |
|---|---|---|---|---|---|---|---|---|
| R228 | 2 | 0 | off | FP16 | 34.21 / 35.64 | G1 12/12 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 64/64 | R239 |
| R228 | 2 | 1 | off | FP16 | 51.10 / 50.09 | G2 12/12, G3 12/12 x2, probe exact | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 30/32, c64 58/64 | R239 |
| R228 | 2 | 2 | off | FP16 | 61.14 / 61.54 | G2 12/12, G3 12/12, G3 12/12 | - | R239 |
| R228 | 2 | 3 | off | FP16 | 67.61 / 67.83 | G2 12/12, G3 12/12, G3 12/12 | - | R239 |
| R228 | 2 | 4 | off | FP16 | 68.55 / 67.79 | G2 12/12, G3 12/12, G3 12/12 | - | R239 |
| R228 | 2 | 0 | on | FP16 | 49.83 / 49.89 | G1 12/12; 12/12 vs eager oracle | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 64/64 | R253 |
| R228 | 2 | 1 | on | FP16 | 76.72 / 76.63 | G2 12/12, G3 12/12 x2, probe exact | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 12/16, c32 30/32, c64 61/64 | R253 |
| R228 | 2 | 4 | on | FP16 | 91.00 / 91.01 | G2 12/12, G3 12/12 x2 | c1 1/1, c2 2/2, c4 3/4, c8 7/8, c16 16/16, c32 30/32, c64 58/64 | R247/R251 |
| R228 | 2 | 5 | on | FP16 | 88.84 / 89.12 | G2 12/12, G3 12/12 x2 | - | R250 |
| R228 | 2 | 6 | on | FP16 | 84.06 / 83.98 | G2 12/12, G3 12/12 x2 | - | R250 |
| R228 (R257 pair; R256 identical code path) | 2 | 4 | on | INT4 draft-only | 112.36 / 112.33 | G2 12/12, G3 12/12 x2 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 31/32, c64 58/64 (warm pass; c32/c64 with the W4A16 pad forwarded off: R281 632.6 30/32, 603.7 62/64) | R257/R265b/R281 |
| R228 | 1 | 0 | off | FP16 | 32.96 / 32.95 | G1 12/12 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 64/64 | R239 |
| R228 | 1 | 1 | off | FP16 | 49.64 / 49.47 | G2 12/12, G3 12/12 x2, probe exact | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 15/16, c32 30/32, c64 60/64 | R239 |
| R228 | 1 | 2 | off | FP16 | 56.51 / 56.45 | G2 12/12, G3 12/12, G3 12/12 | - | R239 |
| R228 | 1 | 3 | off | FP16 | 58.47 / 58.47 | G2 12/12, G3 12/12, G3 12/12 | - | R239 |
| R228 | 1 | 4 | off | FP16 | 56.29 / 56.25 | G2 12/12, G3 12/12, G3 12/12 | - | R239 |
| R228 | 1 | 4 | on | FP16 | 56.91 / 56.90 | 12/12 all | - | R246b |
| R256 | 2 | 5 | on | INT4 draft-only | 109.97 / 110.07 | G2 12/12, G3 12/12 x2 | - | R258 |
| R256 | 2 | 6 | on | INT4 draft-only | 108.34 / 108.37 | G2 12/12, G3 12/12 x2 | - | R258 |
| R256 | 2 | 0 | on | n/a | - | MTP0 ladder | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 31/32, c64 64/64 | R259 |
| R266 | 2 | 4 | on | INT4 draft-only (V2 runner, R266) | 112.70 / 112.96 | G2 12/12, G3 12/12 x2 | c1 1/1, c2 2/2, c4 3/4, c8 8/8, c16 16/16, c32 31/32, c64 62/64 (warm pass) | R269/R270 |
| R276 (served since 2026-09-06 pm) | 2 | 4 | on (sizes to 320) | INT4 draft-only | 112.90 / 113.00 | G2 12/12, G3 12/12 x2 | c1 1/1, c2 2/2, c4 4/4, c8 7/8, c16 16/16, c32 30/32, c64 60/64 (warm pass) | R283/R282 |
| R293 (classpad on) | 2 | 4 | on (sizes to 320) | INT4 draft-only | 111.69 / 111.33 | G2 12/12, G3 12/12 x2 (own MTP0 pair) | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 30/32, c64 59/64 (warm pass) | R295 |
| R293 (classpad on) | 2 | 0 | on (sizes to 320) | n/a | 49.39 / 49.39 | G1 12/12 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 64/64 (warm pass) | R295 |
| R293 (classpad on) | 1 | 4 | on (sizes to 320) | INT4 draft-only | 73.19 / 73.25 | G2 12/12, G3 12/12 x2 (own MTP0 pair) | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 15/16, c32 29/32, c64 59/64 (warm pass) | R298 |
| R293 (classpad on) | 1 | 0 | on (sizes to 320) | n/a | 32.58 / 32.50 | G1 12/12 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 63/64 (warm pass) | R298 |
| R294b | 2 | 4 | on (sizes to 320) | INT4 draft-only, 67k shortlist (R294) | 117.46 / 117.59 | G2 12/12, G3 12/12 x2 (own MTP0 pair) | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 31/32, c64 62/64 (warm pass) | R299 |
| R294b | 2 | 0 | on (sizes to 320) | n/a | 50.01 / 50.04 | G1 12/12 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 64/64 (warm pass) | R299 |
| R304 (v0.29.0 rebase) | 2 | 4 | on (sizes to 320) | INT4 draft-only, 67k shortlist (R294) | 117.24 / 116.95 | G2 12/12, G3 12/12 x2 (own MTP0 pair) | c1 1/1, c2 2/2, c4 3/4, c8 8/8, c16 16/16, c32 31/32, c64 57/64 (warm pass) | R304 |
| R304 (v0.29.0 rebase) | 2 | 0 | on (sizes to 320) | n/a | 50.07 / 50.06 | G1 12/12 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 64/64 (warm pass) | R304 |
| R304 (v0.29.0 rebase) | 1 | 4 | on (sizes to 320) | INT4 draft-only, 67k shortlist (R294) | 81.17 / 81.16 | G2 12/12, G3 12/12 x2 (own MTP0 pair) | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 30/32, c64 58/64 (warm pass) | R304 |
| R304 (v0.29.0 rebase) | 1 | 0 | on (sizes to 320) | n/a | 33.10 / 33.08 | G1 12/12 | c1 1/1, c2 2/2, c4 4/4, c8 8/8, c16 16/16, c32 32/32, c64 64/64 (warm pass) | R304 |

**Settings common to every row:** vLLM 0.27.2rc1.dev77+gac7509e2b (XPU), `--dtype float16 --quantization gptq --kv-cache-dtype auto --block-size 64 --no-enable-prefix-caching --language-model-only`, `VLLM_BATCH_INVARIANT=0` (vLLM's own switch is off: the strict launchers pin it and vLLM refuses to boot the GDN backend with it on; batch invariance on this lane comes from the kernels and the switches below), `TORCHINDUCTOR_DETERMINISTIC=1`, `VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0`, `VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0`, `PYTHONHASHSEED=0`, `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`, `VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1`, `VLLM_XPU_GDN_NATIVE_FALLBACK=1`, `VLLM_XPU_FP8_BLOCK_W8A16=1` (inert on the gptq path), `VLLM_XPU_GDN_SPLIT_MIXED=1`, `VLLM_XPU_GDN_SPEC_GROUP=16`, `VLLM_XPU_FP16_LINEAR_ROWCHUNK=32` (R293 rows: `VLLM_XPU_FP16_LINEAR_CLASSPAD=1`, which replaces the 32-row pieces with one verified oneDNN M-class per weight shape), `VLLM_XPU_W4A16_DETERMINISM_PAD=0` (correction 2026-09-06: the launchers did not forward this switch until R278k, so every runner-launched ladder rung above 128 verify rows, i.e. c32/c64, ran with the R213b pad on; c1-c16 and the single-user headline were never affected; the R281 ladder below is the corrected measurement), `VLLM_XPU_ALLREDUCE_HOST_WAIT=1`, `VLLM_XPU_RMSNORM_TRITON=0`, `VLLM_XPU_GEMMA_RMSNORM_TRITON=0`, whole-graph `torch.compile` (`splitting_ops: []`) with `inductor_compile_config {deterministic: true, split_reductions: false, triton.autotune_pointwise: false, combo_kernels: false, benchmark_combo_kernel: false, benchmark_epilogue_fusion: false}`, oneCCL `CCL_ATL_TRANSPORT=ofi FI_PROVIDER=tcp CCL_ZE_IPC_EXCHANGE=pidfd CCL_SEND=direct CCL_RECV=direct CCL_TOPO_P2P_ACCESS=1` with the three `CCL_SYCL_*_SIMPLE_THRESHOLD=4294967296`, greedy decoding (`temperature 0`), speculative config `{"method":"qwen3_next_mtp","num_speculative_tokens":<depth>}` (omitted for MTP0). Model: `devan-carlin/Qwen3.8-27B-int4-AutoRound` bce40cac relabelled to plain gptq (manifest `model-gptq-relabel-r212.json`).

| setting | strict pairs (1 user) | identity ladders (c1-c64) |
|---|---|---|
| `--max-model-len` / context | 1024 | 256 |
| `--max-num-seqs` | 1 | 64 |
| `--max-num-batched-tokens` | 1024 | 512 |
| completion cap | 512 tokens (suite prompts 26-31 tokens, six classes) | 128 tokens, 64-prompt small-context suite |
| GPU memory utilization | TP2 0.95, TP1 0.96 | same |
| XPU graph on | `VLLM_XPU_ENABLE_XPU_GRAPH=1`, `cudagraph_mode FULL_DECODE_ONLY`, `cudagraph_capture_sizes [1,2,3,4,5,6,8]`, `max_cudagraph_capture_size 8` | same |
| XPU graph off | `VLLM_XPU_ENABLE_XPU_GRAPH=0`, `cudagraph_mode PIECEWISE`, `cudagraph_capture_sizes [1]` | same |
| draft head INT4 | `VLLM_XPU_DRAFT_LM_HEAD_INT4=1` (group 128, bf16 scales; R256 image or later) | same |
| TP1 | `TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0` (`ZE_AFFINITY_MASK=0`) | same |
| TP2 | `TENSOR_PARALLEL_SIZE=2 XPU_DEVICE_MASK=0,1` | same |

Images: R228 = `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:aaf920b04224cb3f4be881ae41dbef4fa7841f4ab26fbbe09e4e780fe361ff7d` (`_xpu_ops.py` sha256 c91d6b0d…, `_xpu_C.abi3.so` 271db0d4…); R256 = `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:f7696bcaefab1bc1c93e12cbde630b6e81bed8e00e41154ca2198e246c35dea3` (R228 + a draft-only INT4 head fallback whose branch is never taken on this model: the relabelled head is unquantized and already carries `make_xpu_int4_draft_copy`, so both images run the same code here; the container records show the R257 headline pair ran R228 and R258/R259/R260b/R265b ran R256); R276 = `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad` (`_xpu_ops.py` sha256 6ee6b8db…; R256 + the sync-free grouped GDN branch, served image since 2026-09-06 afternoon: graph capture to 320 tokens, lossless, +22%/+10% at c2/c4); R266 = `neural-download/vllm-openai-xpu:qwen38-int4-v2-draft-int4-head-r266 sha256:1d12b64e46f99a6092014319b2b66f14f380f24da82c6ce7b852db7ee6ebd10e (local; R256 + docker/r266-v2-draft-int4-head.py)` (V2 model runner variant, not the published path). Registry digest equals the local image id; pass it as `EXPECTED_IMAGE_ID` and the two file digests as `XPU_OPS_SHA256_OVERRIDE` / `XPU_EXTENSION_SHA256_OVERRIDE` (the launcher does this).

<!-- replication-matrix:end -->

**LocalMaxxing:** the depth-4 headline is approved as `cmtq3mx7e03gen701xxpwu67z` (112.344 tok/s, center of the R257 pair; ledger `results/localmaxxing-submissions.md`, attestation `experiments/qwen38-27b-b70/data/2026-09-06-qwen38-int4-r257-graph-drafthead-depth4-strict-result.json`).

## What makes it exact

| layer | problem | fix |
|---|---|---|
| kernel routing | `quant_method: auto-round` selects INC/ARK `woqgemm`: nondeterministic for 32-256 rows, never batch-invariant, 6-10x slower at two rows | relabel the identical tensors as plain `gptq` (`scripts/make-gptq-relabel.py`) -> oneDNN `int4_gemm_w4a16` |
| W4A16 GEMM | oneDNN picks a different K partition per row-count class | rebuilt `_xpu_C` pins a two-tier fixed-K strategy (R221 patch); decode unchanged, prefill GEMMs ~2x |
| FP16 linears (`lm_head`, `mtp.fc`) | oneDNN f16 GEMM changes class above 32 rows | `<=32`-row pieces in an opaque custom op (R224) |
| FP16 linears, many users | each `<=32`-row piece re-reads the 2.5 GB `lm_head`: a throughput tax above 32 rows | R293: `CLASSPAD=1` pads or splits every call into one measured, verified oneDNN M-class per weight shape (one weight read per step, rows bit-identical across batch sizes); off by default, R276 code path unchanged |
| attention decode | flash-decoding split count follows batch size | not pinned by vLLM's flag (`VLLM_BATCH_INVARIANT` stays 0: it refuses to boot the GDN backend); MTP0 identity holds through c64 without it (R222-R253 ladders) |
| compiled reductions | Inductor splits reductions by row count | `"split_reductions": false` |

The last known composition dependence is the GDN kernel (launch grouping does not restore single-request
arithmetic); it accounts for the c32/c64 near-tie flips with speculation.

## Run the strict benchmark

The package's `benchmark` command runs the fixed 12-prompt suite with a 512-token answer cap. It needs a server
started with the record's shape, `MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1` in front of the step 3 command (the default
256-token context is too small for it), and it reads the server address from `BASE_URL`:

```bash
BASE_URL=http://127.0.0.1:18134 OUT_DIR=/path/to/new-strict-attempt MODEL_NAME=qwen38-int4-fixed-k-mtp4 \
PROFILE_LABEL=int4-fixed-k-mtp4 repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

`OUT_DIR` must be a new directory. One run is measurement evidence, not a qualification: the published pairs compare
two fresh servers with each other and with a fresh MTP0 pair (`MTP_DEPTH=0`).

Other launcher settings: `MTP_DEPTH=0..4` selects the speculative depth (the served model and container names follow
it); `TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 GPU_MEMORY_UTILIZATION=0.96` runs one card; `CLASSPAD=1` is the
many-user FP16 linear (R293); `DRAFT_SHORTLIST=` (empty) scores every draft row (R294). The launcher verifies the
image contract, the rebuilt extension digest and the relabelled model manifest before serving.

## Docker Compose packet (alternative start)

A level-2 packet: the same digest-pinned R304 image (the runtime rebased onto stock vLLM XPU v0.29.0), explicit GPU
device mapping, read-only model and persistent cache volumes, and one- and two-card profiles (depth 4 with the INT4
draft head scoring the 67k shortlist: 117 tok/s on two cards, 81 on one). It differs from the quick start in operator
settings only: it serves the model name `qwen38-27b-int4`, uses port 18131 unless `PORT` is set (`env/two-gpu.env`
sets 18134), and allows 8,192 tokens with 16 requests at once. Those are packet defaults, not the strict-suite values.
Its `memswap_limit` is 20g, while the launcher uses 16g.

```bash
cd packages/qwen38-27b-int4-fixed-k-tp2-b70
# the model is the R212 plain-GPTQ relabel of devan-carlin/Qwen3.8-27B-int4-AutoRound; download builds it:
./scripts/download-model.sh /path/to/qwen3.8-27b-int4-autoround /path/to/qwen3.8-27b-int4-autoround-gptq-relabel
export MODEL_DIR=/path/to/qwen3.8-27b-int4-autoround-gptq-relabel

PROFILE=two-gpu ./scripts/preflight.sh     # GPUs, driver, RAM, storage, image
./scripts/verify.sh                        # revision, sizes, every SHA-256 (relabelled config included)
PROFILE=two-gpu ./scripts/smoke-test.sh    # start, health, and a repeat-identity gate
```

`smoke-test.sh` starts the service with `docker compose`, waits for health, sends one greedy request twice and
requires identical answers, then stops the service (`KEEP_UP=1` leaves it running).

`compose.yaml` is **generated, not hand-written**: `scripts/render-compose.sh` runs the real recipe launcher behind a
docker shim that captures the `docker run` argv, so the packet carries the measured container's environment and serve
command verbatim. The operator scripts are thin wrappers over `tools/container-packet/`, shared with the other packets.
`tools/check-container-packet.py` runs in CI and fails the build if the committed file stops matching the launcher, if
the image is not pinned by digest, if the model mount is not read-only, or if a port leaves loopback. Both profiles
passed the packet smoke test on 2026-09-13 (health plus repeat-identity gate) on the lab host.

Regenerate after any launcher change:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-int4-autoround-gptq-relabel ./scripts/render-compose.sh
```

Source of truth: [`repro/qwen38-27b-autoround-int4-b70/scripts/run-fixed-k-mtp-server.sh`](../../repro/qwen38-27b-autoround-int4-b70/scripts/run-fixed-k-mtp-server.sh).

## History

<details>
<summary>R294 and R293 (September 11-12, 2026), before the R304 rebase</summary>

### R294: the draft head scores a shortlist (2026-09-12)

The served image became R294b (R293 plus a draft-only lm_head that scores a 67,248-row token shortlist; the target
verifies every draft, so outputs cannot change). Single request, TP2, depth 4: **117.46 / 117.59 tok/s** against
112.74 on the same image scoring every row and the 112.90 / 113.00 headline above, G1/G2/G3 12/12 (R299/R300).
`DRAFT_SHORTLIST=` (empty) on the launcher restores the full head. LocalMaxxing `cmtyqbeu40aqgps011wl4mljo` at `117.528 tok/s` (approved 2026-09-12; the prior approved headline `cmtq3mx7e03gen701xxpwu67z` at 112.344 stands as the full-head figure). Rows R299 in the matrix; recipe README, R294 section.

### R293: class-consistent FP16 linears (2026-09-11)

The served image became R293 (R276 + `experiments/qwen38-27b-b70/docker/r290..r293-*.py`; with `CLASSPAD=0`, the
default, it runs R276's code path unchanged and reproduces the headline above). `CLASSPAD=1` removes the 32-row
re-read of the vocabulary projection: on this lane depth 4 gains 3-8% from eight users up (c16 611 / c32 683 / c64 628
tok/s against 579 / 635 / 589), MTP0 3-6% from 64 users up (1019 at c64, 1080 at c256), at a 1% single-user cost
(111.69 / 111.33 against 112.90 / 113.00), lossless by G1/G2/G3 regenerated on the same image, identity unchanged at
every rung. Two cards without speculation with a 5 ms admission stagger are byte-identical to the sequential oracle
over ten passes of 64 users (640/640, harness-certified) at 1014 tok/s. Rows R295-R298 in the matrix; detail in the
recipe README's R293 section. The 4B and 9B Qwen3.5 lanes, where the projection is a larger share of the step, gain
25-56% from the same switch.

</details>

The 2026-09-05 package named the R228 image
(`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:aaf920b0...`). The current launcher and every step above use
R304.

Evidence and rationale: [`repro/qwen38-27b-autoround-int4-b70/README.md`](../../repro/qwen38-27b-autoround-int4-b70/README.md)
(fixed-K profile section) and the notes under `experiments/qwen38-27b-b70/notes/2026-09-05-qwen38-int4-*`.
