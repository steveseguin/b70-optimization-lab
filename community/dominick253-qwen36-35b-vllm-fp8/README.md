# Qwen3.6 35B A3B FP8 on Intel Arc B70 (vLLM Docker)

> **Maintainer note — corrected community submission, `B70-tested`.** The
> corrected launcher now starts and passes bounded smoke, semantic,
> concurrency, and 30,049-token retrieval checks in the reference lab. This is
> a prospective replay at pinned model/image revisions; it does not verify the
> contributor's original identity, the configured 256K boundary, or a
> performance claim. See [STATUS.md](STATUS.md) and the
> [lab summary](validation/2026-08-01-reference-lab-summary.json).

---

This community recipe serves `Qwen/Qwen3.6-35B-A3B` from its BF16 checkpoint
and asks vLLM to quantize weights to FP8 at load time on two Intel Arc B70s.
The submitted image tag was `intel/llm-scaler-vllm:0.21.0-b1`. The corrected
launcher defaults to the immutable image identity
`docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`,
which is how that tag resolved when inspected in the reference lab. The image
used by the contributor remains unknown because no digest was recorded there.

The contributor reported that the service passed initial smoke tests. The
reference lab separately confirmed the corrected recipe at the identities
below. No contributor throughput, long-context, or quality result was supplied.

## Model And Precision

- Model repo: `Qwen/Qwen3.6-35B-A3B`.
- Contributor model revision and local artifact digest: unknown.
- Reference-lab model revision:
  `995ad96eacd98c81ed38be0c5b274b04031597b0`; all 40 files matched the
  upstream size manifest and all 27 LFS objects passed SHA-256 verification.
- Source checkpoint: BF16.
- Runtime weight quantization: FP8 via `--quantization fp8` and
  `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1`.
- Runtime activation precision: `--dtype float16`.
- SSM state/cache precision: model configuration / vLLM default. The checkpoint
  declares float32 SSM state. The launcher does not silently override it.

Setting `MAMBA_SSM_CACHE_DTYPE=float16` is available only as an explicitly
unverified, quality-changing experiment and additionally requires
`ALLOW_UNVERIFIED_FLOAT16_SSM=1`. It must be benchmarked and quality-tested as
a separate configuration.

## Start

Requirements:

- Docker or Podman and two Intel Arc B70 GPUs exposed through `/dev/dri`;
- the model already downloaded to a local directory;
- `curl`, `python3`, `ss`, and membership/access appropriate for Docker and the
  render device.

Run from this directory:

```bash
export MODEL_HOST_DIR=/path/to/Qwen3.6-35B-A3B
export IMAGE=docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780
export PORT=8001
export TP=2
export MAX_LEN=262144
export MAX_SEQS=4
export EAGER=1

bash vllm-qwen36-35b-fp8.sh
```

All launcher settings use the exported environment when present. Important
optional settings include `CONTAINER_RUNTIME`, `NAME`, `SERVED_NAME`,
`BIND_HOST`, `ALLOW_REMOTE_BIND`, `GPU_UTIL`, `ZE_AFFINITY_MASK`,
`ONEAPI_DEVICE_SELECTOR`, `RESTART_POLICY`, `STARTUP_TIMEOUT_SECONDS`, and
`THINKING_BUDGET`.
`RESTART_POLICY` defaults to `no` until this recipe is locally validated.

The script prefers Docker when both supported CLIs are installed and otherwise
uses Podman. Set `CONTAINER_RUNTIME=docker` or `CONTAINER_RUNTIME=podman` to
choose explicitly. Docker receives the numeric render GID; rootless Podman uses
`--group-add keep-groups`, matching this lab's prior B70 container validation.
Podman omits `--shm-size` because it rejects that option with `--ipc=host`.
The reference-lab run used rootless Podman 4.9.3.

The model mount is read-only. The script fails if the requested host port is
already listening or if a container with `NAME` already exists. It never stops
a systemd service and never removes an existing container. Resolve ownership
yourself, then rerun it. After it successfully creates its own exact-name
container, a failed startup or smoke check stops and removes only that newly
created container. A successful service remains running.

## Network Safety

The default is `BIND_HOST=127.0.0.1`. The vLLM process listens on all interfaces
inside the container, but the container runtime publishes it only to localhost.
The recipe does not configure authentication.

To publish on a LAN, make the exposure explicit:

```bash
export BIND_HOST=0.0.0.0
export ALLOW_REMOTE_BIND=1
bash vllm-qwen36-35b-fp8.sh
```

Do this only behind an appropriate firewall or authenticated reverse proxy.
The container uses `/dev/dri`, host IPC, and the render group, but does not use
`--privileged` or host networking.

## Effective Configuration

| Field | Recipe default |
| --- | --- |
| Image | `intel/llm-scaler-vllm:0.21.0-b1`, pinned by the launcher to digest `sha256:5d87be271e4d...` |
| Served model name | `qwen36-35b-fp8` |
| Host publication | `127.0.0.1:8001` |
| Tensor parallelism | 2 |
| Configured maximum model length | 262144 |
| Maximum active sequences | 4 |
| Restart policy | `no` |
| Weight quantization | runtime FP8 |
| SSM state/cache | model config / vLLM default (checkpoint declares float32) |
| Prefix caching | disabled |
| Eager mode | enabled |
| Thinking | enabled by default in chat-template kwargs |
| Reasoning parser | `qwen3` |

`MAX_LEN=262144` is only a configured limit. The reference-lab run passed one
30,049-token retrieval request, but did not attempt a 262144-token prefill,
near-boundary retrieval, rollover, or next-request check. It therefore does not
establish working 256K context.

## Thinking Budget

The server enables thinking by default, but `THINKING_BUDGET` is not a global
server limit. It is used only by the launcher's thinking smoke-test request.
Clients that want a hard budget must send `thinking_token_budget` in each
request (subject to the selected vLLM/chat-template API behavior).

The launcher smoke tests check more than JSON syntax:

- `curl --fail-with-body` rejects HTTP errors;
- the plain response must contain `HELLO` in assistant content;
- the thinking response must expose nonempty parsed reasoning and contain the
  correct arithmetic answer `408` in reasoning or final content. The pinned
  image uses `message.reasoning`; the check retains a
  `message.reasoning_content` fallback for older compatible images.

These are startup checks, not a quality or benchmark suite.

## Reference-Lab Validation

On 2026-08-01/02, the corrected recipe ran on two reference-lab B70s with:

- model revision `995ad96eacd98c81ed38be0c5b274b04031597b0`;
- pinned image digest `sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`;
- vLLM `0.21.1.dev0+gad7125a43.d20260709` at commit `ad7125a431`;
- vLLM XPU kernels `3cab97adf` and torch `2.11.0+xpu`;
- TP2, eager mode, runtime FP8, float16 activation dtype, prefix caching off,
  and model-default float32 Mamba SSM state.

The service reached health in 121 seconds and selected the XPU FP8 linear and
MoE kernels. It passed exact plain text, structured JSON/arithmetic, parsed
thinking/arithmetic, four simultaneous unique-sentinel requests, and exact
retrieval at 30,049 prompt tokens. Teardown removed only the exact test
container and returned the endpoint and GPUs to idle.

All 12 prompts in the fixed realistic suite completed with 128 output tokens
and no reasoning deltas in non-thinking mode. Their diagnostic conventional
99-interval median was `48.095169967532186 tok/s`. The suite remains
`invalid-or-incomplete`, not promoted evidence, because this vLLM build omitted
`prompt_tokens_details.cached_tokens` on every response, so the required
`cached_tokens=0` telemetry gate could not pass even though prefix caching was
disabled.

Runtime validation also found and fixed two packaging/API issues: the launcher
lacked its executable bit, and its thinking check read only the deprecated
`reasoning_content` field instead of this image's `reasoning` field. Failure
cleanup now emits recent container logs before removing its own container.
Raw artifacts are outside Git at
`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-exact-lab-20260802T0408Z`.

## Contributor Environment

The contributor reported:

| Field | Value |
| --- | --- |
| OS / kernel | Ubuntu 26.04 LTS / 7.0.0-28-generic |
| CPU | AMD Ryzen 9 9950X |
| GPU | 2x Intel Arc B70, 32 GB each, PCIe 4.0 x8 |
| Driver | `xe`, version unknown |
| Image | `intel/llm-scaler-vllm:0.21.0-b1` |
| Context setting | 262144, not validated at length |

See [STATUS.md](STATUS.md) for the evidence gaps and promotion requirements.
