# Qwen3.6 35B A3B FP8 on Intel Arc B70 (vLLM Docker)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` for the corrected prospective replay; contributor identity and claims remain `community-reported` |
| Patch review status | read, corrected, and executed |
| Tested in reference lab | yes; repeated startup/smoke, semantic, concurrency, 261,794-token retrieval, and immediate next-request gates |
| Safe to merge as documentation | yes, after maintainer corrections recorded below |
| Eligible for `repro/` or `results/` | no; strict realistic-suite telemetry and promotion gates remain incomplete |

## Provenance

- Contributor: `dominick253`
- Source PR: [PR #15](https://github.com/steveseguin/b70-optimization-lab/pull/15)
- Contributor commit: `975a097891fb00e0cdf989b9f3a13d3c09114321`
- Right-to-submit statement present: implicit via `CONTRIBUTING.md`; not
  separately stated
- Third-party material and attribution: vLLM and Intel's
  `intel/llm-scaler-vllm` image; `Qwen/Qwen3.6-35B-A3B` model. Their upstream
  licenses and terms apply.
- Maintainer corrections: launcher and documentation edited after submission
  to fail closed around ports/containers, default to localhost, remove broad
  container privileges, make configuration effective, distinguish precision
  modes, and replace syntax-only smoke tests with bounded semantic checks.
  Runtime validation additionally fixed the executable bit, accepted this
  image's `message.reasoning` response field with a legacy fallback, made the
  thinking-mode request explicit, required a normally completed final answer,
  and made recent-log capture portable across Docker and Podman before failure
  cleanup.

## Claim

The contributor reports that a two-B70 Docker service loads the full
`Qwen/Qwen3.6-35B-A3B` BF16 checkpoint with vLLM runtime FP8 weight
quantization and passes initial plain and thinking smoke tests. The submission
contained no durable benchmark or validation artifacts supporting a throughput,
long-context, or quality claim.

An original launcher comment described a "golden" June recipe and a `150 tok/s`
baseline. It had no run identity, metric definition, raw logs, JSON, or quality
evidence, and was removed rather than preserved as a supported claim.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2x Intel Arc B70 (Battlemage G31), 32 GB each, reported PCIe 4.0 x8 |
| OS / kernel | Ubuntu 26.04 LTS / 7.0.0-28-generic |
| GPU driver (`i915` / `xe`) and version | `xe`; version unknown |
| compute-runtime / level-zero | unknown |
| Engine / image and exact version | vLLM reported as 0.21 in image tag `intel/llm-scaler-vllm:0.21.0-b1`; contributor's image digest unknown. Corrected recipe pins the lab-resolved digest `docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780` |
| Model repo and revision | `Qwen/Qwen3.6-35B-A3B`; revision and local artifact digest unknown |
| Quantization (weights / KV / activations) | BF16 source weights; runtime FP8 weights; `--dtype float16`; KV precision unknown; corrected recipe leaves SSM state/cache at model config / vLLM default (checkpoint declares float32) |
| Command and environment variables | corrected `vllm-qwen36-35b-fp8.sh`; original contributor configuration is in commit `975a097891fb00e0cdf989b9f3a13d3c09114321` |
| Prompt / output / context lengths, concurrency | configured max model length 262144 and max sequences 4; contributor smoke prompts only; actual lengths and concurrency evidence unknown |
| Cache and speculation policy | prefix caching disabled; no speculative decoding; other cache policy unknown |
| Metric definition, repeats, dispersion, TTFT | none supplied |
| Logs / JSON / durable links | none supplied beyond source PR and commit |

## Reference Lab Environment

| Field | Value |
| --- | --- |
| GPU | 2x Intel Arc B70, logical devices 0 and 1 |
| Kernel / driver source | `7.0.0-28-generic`; xe srcversion `85B7CA089405934276CBAD3` |
| Container runtime | rootless Podman 4.9.3 |
| Image | `docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780` |
| vLLM / XPU kernels / torch | `ad7125a431e176d4161099480a66f0169609a690` / `3cab97adf65f7e85fb96f4a08db5611832d37382` / `2.11.0+xpu` |
| Model | `Qwen/Qwen3.6-35B-A3B` revision `995ad96eacd98c81ed38be0c5b274b04031597b0`; 40 files, 71,926,865,825 bytes; 27/27 LFS SHA-256 checks passed |
| Runtime | TP2, dynamic FP8 weights, float16 activation dtype, no SSM-state override (checkpoint declares float32), eager, prefix caching off, max length 262144, max sequences 4 |
| Bind / name | localhost ports 18215–18217 with unique exact test-container names; served name `qwen36-35b-fp8` |
| Raw artifacts | `/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-exact-lab-20260802T0408Z`; `/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-claim-validation-20260802T045055Z` |

## What Was Actually Run Here

After the lane owner paused Laguna and released the community lane, the exact
model snapshot was downloaded to internal NVMe and checked against the upstream
40-file size manifest plus all 27 LFS SHA-256 values. The corrected launcher
then started the pinned image on two B70s, reached HTTP health in 121 seconds,
reported the intended model and 262144 configured maximum, selected the XPU
FP8 linear/MoE kernels, and passed its plain and thinking smoke checks.

Additional checks passed:

- exact plain sentinel;
- structured JSON with `17 * 24 = 408`;
- nonempty parsed thinking containing the correct result;
- four simultaneous unique-sentinel requests with no cross-talk;
- exact key retrieval with 30,049 actual prompt tokens;
- exact near-boundary retrieval with 261,794 prompt tokens and 261,812 total
  prompt-plus-completion tokens (261,826 reserved at the 32-token maximum),
  followed immediately by an independent exact next-request sentinel.

The fixed 12-prompt realistic suite completed 12/12 at 128 output tokens per
prompt with thinking disabled. Its diagnostic medians were
`48.580979765184026 tok/s` under the historical 100-event convention and
`48.095169967532186 tok/s` under conventional 99-interval accounting. The
strict gate is `invalid-or-incomplete`: every response omitted
`prompt_tokens_details`, so `cached_tokens=0` could not be observed. Prefix
caching was disabled, but missing telemetry is not equivalent to a passing
cache-zero gate. A fresh second suite measured `50.43388928995701` and
`49.92955039705744 tok/s`, respectively, with the same telemetry failure.
These rates are not promoted or LocalMaxxing evidence.

The final published launcher was executed after strengthening the thinking
smoke. It reached health in 121 seconds, passed its plain `HELLO` check, and
returned nonempty parsed reasoning with `finish_reason=stop` and final content
exactly `408`. Two preceding strengthened candidates instead ended with
`finish_reason=length`; their complete payloads were not preserved, so no more
specific configuration claim is made from them. The final smoke uses the
reproducible seeded 32-token case and does not describe the budget as a
universal hard limit.

All exact test containers were stopped and removed, localhost ports 18215–18217
were clear, and the two tested B70s returned to approximately 42.9 MiB device
memory each. No reset, reboot, service change, or collective retry was used.

## Findings

1. The exact submitted image tag is known, but the contributor's immutable
   digest and the vLLM/runtime source commits inside it are not. The corrected
   recipe pins the digest to which the tag resolved in the reference lab; that
   is a prospective reproduction identity, not evidence of what the contributor
   executed.
2. The model repository is known, but the downloaded revision and artifact
   digest are not, so the model identity is incomplete.
3. The original `150 tok/s` / "golden" statement was unsupported and has been
   removed. The contributor supplied no workload, metric, repetition, or
   quality gate. The lab's two roughly 48–50 tok/s fixed-suite diagnostics are
   not comparable proof for or against an undefined metric.
4. The original top-level README variables did not reach hard-coded launcher
   values. The corrected launcher consistently honors exported settings and
   requires an explicit model directory.
5. The original launcher could stop a host service and force-remove an existing
   container. The corrected launcher fails on either an occupied port or an
   existing same-name container and leaves remediation to the operator. It
   defaults to no automatic restart; after creating its own exact-name
   container, failed startup/smoke checks clean up only that new container.
6. The corrected launcher defaults to localhost publication, removes
   `--privileged`, host networking, the false `qwen36-27b-fp8` alias, and
   `--trust-remote-code`.
7. The original launcher forced float16 SSM state despite the checkpoint's
   float32 declaration. The corrected default does not override the model;
   optional float16 is labeled and gated as an unverified quality-changing
   experiment.
8. The configured `MAX_LEN=262144` passed a near-boundary gate at 261,794
   prompt tokens and 261,812 total tokens, including exact early-key retrieval
   and an immediate independent next request. This applies only to the pinned
   corrected lab identity, not the contributor's unknown runtime.
9. Corrected smoke tests fail on HTTP/API errors and assert a bounded plain
   response plus completed arithmetic/reasoning behavior. Runtime validation
   found that this image emits parsed thinking as `message.reasoning`; the
   published check handles that field plus the older `reasoning_content`
   spelling, requires `finish_reason=stop`, and requires final content `408`.
10. `THINKING_BUDGET` affects only the corrected script's thinking smoke
    request; it is not a server-wide policy. The mixed bounded-pass and fresh
    length-failure evidence does not establish a reliable hard budget for
    arbitrary sampled requests in this image.
11. All fixed-suite responses completed, but the strict suite did not pass
    because cached-token telemetry was absent. Its throughput is diagnostic.

## Known Issues

- No contributor-side immutable image digest, internal vLLM commit, XPU runtime
  identity, model revision, or model artifact digest is recorded.
- No contributor logs or machine-readable smoke-test responses are preserved;
  the reference-lab replay has separate artifacts and identity.
- Runtime FP8 accuracy relative to the source checkpoint has not been measured.
- Float32/default and optional float16 SSM-state quality and memory behavior
  have not been compared.
- The fixed realistic suite lacks cached-token telemetry and therefore remains
  invalid/incomplete despite completing all 12 prompts.
- Reference-lab execution used rootless Podman. The pinned OCI image and Podman
  launcher branch passed, but the Docker-specific render-GID and `--shm-size`
  branch was not executed because the Docker CLI is absent on this host.
- The endpoint has no authentication. Remote publication requires an explicit
  opt-in and an operator-provided firewall or authenticated proxy.

## Remaining Unknowns

No contributor action is required for this entry. The contributor's immutable
image digest, internal runtime commits, exact model revision, raw responses,
and actually exercised context lengths remain unknown and are not inferred
from the separate reference-lab replay. Optional float16 SSM state, runtime-FP8
quality equivalence, peak load memory, and scale correctness remain separate
future experiments.

## Disposition

Keep the corrected entry in `community/` at `B70-tested`: the corrected
prospective replay starts and passes bounded functional checks on the local B70
lab. Do not move it to `repro/` or `results/` because the contributor identity
is still unknown, the strict realistic-suite cache-zero telemetry gate did not
pass, and runtime-FP8 equivalence is unestablished. Do not submit the
diagnostic throughput to LocalMaxxing.
