# Reproduction Guide Certification

The presence of a directory under `repro/` does not, by itself, mean a new
user can reproduce a result from a clean machine. The directory historically
contains several different artifact types: complete-ish expert recipes,
originating-host replay gates, record capsules, active research status, and
superseded material. This document makes those differences explicit while the
guides are upgraded.

The machine-readable authority is
[`repro/guide-catalog.json`](../repro/guide-catalog.json). CI validation is
performed by [`tools/validate-repro-guides.py`](../tools/validate-repro-guides.py).
Recipes that claim public source or binary closure must also follow the
[`Recipe Publication Standard`](recipe-publication-standard.md), include a
`publication-manifest.json`, and pass
[`tools/validate-recipe-publication.py`](../tools/validate-recipe-publication.py).

## Classifications

| Classification | Meaning | May the website say “Install guide”? |
| --- | --- | --- |
| `starter-guide` | Replayed from a clean supported OS, complete dependency closure, beginner-oriented checks and recovery | Yes |
| `candidate-portable-repro` | Substantial install/restore material exists, but clean-host certification or a shared platform dependency is still missing | No |
| `lab-replay` | Replays a result when lab source trees, binaries, caches, models, or topology already exist | No |
| `record-capsule` | Preserves exact result identity, evidence, and commands for audit/history | No |
| `research-status` | Active or unresolved work; not a promoted reproduction | No |
| `archived` | Superseded material retained for provenance or patch archaeology | No |

No current guide is certified as a `starter-guide`. This is an honest starting
point, not a failure. Certification is earned by a fresh replay, not by adding
a label.

## Required Dependency Closure

Every future starter guide must put this table near the top of its README. A
shared in-repository platform guide may satisfy a row, but the model guide must
link it directly and name the tested version.

| Component | Required identity and link |
| --- | --- |
| Host platform | Supported OS/kernel, Intel driver packages, firmware if applicable, Docker/container runtime or native toolchain |
| Accelerator toolchain | Exact compute runtime, Level Zero, oneAPI/compiler, PyTorch XPU and collective versions used by the guide |
| Runtime source/image | Immutable Git commit or container digest; no floating branch/tag as the only identity |
| Project patches | Direct in-repository links to the canonical aggregate patch/bundle and its base commit/checksum; experiment directories alone are insufficient |
| Model | Publisher repository, immutable revision, filenames, sizes and checksums or a generated direct-verification manifest |
| Configuration | Checked-in environment/configuration with visible card count, precision, KV, context, cache and speculation policy |
| Execution | Install, download, build or image acquisition, verify, launch, smoke and stop/recovery commands |
| Validation | Fixed quality gate, benchmark definition, expected outcome, evidence path and last clean-host replay date |

If no patch is required, the guide says `none; pinned upstream runtime/image`
rather than silently omitting the row. If a driver package is fetched from an
official repository rather than stored here, the guide links the official
repository, pins the package version, records the signing-key fingerprint, and
includes a post-install version check.

## Certification Gates

A `starter-guide` requires all of the following:

1. A supported clean OS install or disposable host/image starting point.
2. No undeclared dependency on `/home/steve`, `/mnt/fast-ai`, an existing
   compiler cache, unpublished binary, dirty tree, or maintainer-only service.
3. All in-repository dependency links resolve and all model/runtime/patch
   identities are immutable.
4. The install/download/build path is executed exactly as written.
5. Hardware and model identity checks pass before serving.
6. The endpoint starts, passes smoke and fixed quality gates, and stops cleanly.
7. The guide records the clean replay evidence and date.
8. A second reader can distinguish required settings from optional performance
   experiments and known failures.
9. Any claimed public release has been downloaded by its direct public URLs and
   reverified against the tracked publication manifest.

Containerization does not remove the host-platform requirement. A container
can pin userspace but still depends on a compatible host kernel, Intel driver,
device permissions and topology.

## Upgrade Order

The first candidate is the two-card official Qwen3.8 FP8 container reproduction
because it already has an immutable image digest, exact model revision,
download command, model verifier, launcher, benchmark and quality boundary.
Its missing pieces are bounded: a tested host-platform guide, a clean-host
replay, and beginner recovery instructions. Direct-I/O and ordinary-path model
verification were added and passed on the current host on 2026-08-21.

The first one-card starter should follow from a small model in the model-intake
queue after its USB artifact is present and a clean upstream llama.cpp/SYCL
baseline has passed. Large historical record stacks should not be forced into
starter status merely because their headline performance is attractive.
