# Qwen3.6-27B MTP Q4_K_M on Intel Arc Pro B70 (llama.cpp SYCL)

> **Community contribution.** This packet documents the independently deployed
> two-endpoint llama.cpp/SYCL service on `intel-b70` and preserves the existing
> llama-benchy measurements without rerunning them. Read `STATUS.md` for
> evidence boundaries.

## Recipe

Model: `Qwen3.6-27B-MTP-GGUF/Qwen3.6-27B-Q4_K_M.gguf` (Unsloth MTP GGUF).
The model file used by the service is 17,106,773,120 bytes. Record a SHA-256
and exact model revision before comparing another download.

The service uses llama.cpp commit `15586e2d7165570fb3aa7c26e0d442e289ef69de`
with a generic SYCL build (`build-sycl`). Use the generic JIT path; do not set a
Battlemage-specific AOT architecture unless its kernels have been validated at
model load.

### Per-GPU architecture

Run one independent server per physical B70; do not tensor-split:

| Instance | Physical GPU | Selector | Port |
|---|---:|---|---:|
| GPU 0 | 0 | `ONEAPI_DEVICE_SELECTOR=level_zero:0` | 8001 |
| GPU 1 | 1 | `ONEAPI_DEVICE_SELECTOR=level_zero:1` | 8002 |

Each process sees its selected physical device as `SYCL0`.

### Exact server flags

```text
--model /models/Qwen3.6-27B-MTP-GGUF/Qwen3.6-27B-Q4_K_M.gguf
--host 0.0.0.0
--port 8001                 # 8002 for GPU 1
--ctx-size 150000
--n-gpu-layers 99
--device SYCL0
--split-mode none
--main-gpu 0
--parallel 1
--batch-size 2048
--ubatch-size 2048
--cache-type-k f16
--cache-type-v f16
--cache-type-k-draft f16
--cache-type-v-draft f16
--flash-attn on
--spec-type draft-mtp
--spec-draft-n-max 2
--spec-draft-p-min 0.0
--temp 0.6
--top-p 0.95
--top-k 20
--min-p 0.0
--presence-penalty 0.0
--repeat-penalty 1.0
--fit off
```

Required environment:

```text
UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
GGML_SYCL_USE_LEVEL_ZERO_API=1
GGML_SYCL_ENABLE_FLASH_ATTN=1
GGML_SYCL_FA_ONEDNN=1
GGML_SYCL_ENABLE_GRAPH=0
```

Source `/opt/intel/oneapi/setvars.sh` before strict shell options. The
installed launcher is `/usr/local/bin/launch-llama-qwen36-27b-mtp.sh`; the
systemd units are `llama-qwen36-27b-gpu0.service` and
`llama-qwen36-27b-gpu1.service`. The unit files set the selector, port, context,
Flash Attention, MTP, and sampling defaults shown above.

## Hardware and runtime identity

- Host: `intel-b70`, Ubuntu 24.04.4 LTS
- Kernel: `6.17.0-1009-intel`
- GPUs: 2x Intel Arc Pro B70, 32 GiB each, `xe`
- Build commit: `15586e2d7`
- Endpoints: `:8001` and `:8002`
- KV cache: F16 for target and draft
- Context: 150,000 total server context; one slot per instance
- MTP: draft-MTP, two speculative tokens, `p_min=0.0`

## Reproduction

Start the persistent units after confirming model availability and accelerator
runtime setup:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now llama-qwen36-27b-gpu0.service
sudo systemctl enable --now llama-qwen36-27b-gpu1.service
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8002/health
```

Do not stop or replace an active service solely to reproduce this packet without
first checking the host's current work authority and GPU ownership.

## Existing llama-benchy data

The benchmark was previously run from the separate local repository
`/home/dom/llama-benchy`; it was not rerun for this contribution. The available
27B llama-benchy packet is the INT4/vLLM comparison run, not this llama.cpp
SYCL service, so it is preserved as related context rather than relabeled as a
llama.cpp measurement. See `STATUS.md` for that distinction.

The inspected historical 27B packet reports, for the separate vLLM service,
1,494.6 ± 107.7 pp tok/s and 46.3 ± 1.5 tg tok/s at depth 0, declining to
1,264.3 ± 1.6 pp and 14.9 ± 0.7 tg at depth 32768. These numbers are included
only to identify the artifact and are **not** claimed for this llama.cpp
recipe.

The prior llama.cpp benchmark record located in session history is the 35B
Q8/UD-Q8 lane, not this 27B service. It must not be copied into this packet as
27B evidence.

## Safety and scope

This is a community recipe, not a promoted `repro/` result. The service binds
`0.0.0.0` as currently deployed; protect it with the host firewall or change
`--host` to `127.0.0.1` for local-only use. Never commit credentials, model
weights, or private logs.

## Source

- Repository: <https://github.com/steveseguin/b70-optimization-lab>
- Benchmark tool: <https://github.com/dominick253/llama-benchy>
- Related prior llama.cpp packet: `community/dominick253-qwen36-35b-llamacpp-sycl/`
- Operations/session context: `@session:default/20260806_065933_add186`
- Earlier llama.cpp benchmark session: `@session:default/20260727_093033_7695fc`
- Exact public benchmark data must be added only after a matching 27B llama.cpp
  run is performed and its raw JSON/logs are preserved.

## Contributor statement

This contribution is submitted by `dominick253` under the repository license.
It contains no model weights, credentials, access tokens, or private user data.

---

## Maintainer note

The running service and exact launcher were inspected on 2026-08-07. The
historical benchmark material was checked separately. No benchmark was rerun,
and no claim is made here that the existing vLLM llama-benchy numbers represent
this llama.cpp service.

---

## License

See the repository root `LICENSE`.