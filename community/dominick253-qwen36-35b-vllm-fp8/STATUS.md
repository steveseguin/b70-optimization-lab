# Qwen3.6 35B A3B FP8 on Intel Arc B70 (vLLM Docker)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` for the corrected prospective replay; contributor identity and claims remain `community-reported` |
| Patch review status | read, corrected, and executed |
| Tested in reference lab | yes; startup/functional/context gates, matched `llama-benchy` replay under Podman and Docker Engine, image source-delta audit, and MTP2 calibration |
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
commit contained no durable benchmark or validation artifacts. Immediately
afterward, the contributor posted a `llama-benchy` CSV in the PR discussion:
five concurrency-1 runs per depth, a 2,048-token prompt, 1,024 requested output
tokens, depths 0/4K/8K/16K/32K, and generation-latency accounting. It reports
127.86–135.05 decode tok/s and 8,330–9,251 prefill tok/s. That artifact is
preserved under `reported/` and remains `community-reported`.

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
| Prompt / output / context lengths, concurrency | benchmark comment: prompt 2048, requested output 1024, context depths 0/4096/8192/16384/32768, concurrency 1, five runs per depth; service maximum 262144 and max sequences 4 |
| Cache and speculation policy | prefix caching disabled; no `--speculative-config` in the submitted launcher, so its `qwen36-35b-mtp` name was only an alias and MTP was off; other cache policy unknown |
| Metric definition, repeats, dispersion, TTFT | `llama-benchy` generation-latency mode; CSV means/stddev and peak values for five runs; exact tool version/command and JSON requests absent |
| Logs / JSON / durable links | PR-attached CSV only; no engine log, benchmark JSON, or per-request responses |

## Reference Lab Environment

| Field | Value |
| --- | --- |
| GPU | 2x Intel Arc B70, logical devices 0 and 1 |
| Kernel / driver source | `7.0.0-28-generic`; xe srcversion `85B7CA089405934276CBAD3` |
| Container runtime | rootless Podman 4.9.3 initially; rootful Docker Engine 29.7.1 follow-up |
| Image | `docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780` |
| vLLM / native kernels / torch | `0.21.1.dev0+gad7125a43.d20260709` plus downstream tree changes; `vllm-xpu-kernels 0.1.8.3.dev0+g3cab97a.d20260709` plus downstream tree changes; `custom-esimd-kernels-vllm 0.1.0`; torch `2.11.0+xpu` |
| Model | `Qwen/Qwen3.6-35B-A3B` revision `995ad96eacd98c81ed38be0c5b274b04031597b0`; 40 files, 71,926,865,825 bytes; 27/27 LFS SHA-256 checks passed |
| Initial corrected/default runtime | TP2, dynamic FP8 weights, float16 activation dtype, no SSM-state override (checkpoint declares float32), eager, prefix caching off, max length 262144, max sequences 4 |
| Bind / name | initial localhost ports 18215–18217; Podman benchmark/MTP ports 18218–18221; Docker follow-up port 18222; unique exact test-container names; served name `qwen36-35b-fp8` |
| Raw artifacts | `/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-exact-lab-20260802T0408Z`; `/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-claim-validation-20260802T045055Z`; `/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-llama-benchy-replication-20260802T133000Z`; `/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-docker-engine-replay-20260802T151250Z` |

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

The contributor's attached CSV was then replayed separately. The closest
recoverable identity used the pinned model/image, TP2, eager mode, online FP8,
the submitted float16 SSM override, prefix caching off, and `llama-benchy`
commit `e9be344578cec17745066b220798b80a0d2686d3`, the final upstream commit
before the contributor's post. All 25 measured requests completed without API
errors. Across the five depth rows, lab decode means were
53.58–54.92 tok/s (54.2564 overall mean), while the contributor's CSV reports
127.86–135.05 tok/s (132.8771 overall mean). The contributor rate is about
2.45x the lab rate. Prefill was broadly similar. Release `llama-benchy` v0.4.0
gave 55.5351 tok/s in a depth-0 calibration, ruling out the small upstream tool
revision difference as the explanation. A graph-disabled, non-eager depth-0
calibration was worse at 21.1090 tok/s.

Docker Engine 29.7.1 was then installed from Docker's official Ubuntu
repository and the corrected Docker-specific launcher branch was executed with
the same digest-pinned image and float16-SSM benchmark identity. It reached
health in 121 seconds, passed both smokes, and completed the same 25 measured
requests without API errors. The five Docker decode means were 53.8852,
54.2868, 53.8959, 54.4105, and 55.0716 tok/s, for a 54.3100 tok/s overall
mean. This is only `+0.10%` versus Podman's 54.2564 tok/s mean, so the
container engine is not the source of the contributor's approximately 2.45x
higher report.

The downloaded checkpoint does contain MTP: `text_config` declares one MTP
hidden layer and its index contains `mtp.*` weights. The model card recommends
two speculative tokens for vLLM, but the submitted launcher did not enable
speculative decoding. A separate eager, float16-SSM, online-FP8 calibration
added only the model-card MTP2 setting. vLLM loaded `Qwen3_5MoeMTP`; it accepted
1,247 of 1,800 draft tokens (69.28%) and produced exactly 1,024 output tokens at
46.4358 tok/s, versus 54.9226 tok/s for MTP off. It also reduced reported
KV-cache capacity from 1,010,114 to 860,623 tokens. Four exact-answer cases,
four deterministic repeats, and four simultaneous bounded completions passed.
MTP therefore does not explain the reported throughput and remains an explicit
launcher option rather than the default. The final corrected launcher was then
executed with `MTP_TOKENS=2` and default/checkpoint float32 SSM state. It reached
health in 142 seconds and passed its plain and thinking smoke checks.

The pinned image's embedded Git trees were compared to their stated bases.
vLLM has 64 modified tracked files totaling 4,283 insertions and 340 deletions,
plus 18 untracked files beyond `ad7125a431`: 17 source/test files and one
release-note file. `vllm-xpu-kernels` has
25 modified tracked files totaling 2,192 insertions and 379 deletions beyond
`3cab97adf`, including GDN and paged-decode native kernels. The image also
installs `custom-esimd-kernels-vllm 0.1.0` from a source tree with no Git
metadata. These changes include Intel/XPU GDN, ESIMD, FP8, scheduler, sampler,
and speculative-decode work. The Qwen MTP model-loader files themselves are
byte-identical to upstream; common speculative paths are modified. No separate
contributor patch was submitted or discovered. Exact diffs and the custom-
ESIMD source archive are preserved in the raw artifact root.

The performance-relevant Qwen delta includes an ESIMD fused GDN decode path
whose source gates execution on actual float16 SSM cache state. The submitted
float16 SSM override makes this path eligible; checkpoint-declared float32 does
not. The matched replay retained that override and registered the custom ESIMD
operations, so this known image-integrated fast-path prerequisite was included.

The final published launcher was executed after strengthening the thinking
smoke. It reached health in 121 seconds, passed its plain `HELLO` check, and
returned nonempty parsed reasoning with `finish_reason=stop` and final content
exactly `408`. Two preceding strengthened candidates instead ended with
`finish_reason=length`; their complete payloads were not preserved, so no more
specific configuration claim is made from them. The final smoke uses the
reproducible seeded 32-token case and does not describe the budget as a
universal hard limit.

All exact test containers were stopped and removed and localhost ports
18215–18222 were clear after their respective runs. No reset, reboot, model
service change, or collective retry was used. The newly installed Docker and
containerd system services remain enabled and active with no containers.

## Findings

1. The exact submitted image tag is known, but the contributor's immutable
   digest and the vLLM/runtime source commits inside it are not. The corrected
   recipe pins the digest to which the tag resolved in the reference lab; that
   is a prospective reproduction identity, not evidence of what the contributor
   executed.
2. The model repository is known, but the downloaded revision and artifact
   digest are not, so the model identity is incomplete.
3. The original `150 tok/s` / "golden" statement was unsupported and has been
   removed. It has no workload, metric, repetition, or quality gate and remains
   distinct from the later defined `llama-benchy` CSV.
4. The later 127.86–135.05 tok/s `llama-benchy` report is real source evidence,
   but it was not reproduced. The matched lab replay measured 53.58–54.92
   tok/s. Missing contributor tool/runtime identity prevents a causal diagnosis
   of the approximately 2.45x gap.
5. The checkpoint has MTP weights, but the submitted launcher did not enable
   them. Model-card MTP2 was slower here (46.4358 vs 54.9226 tok/s), passed the
   bounded functional checks, and does not explain the contributor result.
6. The image carries substantial Intel downstream changes in both vLLM and
   `vllm-xpu-kernels`, plus a custom ESIMD package with no source commit. There
   is no separate contributor patch; the OCI digest is the reproducible patch
   identity. The matched replay retained the float16-SSM prerequisite for its
   Qwen GDN ESIMD decode path.
7. The original top-level README variables did not reach hard-coded launcher
   values. The corrected launcher consistently honors exported settings and
   requires an explicit model directory.
8. The original launcher could stop a host service and force-remove an existing
   container. The corrected launcher fails on either an occupied port or an
   existing same-name container and leaves remediation to the operator. It
   defaults to no automatic restart; after creating its own exact-name
   container, failed startup/smoke checks clean up only that new container.
9. The corrected launcher defaults to localhost publication, removes
   `--privileged`, host networking, the false `qwen36-27b-fp8` alias, and
   `--trust-remote-code`.
10. The original launcher forced float16 SSM state despite the checkpoint's
   float32 declaration. The corrected default does not override the model;
   optional float16 is labeled and gated as a quality-changing experiment. The
   benchmark replay tested it for throughput and bounded coherence, not for
   BF16-relative quality equivalence.
11. The configured `MAX_LEN=262144` passed a near-boundary gate at 261,794
   prompt tokens and 261,812 total tokens, including exact early-key retrieval
   and an immediate independent next request. This applies only to the pinned
   corrected lab identity, not the contributor's unknown runtime.
12. Corrected smoke tests fail on HTTP/API errors and assert a bounded plain
   response plus completed arithmetic/reasoning behavior. Runtime validation
   found that this image emits parsed thinking as `message.reasoning`; the
   published check handles that field plus the older `reasoning_content`
   spelling, requires `finish_reason=stop`, and narrowly accepts bare `408` or
   the exact equivalent `17 * 24 = 408` / `17 × 24 = 408` equation.
13. `THINKING_BUDGET` affects only the corrected script's thinking smoke
    request; it is not a server-wide policy. The mixed bounded-pass and fresh
    length-failure evidence does not establish a reliable hard budget for
    arbitrary sampled requests in this image.
14. All fixed-suite responses completed, but the strict suite did not pass
    because cached-token telemetry was absent. Its throughput is diagnostic.

## Known Issues

- No contributor-side immutable image digest, internal vLLM commit, XPU runtime
  identity, model revision, or model artifact digest is recorded.
- No contributor engine logs, benchmark JSON/per-request output, exact
  `llama-benchy` version/command, or machine-readable smoke responses are
  preserved; only the reported CSV is available.
- Runtime FP8 accuracy relative to the source checkpoint has not been measured.
- The original float16 SSM override was exercised in the benchmark replay, but
  its quality equivalence and long-context behavior relative to checkpoint-
  declared float32 remain unestablished.
- MTP2 is functional but slower in the bounded eager calibration, reduces KV
  capacity, and is not listed among this image release note's supported XPU
  speculative methods. It remains opt-in.
- The fixed realistic suite lacks cached-token telemetry and therefore remains
  invalid/incomplete despite completing all 12 prompts.
- Both rootless-Podman and rootful-Docker launcher branches passed. Docker's
  numeric render-GID and `--shm-size` path produced essentially the same
  matched decode rate as Podman; this does not validate the contributor's
  unrecorded historical Docker/image identity.
- The endpoint has no authentication. Remote publication requires an explicit
  opt-in and an operator-provided firewall or authenticated proxy.

## Remaining Unknowns

No contributor action is required for this entry. The contributor's immutable
image digest, internal runtime commits, exact model revision, raw responses,
and exact benchmark tool/runtime environment remain unknown and are not
inferred from the separate reference-lab replays. Runtime-FP8 and float16-SSM
quality equivalence, peak load memory, scale correctness, and whether a
different immutable Intel image explains the decode gap remain separate future
experiments. The current pinned image under Docker versus Podman is now ruled
out as the explanation.

## Disposition

Keep the corrected entry in `community/` at `B70-tested`: the corrected
prospective replay starts and passes bounded functional checks on the local B70
lab. Do not move it to `repro/` or `results/` because the contributor identity
is still unknown, the strict realistic-suite cache-zero telemetry gate did not
pass, the reported throughput was not reproduced, and runtime-FP8 equivalence
is unestablished. Preserve the contributor CSV under `reported/`; do not submit
either the report or diagnostic lab throughput to LocalMaxxing.
