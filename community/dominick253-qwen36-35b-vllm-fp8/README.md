# Qwen3.6 35B A3B FP8 on Intel Arc B70 (vLLM Docker)

> **Maintainer note — corrected community submission, `B70-tested`.** The
> corrected launcher starts and passes bounded smoke, semantic, concurrency,
> and exact near-256K retrieval plus next-request checks in the reference lab.
> This is a prospective replay at pinned model/image revisions; it does not
> verify the contributor's original identity, unsupported `150 tok/s`
> launcher comment, or separately reported `128–135 tok/s` benchmark. See
> [STATUS.md](STATUS.md), the
> [initial lab summary](validation/2026-08-01-reference-lab-summary.json), and
> the [matched-benchmark summary](validation/2026-08-02-llama-benchy-replication-summary.json).

---

This community recipe serves `Qwen/Qwen3.6-35B-A3B` from its BF16 checkpoint
and asks vLLM to quantize weights to FP8 at load time on two Intel Arc B70s.
The submitted image tag was `intel/llm-scaler-vllm:0.21.0-b1`. The corrected
launcher defaults to the immutable image identity
`docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`,
which is how that tag resolved when inspected in the reference lab. The image
used by the contributor remains unknown because no digest was recorded there.

The contributor reported that the service passed initial smoke tests. In the
PR discussion they also attached a `llama-benchy` CSV for five single-request
runs at each context depth, using a 2,048-token prompt and 1,024-token
generation. It reports 127.86–135.05 decode tok/s. The CSV is preserved under
[`reported/`](reported/README.md), not mixed into lab validation. The
reference lab separately confirmed the corrected recipe but did not reproduce
that decode rate: the closest recoverable matched replay measured
53.58–54.92 tok/s. The older `150 tok/s` launcher comment remains undefined
and unsupported.

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
- MTP capability: the checkpoint declares one MTP hidden layer and includes
  `mtp.*` weights. Capability is not activation: the submitted launcher did not
  pass `--speculative-config`, so its extra `qwen36-35b-mtp` served-name alias
  did not enable MTP.

Setting `MAMBA_SSM_CACHE_DTYPE=float16` is available only as an explicitly
quality-changing experiment and additionally requires
`ALLOW_UNVERIFIED_FLOAT16_SSM=1`. It was exercised in the matched throughput
replay and bounded coherence checks, but still lacks quality-equivalence and
long-context comparison against the checkpoint's float32 declaration.

The corrected launcher offers MTP only as an explicit option. Set
`MTP_TOKENS=2` for the checkpoint model card's recommended vLLM draft count;
the launcher uses this image's canonical `method=mtp` spelling and verifies
that the mounted checkpoint declares MTP layers. It remains off by default
because the matched reference-lab calibration regressed from `54.92 tok/s`
without MTP to `46.44 tok/s` with MTP2. The MTP run passed bounded deterministic
functional canaries and a four-request check, but the image's own release notes
do not list MTP among its supported XPU speculative methods.

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
export MTP_TOKENS=0

bash vllm-qwen36-35b-fp8.sh
```

All launcher settings use the exported environment when present. Important
optional settings include `CONTAINER_RUNTIME`, `NAME`, `SERVED_NAME`,
`BIND_HOST`, `ALLOW_REMOTE_BIND`, `GPU_UTIL`, `ZE_AFFINITY_MASK`,
`ONEAPI_DEVICE_SELECTOR`, `RESTART_POLICY`, `STARTUP_TIMEOUT_SECONDS`, and
`MTP_TOKENS`, `THINKING_BUDGET`, and `THINKING_MAX_TOKENS`.
`RESTART_POLICY` defaults to `no` until this recipe is locally validated.

The script prefers Docker when both supported CLIs are installed and otherwise
uses Podman. Set `CONTAINER_RUNTIME=docker` or `CONTAINER_RUNTIME=podman` to
choose explicitly. Docker receives the numeric render GID; rootless Podman uses
`--group-add keep-groups`, matching this lab's prior B70 container validation.
Podman omits `--shm-size` because it rejects that option with `--ipc=host`.
The reference-lab runs used rootless Podman 4.9.3. They validate the pinned OCI
image, serve command, and Podman branch; the Docker-specific group and shared-
memory branch was reviewed but not executed because the Docker CLI is absent on
this host.

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
| MTP speculative decoding | disabled; opt in with tested `MTP_TOKENS=2` |
| Thinking | enabled by default in chat-template kwargs |
| Reasoning parser | `qwen3` |

`MAX_LEN=262144` is the configured combined request limit, not permission to
send 262144 prompt tokens plus output. The reference lab passed exact retrieval
with 261,794 prompt tokens and 18 completion tokens (261,812 total), followed
immediately by an independent exact next-request sentinel. That validates this
pinned corrected recipe near the configured boundary; it does not retroactively
validate the contributor's unknown model/image identity.

## Thinking Budget

The server enables thinking by default, but `THINKING_BUDGET` is not a global
server limit. It is used only by the launcher's thinking smoke-test request,
which defaults to a seeded 32-token reasoning budget and a separate 256-token
overall response cap. Clients may send `thinking_token_budget` per request, but
must also bound `max_tokens` and inspect the finish reason. In lab probes, 32-
and 128-token examples completed as intended, while two fresh strengthened
smoke attempts ended with `finish_reason=length`. The latter attempts' complete
request payloads were not preserved, so they support only that narrow failure
classification. This evidence does not support the contributor's unqualified
"hard budget" description.

The launcher smoke tests check more than JSON syntax:

- `curl --fail-with-body` rejects HTTP errors;
- the plain response must contain `HELLO` in assistant content;
- the thinking response must expose nonempty parsed reasoning, finish with
  `finish_reason=stop`, and put either bare `408` or the exact equivalent
  `17 * 24 = 408` / `17 × 24 = 408` equation in final content. The pinned image
  uses `message.reasoning`; the check retains a `message.reasoning_content`
  fallback for older compatible images. The narrow equation allowance avoids
  treating harmless final-answer formatting as an engine-start failure.

These are startup checks, not a quality or benchmark suite.

## Reference-Lab Validation

On 2026-08-01/02, the corrected recipe ran on two reference-lab B70s with:

- model revision `995ad96eacd98c81ed38be0c5b274b04031597b0`;
- pinned image digest `sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`;
- vLLM `0.21.1.dev0+gad7125a43.d20260709` at commit `ad7125a431`;
- vLLM XPU kernels `0.1.8.3.dev0+g3cab97a.d20260709`, custom ESIMD kernels
  `0.1.0`, and torch `2.11.0+xpu`;
- TP2, eager mode, runtime FP8, float16 activation dtype, prefix caching off,
  and no SSM-state override (the checkpoint declares float32).

The service reached health in 121 seconds and selected the XPU FP8 linear and
MoE kernels. It passed exact plain text, structured JSON/arithmetic, parsed
thinking/arithmetic, four simultaneous unique-sentinel requests, and exact
retrieval first at 30,049 prompt tokens and then at 261,794 prompt tokens. The
near-boundary request returned the exact key in 63.79 seconds and an immediate
next request returned its independent exact sentinel in 0.29 seconds. Teardown
removed only the exact test containers and returned the endpoints and GPUs to
idle.

All 12 prompts in the fixed realistic suite completed with 128 output tokens
and no reasoning deltas in non-thinking mode. Their diagnostic conventional
99-interval median was `48.095169967532186 tok/s`. The suite remains
`invalid-or-incomplete`, not promoted evidence, because this vLLM build omitted
`prompt_tokens_details.cached_tokens` on every response, so the required
`cached_tokens=0` telemetry gate could not pass even though prefix caching was
disabled. A fresh second suite measured `49.92955039705744 tok/s` under the
same conventional accounting and had the same missing-telemetry failure. The
contributor's `150 tok/s` comment had no workload or metric definition, so it
cannot be treated as a comparable result.

The PR discussion did contain a different, defined `llama-benchy` result. Its
CSV records five runs per depth at depths 0/4K/8K/16K/32K, 2,048 prompt tokens,
1,024 requested generation tokens, concurrency 1, and generation-latency
accounting. Using the pinned image and model revision, the submitted eager,
TP2, online-FP8, float16-SSM configuration, and the last recoverable upstream
`llama-benchy` commit before the post, the lab completed all 25 measured
requests without API errors. Decode means were 53.58–54.92 tok/s, versus the
contributor's 127.86–135.05 tok/s. Prefill was broadly similar. The contributor
did not preserve the benchmark tool version/command, immutable image digest,
model revision, or JSON requests, so the remaining 2.45x decode gap cannot be
assigned to one missing setting.

The pinned image is not stock upstream vLLM at commit `ad7125a431`. Its
embedded vLLM Git working tree contains an Intel downstream patchset: 64
tracked files differ by 4,283 insertions and 340 deletions, plus 18 untracked
files: 17 source/test files and one release-note file. Its
`vllm-xpu-kernels` tree likewise has 25 tracked files
changed by 2,192 insertions and 379 deletions beyond embedded commit
`3cab97adf`, including GDN and paged-decode kernels. A separate source tree and
wheel provide `custom-esimd-kernels-vllm 0.1.0`; that tree has no Git metadata.
Qwen3.5/3.6 GDN and ESIMD decode changes are therefore present across the
image's Python and native-kernel layers. The image's Qwen MTP model loaders
match upstream byte-for-byte, while its common
speculative scheduler/sampler/metrics paths carry downstream changes. No
separate contributor patch was supplied or found; reproducing this entry means
pinning the OCI digest, not rebuilding plain upstream vLLM from the advertised
commits. The exact vLLM and XPU-kernel diffs, untracked files, and custom-ESIMD
source archive are preserved with the raw benchmark artifacts.

The most directly relevant image delta is an ESIMD fused Qwen3.5/3.6 GDN
decode path. Its source explicitly requires float16 Mamba/SSM cache state; the
submitted `--mamba-ssm-cache-dtype float16` override makes that fast path
eligible, whereas the checkpoint-declared float32 state falls back. The matched
replay deliberately retained the submitted float16 override and registered the
image's custom ESIMD operations, so this image-integrated optimization was not
omitted from the reproduction attempt. It still measured about 54 tok/s.

Finally, the model-card-recommended MTP2 variant was tested under the same
eager float16-SSM identity. vLLM loaded `Qwen3_5MoeMTP`, generated 1,800 draft
tokens for the calibration, and accepted 1,247 (69.28%). It completed exactly
1,024 output tokens at `46.4358 tok/s`, slower than the MTP-off `54.9226 tok/s`
calibration, and reduced reported KV-cache capacity from 1,010,114 to 860,623
tokens. Exact-answer, repeatability, and four-request checks passed. MTP does
not explain the contributor's reported speed and is therefore not the default.
The final corrected launcher was also executed with `MTP_TOKENS=2` and the
checkpoint's default float32 SSM state: it reached health in 142 seconds and
passed both plain and thinking smoke checks before exact-name teardown.

Runtime validation found and fixed packaging/API issues: the launcher lacked
its executable bit, read only the deprecated `reasoning_content` field, and
accepted length-truncated thinking as a smoke pass. It now requires a completed
final answer, and failure logging uses Docker/Podman's portable option order
before removing only its own container. Raw artifacts are outside Git at
`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-exact-lab-20260802T0408Z`
and
`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-claim-validation-20260802T045055Z`.
The matched benchmark, image source-delta audit, and MTP artifacts are under
`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-llama-benchy-replication-20260802T133000Z`.

## Contributor Environment

The contributor reported:

| Field | Value |
| --- | --- |
| OS / kernel | Ubuntu 26.04 LTS / 7.0.0-28-generic |
| CPU | AMD Ryzen 9 9950X |
| GPU | 2x Intel Arc B70, 32 GB each, PCIe 4.0 x8 |
| Driver | `xe`, version unknown |
| Image | `intel/llm-scaler-vllm:0.21.0-b1` |
| Context setting | 262144 reported; contributor run unvalidated, separate corrected lab replay passed at 261,794 prompt / 261,812 total tokens |

See [STATUS.md](STATUS.md) for the evidence gaps and promotion requirements.
