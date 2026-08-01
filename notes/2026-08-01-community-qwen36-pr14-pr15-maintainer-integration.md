# Community Qwen3.6 PR #14/#15 Maintainer Integration

Date: 2026-08-01

## Scope

Integrate the two open `dominick253` community contributions without requiring
the contributor to rewrite their branches:

- PR #14: Qwen3.6-35B-A3B llama.cpp/SYCL recipe;
- PR #15: Qwen3.6-35B-A3B dynamic-FP8 vLLM container recipe.

The contributor commits were merged with their authorship intact. Maintainer
corrections were committed afterward so the submitted state and corrected
state remain distinguishable in history.

## Corrections Applied

PR #14 is classified `community-reported` and now:

- identifies the actual artifact as UD-Q8_K_XL rather than Q8_0;
- labels the implicit KV cache as F16 because no `-ctk`/`-ctv` override was
  supplied;
- records the contributor's later approximate control of 45 tok/s MTP-off
  versus 40 tok/s MTP-on;
- defaults MTP off and keeps MTP-on as a diagnostic;
- distinguishes a configured 512000-token ceiling from the reported measured
  prompt lengths, which reached only 96 tokens;
- defaults to loopback, removes forced process killing, and uses an
  unprivileged systemd example;
- records the exact locally pre-positioned candidate GGUF identity without
  treating its presence as execution evidence.

PR #15 is classified `community-reported` and now:

- removes the unsupported `150 tok/s` / "golden" claim;
- pins the image digest resolved in the reference lab while leaving the
  contributor's original digest and model revision unknown;
- honors exported configuration and requires an explicit model directory;
- supports Docker or rootless Podman without `--privileged` or host networking;
- defaults to loopback and requires an explicit opt-in for remote exposure;
- fails closed on an occupied port or existing container and never changes a
  systemd service;
- removes the false 27B alias and `--trust-remote-code`;
- leaves SSM state at model/default precision, with float16 available only as
  an explicitly unverified quality-changing option;
- uses HTTP and bounded semantic smoke checks rather than JSON syntax alone;
- defaults to no container restart loop and removes only the newly created
  exact container when launch/smoke validation fails.

Both entries are indexed in `community/README.md`. Neither is eligible for
`repro/`, `results/`, or LocalMaxxing until its required validation passes.

## Review Validation

Completed without loading either model:

- `git diff --check`;
- `bash -n` for the corrected launchers/snippets;
- AST parsing of the two embedded Python response validators in the vLLM
  launcher;
- a fail-closed missing-model-path check for the vLLM launcher;
- local resolution of the pinned OCI image digest.

No service, container, model workload, sudo command, reset, reboot, or driver
operation was performed.

## Why Runtime Validation Is Deferred

`CURRENT.md` still marks the Laguna calibrated-FP8-KV work as active and says
the host is blocked by an executed four-rank XCCL collective failure. Its next
authorized action is a clean reboot, strict per-device checks, and exactly one
corrected collective probe requiring `PASS clean_teardowns=4/4`.

Idle cards and the absence of a public endpoint do not override that state.
Do not download/stage the missing large model, build a community runtime, or
start either recipe until the Laguna lane owner releases the cards and the
post-recovery gate is authoritative.

## Validation Prerequisites

For PR #14:

- use a clean isolated llama.cpp checkout at contributor commit `fb92d8f18`;
- do not use or clean the modified `/home/steve/src/llama.cpp` tree;
- acquire and hash `mmproj-BF16.gguf`, or explicitly label a text-only run;
- use the pre-positioned GGUF at revision
  `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`, size `39099447584`, SHA-256
  `6c6b816537abad90b250a0972b345466028d861ddfe316d5f0de31ca6440f781`.

For PR #15:

- download the full BF16 `Qwen/Qwen3.6-35B-A3B` checkpoint at a pinned revision
  into an isolated cache and verify every shard;
- use rootless Podman as a recorded deviation because Docker is absent;
- use image
  `docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`;
- keep SSM state at the checkpoint/model default for the baseline.

## Validation Ladder After Lane Release

Run the recipes sequentially on cards 0 and 1, using distinct loopback ports
and unique process/container names. Preserve exact source, binary, DSO, image,
model, driver, runtime, command, environment, request, response, and cleanup
identities.

1. Require clean startup, `/health`, `/v1/models`, one intended model identity,
   and no precision fallback or device error.
2. Run plain, reasoning, arithmetic, JSON, and deterministic output canaries.
3. Run unique cold realistic prompts and sequential/concurrency contamination
   checks.
4. For PR #14, compare greedy MTP-off and MTP-on on identical fresh prompts,
   requiring target-token identity before interpreting speed or acceptance.
5. For PR #15, validate dynamic FP8 quality at default float32/model SSM state;
   keep any float16-SSM test in a separately labeled lane.
6. Progress through exact-token long-context retrieval ladders rather than
   treating configured maximum lengths as proof.
7. Only after correctness passes, run the fixed cold 13-prompt performance
   suite with conventional 99-interval accounting and complete artifacts.

Stop at the first correctness, device, collective, context, teardown, or
identity failure. Preserve the negative result; do not reboot, reset, retry a
collective, or continue into performance under the community-validation scope.
