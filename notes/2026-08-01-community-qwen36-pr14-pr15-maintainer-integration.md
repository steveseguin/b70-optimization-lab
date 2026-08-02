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

PR #14 was initially classified `community-reported`, then raised to
`B70-tested` after the corrected prospective replay. It now:

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

PR #15 was initially classified `community-reported`, then raised to
`B70-tested` after the corrected prospective replay. It now:

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

Both entries are indexed in `community/README.md` at `B70-tested`. They remain
in `community/`: neither has the complete promotion evidence required for
`repro/`, `results/`, or LocalMaxxing.

## Static Review Validation

Before the lane was released, both contributions passed `git diff --check`,
shell syntax checks, embedded-Python parser checks, fail-closed input checks,
and image/source identity review. No active Laguna path or runtime was changed.

## Runtime Release And Safety Boundary

The lane owner explicitly paused Laguna and released cards 0 and 1 for this
community validation. A host boot had occurred earlier during model staging;
afterward the B70s passed isolated allocation/compute checks. The community
work did not perform a reset, reboot, driver reload, service change, or
standalone collective retry. Each recipe used its own source tree, loopback
port, process/container name, and external artifact directory.

An unrelated USB `aria2c` process became stuck in an uninterruptible NTFS
truncate syscall during model mirroring. It used no GPU and did not overlap the
final NVMe model. It was left untouched rather than escalating to reset or
reboot.

## PR #14 Reference-Lab Result

The corrected llama.cpp recipe ran from clean commit `fb92d8f1873` with the
UD-Q8_K_XL GGUF and BF16 projector at pinned revision
`5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`. Startup, health, semantic,
concurrency, seven retrieval cases through 34,649 actual prompt tokens, and all
12 fixed-suite prompts passed. The conventional 99-interval content-delta
median was `48.181817970061076 tok/s`.

MTP-on measured `45.7156408565 tok/s`; three MTP-off confirmations measured
`48.4407013911`, `48.4534088298`, and `48.4744558553 tok/s`. MTP was slower for
this identity. Exact MTP quality attribution remains inconclusive because the
MTP-off greedy control was itself nondeterministic across fresh starts.

Summary:
`community/dominick253-qwen36-35b-llamacpp-sycl/validation/2026-08-01-reference-lab-summary.json`.

## PR #15 Reference-Lab Result

The full BF16 `Qwen/Qwen3.6-35B-A3B` snapshot at revision
`995ad96eacd98c81ed38be0c5b274b04031597b0` matched the upstream 40-file size
manifest; all 27 LFS SHA-256 checks passed. The pinned Intel image contained
vLLM `ad7125a431`, XPU kernels `3cab97adf`, and torch `2.11.0+xpu`.

Runtime validation found two correctable launcher defects before the final
pass: the file lacked its executable bit, and the smoke check read only the
deprecated `reasoning_content` field while this image returns parsed thinking
as `reasoning`. The published launcher now handles both field spellings, makes
thinking explicit per request, and preserves recent logs on smoke failure.

The corrected TP2 service reached health in 121 seconds and selected the XPU
dynamic-FP8 linear and MoE kernels. Exact text, JSON/arithmetic, parsed
thinking, four-request concurrency, and 30,049-token retrieval checks passed.
The fixed 12-prompt suite completed with a conventional 99-interval median of
`48.095169967532186 tok/s`, but remains `invalid-or-incomplete` because this
image omitted cached-token telemetry. Prefix caching was disabled; missing
telemetry was not converted into a passing `cached_tokens=0` gate. No 256K,
float16-SSM, or LocalMaxxing claim is made.

Summary:
`community/dominick253-qwen36-35b-vllm-fp8/validation/2026-08-01-reference-lab-summary.json`.

The exact test container was stopped and removed, its port was clear, and all
four B70s were idle after teardown.
