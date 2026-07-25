# Qwen3.6 27B FP8 native TP2 Docker on 2x B70

Community contribution from [PR #9](https://github.com/steveseguin/b70-optimization-lab/pull/9).

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | Read in full; no contributed code executed |
| Tested in reference lab | Partial — bounded multi-GPU runtime probe passed; recipe itself not run |
| Safe to merge as documentation | Yes, with changes (see Known Issues) |
| Eligible for `repro/` or `results/` | No |

The contribution is documentation only: two Markdown files, no code, no CI, no
workflows, no external URLs, no secrets, and a pinned official Intel image.
Nothing in it executes on merge. The reservations below are about evidence
quality and copy-paste safety, not about malicious content.

## Provenance

- Contributor: `dominick253` (GitHub association NONE, first contribution)
- Source: PR #9, 3 commits `de8dec51e`, `8a94f466a`, `72e08ff2f`
- Right-to-submit statement: implicit via `CONTRIBUTING.md`; not separately stated
- Third-party material: none beyond the public `intel/llm-scaler-vllm` image

## Claim

The contributor reports a working TP2 Docker deployment of `Qwen/Qwen3.6-27B`
at native FP8 across two Arc Pro B70s under `intel/llm-scaler-vllm:0.21.0-b1`,
tested 2026-07-22, and reports 28.3-34.7 tok/s across five prompt lengths at
256 output tokens. The PR's `results/README.md` row summarized this as
"Speed-benchmarked 34 Tokens a second".

This is the contributor's claim on the contributor's hardware. It is not a lab
measurement.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2x Intel Arc Pro B70, VRAM unstated |
| OS / kernel | **unknown — not supplied** |
| GPU driver (`i915` / `xe`) and version | **unknown — not supplied** |
| compute-runtime / level-zero | **unknown — not supplied** |
| Engine / image | `intel/llm-scaler-vllm:0.21.0-b1` (pinned) |
| Model repo and revision | `Qwen/Qwen3.6-27B` @ `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9` |
| Quantization | weights native FP8 (`--quantization fp8`); KV `fp8_e4m3`; dtype `float16` |
| Command and environment | Supplied in full; see the contribution README |
| Prompt / output / context | Prompt ~10-2000 tokens, output 256, `--max-model-len 262144`, `--max-num-seqs 4` |
| Cache and speculation policy | `--no-enable-prefix-caching`; no speculation; cold/warm state **unstated**, `cached_tokens` **not reported** |
| Metric definition, repeats, dispersion, TTFT | Prefill time given; metric definition, repeat count, and dispersion **unstated** |
| Logs / JSON / durable links | **none supplied** |

The three unknown host-identity rows are the first thing to request. They are
also exactly what the failed reproduction below needs in order to be
interpreted.

## Reference Lab Environment

| Field | Value |
| --- | --- |
| GPUs | 4x Intel Arc Pro B70, BDF `0000:23:00.0`, `0000:27:00.0`, `0000:43:00.0`, `0000:47:00.0` |
| Kernel | `7.0.0-28-generic` |
| GPU driver module | `xe` |
| Host compute-runtime / level-zero | `intel-opencl-icd` and `libze-intel-gpu1` `26.18.38308.1-0` |
| Container runtime | podman 4.9.3, rootless (installed 2026-07-25 for this validation) |

## What Was Actually Run Here

The contributed recipe was **not** executed. No model was loaded, no endpoint
was served, and no throughput number was produced in this lab.

What was run is a bounded multi-GPU Level Zero context probe
([`validation/probe-multigpu-context.sh`](validation/probe-multigpu-context.sh))
against the same pinned image, testing single-GPU and two-GPU context creation
with and without `SYCL_UR_TRACE=2`. Its scope is the reproduction failure
reported in the PR discussion, not the performance claim.

Full recipe validation is blocked on local infrastructure, not on the
contribution:

- The reference host had no container runtime; rootless podman was installed
  for this probe.
- `Qwen/Qwen3.6-27B` is not cached locally.
- The host filesystem has ~34 GB free against a ~51.75 GiB checkpoint, so the
  model cannot currently be staged.

These are host limitations. They are not evidence about the recipe.

## Findings

A second contributor (`bosd`) reported in the PR that the recipe fails on their
2x B70 host in two ways: TP2 startup dies at
`urContextCreate(.DeviceCount = 2) -> UR_RESULT_ERROR_UNKNOWN` inside
`torch.xpu.device_count()`, with device enumeration itself succeeding; and a
TP1 fallback serves but generates at roughly 0.5 tok/s. They attributed both to
the container's compute-runtime `26.14` being older than a host on the `xe`
driver, kernel `7.0.10`, and host runtime `26.18`.

**Confirmed: the version gap is real.** The pinned image ships
`intel-opencl-icd` and `libze-intel-gpu1` `26.14.37833.4-1~24.04~ppa1` against
this host's `26.18.38308.1-0`, matching the reporter's description.

**Confirmed: the reported multi-GPU failure does not reproduce here.** The
probe ran the exact call that failed for the reporter, on a host in the same
configuration class (`xe`, kernel `7.0.x`, host runtime `26.18`, same
Battlemage silicon `0xe223`, same `26.14` container):

| Arm | `ZE_AFFINITY_MASK` | Result |
| --- | --- | --- |
| A control | `0` | `device_count: 1`, exit 0 |
| B candidate | `0,1` | `device_count: 2`, both B70s enumerated, allocation on `xpu:0` and `xpu:1` succeeded, exit 0 |
| C trace | `0,1` | `urDeviceGet(... pNumDevices = 2) -> UR_RESULT_SUCCESS`, initialization proceeded past the reported failure point, no `UR_RESULT_ERROR_UNKNOWN`, exit 0 |

`torch 2.11.0+xpu` inside the container drove both cards without
`--privileged`.

**Therefore the simple version-gap explanation is refuted as stated.** A
`26.14` container on an `xe`/kernel-7.x/`26.18` host is not sufficient on its
own to break multi-GPU context creation, because that is exactly this host and
it works. The remaining candidate deltas against the reporter's environment are
narrower: kernel `7.0.0-28-generic` here versus `7.0.10` there, Ubuntu 24.04
versus Fedora 44 host stack, GuC firmware revision, and per-host P2P/BIOS
configuration.

**What this does not establish.** The probe says nothing about the throughput
claim, and nothing about whether the full TP2 vLLM serve path completes — only
that the specific call the reporter identified succeeds here. Note separately
that a 27B FP8 model leaves too little room for KV cache on a single 32 GB B70
to reach the advertised 256K context, so TP1 is not a workaround for this
recipe.

Probe script and full log are in [`validation/`](validation/).

## Known Issues

Recorded here rather than edited into the contributor's text.

1. **Hardcoded contributor path.** The prose requires the model at
   `~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B`, but the mount is
   `-v /home/dom/.cache/huggingface/...`. The command fails for every other
   user. Should be `${HOME}` or a documented variable.
2. **`--privileged` is broader than required.** `--device=/dev/dri` plus
   `--group-add` for the render group is normally sufficient for Level Zero.
   The probe in this directory deliberately runs without `--privileged`.
3. **Unauthenticated network exposure.** `--net=host` with `--host 0.0.0.0`,
   `--port 8001`, and `--restart unless-stopped` publishes an unauthenticated
   OpenAI-compatible endpoint on every interface, persisting across reboots.
   The health check uses `127.0.0.1`, which obscures this. Worth an explicit
   warning in the recipe.
4. **`--trust-remote-code`** executes model-repository Python. Combined with
   `--privileged` this compounds trust, and it is likely unnecessary for this
   model on a supported vLLM.
5. **Malformed benchmark table.** Lines 124-129 of the contributed README are
   raw tab-separated values outside any code fence and without a header
   separator; they render as a single run-on paragraph.
6. **Metric selection.** The measured range is 28.3-34.7 tok/s; the PR's
   ledger row promoted "34 Tokens a second", the top of the range rather than a
   median. The series is also non-monotonic in prompt length (2000-token prompt
   faster than 500), which usually indicates run-to-run noise or warm state and
   is unexplained. Sampling is enabled (`temperature 0.7`), so no exactness
   gate applies.
7. **No evidence label.** `CONTRIBUTING.md` requires every result to state its
   evidence level; the submission states "Working" and placed a performance
   claim directly into the promoted ledger.

Issues 1-5 are straightforward fixes. Issues 6-7 are why this entry is
`community-reported` rather than promoted.

## Open Questions For The Contributor

1. Host kernel version, GPU driver (`i915` or `xe`), and compute-runtime /
   level-zero versions on the 2026-07-22 test host. Now that the version-gap
   explanation is refuted, the exact kernel and distro identity of all three
   hosts is what separates a working deploy from a failing one.
2. Benchmark methodology: how many repeats, what metric definition, cold or
   warm, and whether `cached_tokens` was zero.
3. Any logs or JSON from the original run.

## Disposition

Keep as a `community-reported` entry. The recipe is useful and clearly written,
and the flag and environment matrices are genuinely reusable even where the
performance number is not yet verifiable.

It should not enter `repro/` or `results/` at this evidence level. It would
move to `B70-tested` if the recipe runs here, and to `B70-verified` only if the
throughput claim is reproduced under a stated methodology. Both currently
require staging a ~51.75 GiB checkpoint on a host with ~34 GB free.
