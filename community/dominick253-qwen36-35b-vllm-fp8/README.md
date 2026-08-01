# Qwen3.6 35B A3B FP8 on Intel Arc B70 (vLLM Docker)

> **Maintainer note — corrected community submission, `community-reported`.**
> The launcher below was safety- and reproducibility-edited after submission.
> It has been read but not executed in the reference lab. The contributor's
> environment and unverified claims are recorded in [STATUS.md](STATUS.md); do
> not treat this entry as a lab result.

---

This community recipe serves `Qwen/Qwen3.6-35B-A3B` from its BF16 checkpoint
and asks vLLM to quantize weights to FP8 at load time on two Intel Arc B70s.
The submitted image tag was `intel/llm-scaler-vllm:0.21.0-b1`. The corrected
launcher defaults to the immutable image identity
`docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`,
which is how that tag resolved when inspected in the reference lab. The image
used by the contributor remains unknown because no digest was recorded there.

The contributor reported that the service passed initial smoke tests. No
throughput result, long-context result, or quality result is currently
supported by durable evidence in this entry.

## Model And Precision

- Model repo: `Qwen/Qwen3.6-35B-A3B`.
- Model revision and local artifact digest: unknown; pin and record both before
  comparing results.
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

`MAX_LEN=262144` is only a configured limit. This contribution contains no
262144-token prefill, retrieval, boundary, or next-request validation, so it
does not establish working 256K context.

## Thinking Budget

The server enables thinking by default, but `THINKING_BUDGET` is not a global
server limit. It is used only by the launcher's thinking smoke-test request.
Clients that want a hard budget must send `thinking_token_budget` in each
request (subject to the selected vLLM/chat-template API behavior).

The launcher smoke tests check more than JSON syntax:

- `curl --fail-with-body` rejects HTTP errors;
- the plain response must contain `HELLO` in assistant content;
- the thinking response must expose nonempty reasoning and contain the correct
  arithmetic answer `408` in reasoning or final content.

These are startup checks, not a quality or benchmark suite.

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
