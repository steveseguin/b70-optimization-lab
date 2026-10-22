# Nemotron 3.5 Lightning 30B-A3B — candidate recipe; strict replay deferred

> **Integrity status, 2026-10-20: strict headline pending; replay deferred.**
> The historical raw suites, canaries and logs are now
> [imported and hash-bound](../../data/nemotron35-operating-points-20260822/manifest.json).
> These text-delta observations do not satisfy the native token-ID strict replay.
> The October19 attempt was interrupted, with no qualified result; the owner
> deferred another attempt. See the [incident review](../../notes/2026-10-19-nemotron-stock-headline-window.md).
> No speed headline or new LocalMaxxing submission is authorized by this import.

Status: **intake verified (direct+ordinary I/O) and baseline PASSED**
(2026-08-22) — the family runs on Intel B70 with no NVFP4 assumption.
Lane: mid MoE.

NVIDIA Nemotron 3.5 Lightning 30B-A3B in Unsloth's UD-Q4_K_M GGUF on one Intel
Arc Pro B70, for one user. It runs stock upstream llama.cpp built for SYCL; no
lab patch is needed. About 3B of its parameters are active per token. This is
a reconstruction recipe, not a clean-host certification or the exact
historical binary.

## Before you start

| Need | Tested with / required |
| --- | --- |
| OS | Linux. Distribution and kernel version: not recorded. No fresh-install test yet. |
| Driver stack | Intel GPU kernel driver, Level Zero runtime and IntelLLVM/oneAPI 2026.0.0 at `/opt/intel/oneapi` (`setvars.sh` must exist). Driver and runtime versions: not recorded. |
| Runtime / build | Native build from source: stock upstream [llama.cpp](https://github.com/ggml-org/llama.cpp) at `9fee29e9435f865ec0b811a783a6471a136d9317`, SYCL AOT for `bmg_g31`, no project patches. Use a dedicated source/build directory. |
| Tools | `git`, `cmake`, `ninja`, `curl`, `python3` and `huggingface-cli`. Python version: not recorded. |
| Disk | `NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf`, about 25.3 GB. Source and build size: not recorded. |
| Host RAM | At least 32 GiB (package manifest). Do not use the old 12/14 GiB memory-limited campaign wrapper on a small-RAM host or disable earlyoom to bypass its process scan. |
| GPU | One idle B70. Card 0 by default (`ONEAPI_DEVICE_SELECTOR=level_zero:0`); change the `0` to use another card. |
| Card memory | The run receipts do not record the card's ECC setting. With ECC on, a B70 shows about 28 GB instead of 32 GB, and this recipe was not tested that way. See [B70 ECC and usable VRAM](https://neural.download/learn/b70-ecc-and-vram.html). |

Background reading: [models](https://neural.download/learn/models.html) (dense
versus mixture-of-experts), [runtimes](https://neural.download/learn/runtimes.html)
and [context length](https://neural.download/learn/context-length.html).

## Quick start

Clone this repository and run every command below from its root. Replace every
`/path/to/...` with your own absolute directories.

```bash
git clone https://github.com/steveseguin/b70-optimization-lab.git
cd b70-optimization-lab

export MODEL_DIR=/path/to/verified/model
export LLAMA_SRC=/path/to/llama.cpp-9fee29e
export BUILD_DIR="$LLAMA_SRC/build-sycl-aot-bmg-g31"
```

### 1. Download and verify the model

```bash
huggingface-cli download unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF \
  NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf \
  --revision f2d3fe3694501008786e81e5f20360cbf715496a \
  --local-dir "$MODEL_DIR"

python3 scripts/verify-neural-download-model.py \
  repro/nemotron-35-lightning-30b-a3b-b70/model-manifest.json "$MODEL_DIR"
```

The verifier reads the file twice, once bypassing the page cache and once
normally. Both SHA-256 digests must equal
`edcb5d4650796ed2fb412498de6f83b585862312c747ddb74f0ea04b22206181`; it prints
`OK` and exits 0 when they do.

### 2. Get the runtime

```bash
git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_SRC"
git -C "$LLAMA_SRC" checkout 9fee29e9435f865ec0b811a783a6471a136d9317

source /opt/intel/oneapi/setvars.sh --force
# LLAMA_SRC must contain upstream commit 9fee29e9435f865ec0b811a783a6471a136d9317.
test "$(git -C "$LLAMA_SRC" rev-parse HEAD)" = 9fee29e9435f865ec0b811a783a6471a136d9317
cmake -S "$LLAMA_SRC" -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=icpx -DCMAKE_C_COMPILER=icx \
  -DGGML_SYCL=ON -DGGML_SYCL_F16=ON -DGGML_SYCL_DEVICE_ARCH=bmg_g31 \
  -DLLAMA_CURL=OFF
cmake --build "$BUILD_DIR" --target llama-server llama-bench --parallel 2
```

A new build is a new runtime identity: keep its toolchain versions, binary
hashes and validation results. Build time: not recorded.

### 3. Start the server

```bash
source /opt/intel/oneapi/setvars.sh --force
export ONEAPI_DEVICE_SELECTOR=level_zero:0
"$BUILD_DIR/bin/llama-server" \
  --model "$MODEL_DIR/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf" \
  --alias nemotron --reasoning off --ctx-size 8192 \
  --cache-type-k f16 --cache-type-v f16 --device SYCL0 --gpu-layers 99 \
  --split-mode none --flash-attn auto --parallel 1 --cache-ram 0 \
  --ctx-checkpoints 0 --no-cache-prompt --slot-prompt-similarity 0 --fit off \
  --metrics --no-webui --host 127.0.0.1 --port 18100 \
  >nemotron-server.log 2>&1 &
echo $! >nemotron-server.pid
```

This is the package's `launch` command. It starts the server in the background, writes its log to
`nemotron-server.log` and its process ID to `nemotron-server.pid`: one slot,
8,192 tokens of context, F16 KV, reasoning off, prompt caching off, port 18100.

This background shell example does not promise survival after disconnecting
the session. For a remote run, use an explicitly configured detached service
with no restart policy and retain its unit definition and output.

### 4. Wait until it is ready

```bash
until curl -fsS http://127.0.0.1:18100/health; do sleep 10; done
```

Wait for readiness in the log; do not restart on a failed health request. In
the three August 22 lab server logs the server was listening 16-46 seconds
after start ([example log](../../data/nemotron35-operating-points-20260822/nemotron-35-lightning-std.serverA.log)).

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"nemotron","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64}'
```

From Python, with any OpenAI-compatible client (`pip install openai`):

```bash
python3 -c 'from openai import OpenAI; r = OpenAI(base_url="http://127.0.0.1:18100/v1", api_key="unused").chat.completions.create(model="nemotron", messages=[{"role": "user", "content": "Say hello in five words."}], max_tokens=64); print(r.choices[0].message.content)'
```

Any other OpenAI-compatible app works the same way: base URL
`http://127.0.0.1:18100/v1`, model `nemotron`, any API key. The server holds
one model, so the name is only a label (the launch sets it with `--alias`).
The package benchmark sends plain completions (`--api-mode completions`), not
chat requests.

### 6. Check status

```bash
curl -fsS http://127.0.0.1:18100/health
pgrep -ax llama-server
tail -n 20 nemotron-server.log
```

There is no separate status script. An exploratory suite uses the package's
`benchmark` command:

```bash
python3 scripts/bench-openai-realistic-suite.py --base-url http://127.0.0.1:18100 --model nemotron \
  --api-mode completions --suite repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json \
  --max-tokens 512 --metric-tokens 100 --seed 1 \
  --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}' --out bench.json
```

Strict promotion instead requires the registered native-raw protocol, full
token IDs and two independent qualified attempts. The archived stock-headline
runner has unsafe historical memory/process handling and is not an approved
current launch path.

### 7. Stop

After work finishes, verify that the saved PID still belongs to this launch
(`ps -p "$(cat nemotron-server.pid)" -o args=` should show this
`llama-server` command), then stop it gracefully:

```bash
kill -TERM "$(cat nemotron-server.pid)"
```

Then `pgrep -x llama-server` must print nothing.

## What you get

- **Speed:** no strict headline (see the box at the top). Historical
  August 22 observation at the standard operating point (8K ctx, f16 KV,
  target-only), two fresh-server runs of the 12-prompt suite with 512-token
  responses, conventional 99-interval median, `cached_tokens=0` verified per
  request: run A **`72.169452 tok/s`**, run B **`72.035976 tok/s`**
  ([run A](../../data/nemotron35-operating-points-20260822/nemotron-35-lightning-std.benchA.json),
  [run B](../../data/nemotron35-operating-points-20260822/nemotron-35-lightning-std.benchB.json)).
  The metric uses OpenAI text-delta events; native token IDs were not
  retained. The intake diagnostic baseline (1x B70, 8K ctx, f16 KV,
  target-only, 128/100 window, cache-zero verified) was `72.873 tok/s` median /
  `72.712` p10.
- **Quality:** the reasoning-off canary battery (8x repeat hash-stability,
  arithmetic, exact copy, JSON schema) passed. Only **1 of 12** complete
  text-output hashes match between the two suite runs, so a strict full-suite
  repeat claim is not made. With reasoning on, 8x repeat outputs were not
  hash-stable; the recipe defaults to reasoning off.
- **Context:** the launch serves 8,192 tokens of a 1,048,576-token native
  window. Raw-engine decode was measured at depths up to 32,768 tokens
  ([table](#context-depth-sweep-llama-bench-raw-engine-rates-fa-on-5-reps));
  those are `llama-bench` rates, not server rates.
- **One card:** a two-card layer split was about 3.7% slower for one user.
- **Not measured yet:** tested clean-host platform installation; context
  beyond 32K of the 1M native window; native-token-ID strict two-attempt
  replay and promotion attestation (owner deferred after interrupted
  October19 attempt); standard 512-input-token prefill and measured multi-user
  performance; clean-source runtime reproduction qualified against the
  historical binary/toolchain identity.

## If it fails

- **The verifier prints `BAD` or exits 1:** the file is missing or its bytes
  differ from the pinned SHA-256. Delete it, download it again and re-run the
  verifier. Never start the server on unverified files.
- **The verifier exits 2 (`cannot bypass page cache`):** it could not read the
  file while bypassing the page cache, so it refuses to certify the bytes. Put
  the model on a local filesystem that allows direct reads.
- **The `test ... rev-parse HEAD` line in step 2 exits with an error:**
  `$LLAMA_SRC` is not at the pinned upstream commit. Check out
  `9fee29e9435f865ec0b811a783a6471a136d9317` before building.
- **Health fails while the model loads:** wait and read `nemotron-server.log`.
  Do not restart on a failed health request.
- **earlyoom gets in the way on a small-RAM host:** the lab hit a broad
  earlyoom process-name match with the old 12/14 GiB memory-limited campaign
  wrapper (see the incident review linked at the top). Do not disable earlyoom
  and do not use that wrapper; use the plain launch in step 3 on a host with
  at least 32 GiB of RAM, as the package declares.
- **The same prompt gives a different answer between runs:** recorded for this
  runtime (1 of 12 complete outputs matched across two servers; reasoning on is
  less stable). Keep reasoning off.
- **The server stopped when you disconnected:** the background shell launch
  does not promise survival after the session ends; see step 3 for remote runs.
- Keep `nemotron-server.log` and any benchmark JSON when you report a problem.

## Details

### Identity

| Field | Value |
| --- | --- |
| Model | NVIDIA Nemotron 3.5 Lightning 30B-A3B, arch `nemotron_h_moe` (hybrid Mamba-family, 53 blocks, 128 experts / 6 used, embed 2688, native ctx 1,048,576; official base `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`) |
| File | `NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf` |
| SHA-256 | `edcb5d4650796ed2fb412498de6f83b585862312c747ddb74f0ea04b22206181` |
| Source | `unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF` @ `f2d3fe3694501008786e81e5f20360cbf715496a` |
| Lab storage | `/mnt/usb-models/llm-models/nemotron-3.5-lightning-30b-a3b-udq4km/` on the lab host (catalog id `nemotron-35-lightning-30b-a3b-udq4km`); use any local directory |
| Base | upstream llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`, SYCL AOT bmg-g31, IntelLLVM 2026.0.0 |
| Device | 1x Intel Arc Pro B70 (32 GiB); 2x comparison later |

Question this packet answers: does the family run on Intel B70 without
assuming NVIDIA's NVFP4 runtime works there.

### Measurement coverage

| Measurement | Retained evidence / gap |
| --- | --- |
| 512-cap decode | Historical August22 text-delta A/B below; strict token-ID replay deferred |
| Standard 512-input-token prefill | Not measured; pp2048 is a separate raw-engine diagnostic |
| Context scaling | Seven measured raw-engine depths below, through 32K |
| Multi-user concurrency | Not measured; two-card layer split is not a concurrency test |
| Repeat/quality | Historical reasoning-off canaries retained; strict full-output replay pending |
| Clean-host build | Not certified; new builds must retain toolchain, binary hashes and validation |


### Context-depth sweep (llama-bench raw engine rates, fa on, 5 reps)

![depth sweep](depth-sweep.svg)

| Depth | decode tg128 tok/s (±σ) | prefill pp2048 tok/s (±σ) |
|---:|---:|---:|
| 0 | 73.01 (±0.01) | 1260.0 (±5.7) |
| 2,048 | 72.42 (±0.01) | 1166.9 (±3.2) |
| 4,096 | 71.85 (±0.01) | 1153.1 (±2.0) |
| 8,192 | 70.70 (±0.01) | 1145.6 (±3.8) |
| 16,384 | 68.56 (±0.02) | 1106.1 (±4.6) |
| 24,576 | 66.55 (±0.02) | 1102.6 (±1.3) |
| 32,768 | 64.62 (±0.01) | 1018.9 (±2.1) |

Raw engine rates run above server-suite medians by design (no HTTP/sampling); use the suite median as the serving expectation and this curve for the depth trend. Evidence: `nemotron-35-lightning.sweep.json` + `nemotron-35-lightning.meta.json` (model/bench shas inside).

### Historical candidate operating point: standard (8K ctx, f16 KV, target-only)

Two fresh-server runs, 12-prompt suite, 512-token responses,
conventional 99-interval median computed from raw event offsets,
`cached_tokens=0` verified per request:

- run A: **`72.169452 tok/s`**
- run B: **`72.035976 tok/s`**

Evidence: [run A](../../data/nemotron35-operating-points-20260822/nemotron-35-lightning-std.benchA.json), [run B](../../data/nemotron35-operating-points-20260822/nemotron-35-lightning-std.benchB.json), and the [hash manifest](../../data/nemotron35-operating-points-20260822/manifest.json). The metric here uses OpenAI text-delta events; native token IDs were not retained.
Only **1 of 12** complete text-output hashes matches between these two suite files.
That prevents a strict full-suite repeat claim even though the historical canaries passed.
The imported manifest records this comparison; the token-ID replay remains deferred.

Canary battery (reasoning off, temp 0, objective checks): 8x repeat hash-stability PASS, arithmetic PASS, exact copy PASS, JSON schema PASS — **pass_all=True** (`nemotron-35-lightning-std.canaries.json`).
Known behavior: with reasoning ON, 8x repeat outputs were not hash-stable (thinking-channel sampling); the retained reasoning-off canary passed its eight repeats. This is not a full-suite determinism proof. Recipe defaults to reasoning off for reproducibility-sensitive use.

### Two-card comparison (layer split, GPUs 0+1)

Same protocol, `--split-mode layer` across two B70s:
run A **`69.445407 tok/s`**, run B **`69.485984 tok/s`** (canaries 5/5).
That is ~3.7% BELOW the one-card point (72.17/72.04). **Recommendation:
one card** for single-stream serving. Evidence:
`nemotron-35-lightning-tp2.bench{A,B}.json`.
