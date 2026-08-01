# Qwen3.6 35B A3B FP8 on Intel Arc B70 (vLLM Docker)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read, no execution |
| Tested in reference lab | no |
| Safe to merge as documentation | yes, after maintainer corrections recorded below |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor: `dominick253`
- Source PR: [PR #15](https://github.com/steveseguin/b70-optimization-lab/pull/15)
- Contributor commit: `975a0978984e5a47b28d3076b0a80b22c4f3325f`
- Right-to-submit statement present: implicit via `CONTRIBUTING.md`; not
  separately stated
- Third-party material and attribution: vLLM and Intel's
  `intel/llm-scaler-vllm` image; `Qwen/Qwen3.6-35B-A3B` model. Their upstream
  licenses and terms apply.
- Maintainer corrections: launcher and documentation edited after submission
  to fail closed around ports/containers, default to localhost, remove broad
  container privileges, make configuration effective, distinguish precision
  modes, and replace syntax-only smoke tests with bounded semantic checks.

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
| Command and environment variables | corrected `vllm-qwen36-35b-fp8.sh`; original contributor configuration is in commit `975a0978984e5a47b28d3076b0a80b22c4f3325f` |
| Prompt / output / context lengths, concurrency | configured max model length 262144 and max sequences 4; contributor smoke prompts only; actual lengths and concurrency evidence unknown |
| Cache and speculation policy | prefix caching disabled; no speculative decoding; other cache policy unknown |
| Metric definition, repeats, dispersion, TTFT | none supplied |
| Logs / JSON / durable links | none supplied beyond source PR and commit |

## Reference Lab Environment

Not recorded because nothing from this contribution has been executed in the
reference lab.

## What Was Actually Run Here

No Docker image, model load, GPU workload, endpoint request, or benchmark was
run in the reference lab during this review. Review was limited to source and
documentation inspection plus static shell checks. This avoids disturbing the
active/protected work described by `CURRENT.md`; a later validation must first
confirm that the relevant GPUs, port, and runtime paths are free.

## Findings

1. The exact submitted image tag is known, but the contributor's immutable
   digest and the vLLM/runtime source commits inside it are not. The corrected
   recipe pins the digest to which the tag resolved in the reference lab; that
   is a prospective reproduction identity, not evidence of what the contributor
   executed.
2. The model repository is known, but the downloaded revision and artifact
   digest are not, so the model identity is incomplete.
3. The original `150 tok/s` / "golden" statement was unsupported and has been
   removed. There is currently no performance evidence to validate.
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
8. The configured `MAX_LEN=262144` has not been validated at or near that
   length. It is not evidence of working 256K context.
9. Corrected smoke tests fail on HTTP/API errors and assert a bounded plain
   response plus arithmetic/reasoning behavior. They remain smoke tests, not a
   comprehensive quality gate.
10. `THINKING_BUDGET` affects only the corrected script's thinking smoke
    request; it is not a server-wide request policy.

## Known Issues

- No contributor-side immutable image digest, internal vLLM commit, XPU runtime
  identity, model revision, or model artifact digest is recorded.
- No contributor logs or machine-readable smoke-test responses are preserved.
- The image/model combination has not been pulled, loaded, or tested here.
- Runtime FP8 accuracy relative to the source checkpoint has not been measured.
- Float32/default and optional float16 SSM-state quality and memory behavior
  have not been compared.
- No cold realistic-suite quality, cached-token, throughput, TTFT, full-output,
  long-context retrieval, 262144 boundary, rollover, or next-request evidence
  exists.
- The endpoint has no authentication. Remote publication requires an explicit
  opt-in and an operator-provided firewall or authenticated proxy.

## Open Questions For The Contributor

1. Which immutable Docker image digest and internal vLLM/XPU runtime commits
   produced the reported smoke-test success?
2. Which exact model revision and local artifact digest were loaded?
3. Can the original command, complete environment, startup log, and raw plain
   and thinking response JSON be supplied?
4. What output is obtained with model-config/default float32 SSM state, and is
   any float16 SSM-state run exact or semantically equivalent on fixed prompts?
5. What context lengths were actually exercised, including a cold retrieval
   gate and a next-request check?

## Disposition

Keep the corrected entry in `community/` at `community-reported` level. It is
safe to merge as reviewed documentation, but it is not promoted evidence.

Raise it to `B70-tested` only after an isolated reference-lab run records the
immutable image/runtime and model identity, startup logs, raw responses, and
the required fixed realistic quality/performance gate. Validate long context
separately if it is claimed. Do not move this entry to `repro/` or `results/`
and do not submit anything to LocalMaxxing unless those verification gates pass
and a real matching record improvement is confirmed.
