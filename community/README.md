# Community Contributions

This tree holds work contributed from outside the reference lab. It exists so
that contributed evidence can be preserved and credited without being mixed
into the promoted ledger before it has been checked here. Runnable
contributions and informational field reports have different layouts and
different promotion paths.

Nothing in this directory is a lab result unless its entry explicitly records
a reference-lab run. A recipe here may be correct, partially correct,
hardware-specific, or wrong. Read the `STATUS.md` of a runnable entry before
running anything from it. Material under `field-reports/` is informational and
must not be treated as a recipe.

## Boundary Rule

| Directory | Contains | Who may add |
| --- | --- | --- |
| `results/` | Promoted, closed-out result packets | Maintainer, `B70-tested` or better |
| `repro/` | Copy-ready recipes for promoted results | Maintainer, `B70-tested` or better |
| `community/<entry>/` | Contributed runnable work and its validation history | Anyone |
| `community/field-reports/` | Unverified observations from community systems; no runnable assets | Anyone |

A runnable contribution enters `community/` first. It moves into `repro/` or
`results/` only after it reaches `B70-tested` or higher in this lab, and the
move is a separate maintainer commit that records what was actually run. A
`community-reported` entry never enters those directories, however useful it
is. A field report is not a promotion candidate by itself; a separately
identified recipe or result packet must be reproduced before promotion.

This boundary is about evidence provenance, not contributor trust. A careful
contributor with no B70 access produces `community-reported` work by
definition, because the reference hardware is here.

## Runnable Entry Layout

```
community/<contributor>-<model>-<topic>/
  STATUS.md      required; evidence label, provenance, what was tested here
  README.md      the contribution, or a clearly documented maintainer-corrected recipe
  reported/      optional; contributor-reported measurements and source artifacts
  validation/    logs, JSON, and commands from any local validation attempt
```

`STATUS.md` is mandatory and is the first file a reader should open. Copy
[`STATUS-TEMPLATE.md`](STATUS-TEMPLATE.md) to start one. An entry without a
current `STATUS.md` is incomplete regardless of how good its README is.

Material under an entry's `reported/` directory remains
`community-reported`, even when that entry also has separate reference-lab
validation. It is the right place for contributor CSVs, screenshots, and
results that are useful to preserve but have not been reproduced. Keep those
artifacts out of `validation/`, `repro/`, `results/`, `patches/`, and runnable
recipe paths so their evidence status is unambiguous.

The submitted state must remain recoverable from Git history. Maintainers may
correct a contributed `README.md` when that is safer or more useful than
carrying a known-bad copy-ready command, but the correction must be explicit:
identify it in the maintainer note and `STATUS.md`, preserve contributor
authorship/history, and keep contributor-reported claims separate from local
findings. Never silently rewrite provenance or turn a maintainer result into a
contributor claim.

One exception: a maintainer note may be added at the top of a contributed
README, clearly labelled as such and separated from the contributor's text by a
horizontal rule. Its purpose is to stop a reader who lands directly on the file
from mistaking a pending submission for a lab result, and to point at
`STATUS.md`. It states status and directs the reader; it does not argue with
the contribution.

## Field Report Layout

Community measurements and operational observations that do not contribute a
runnable recipe, patch, or configuration belong under
[`field-reports/`](field-reports/):

```
community/field-reports/<contributor>/<system-or-topic>/
  README.md      provenance, environment, review limits, and report index
  <report>.md    reported measurements with narrowly scoped maintainer notes
```

Field reports are always `community-reported` until a separate reference-lab
result reproduces a claim. Link and arithmetic checks may be recorded, but
they do not change the evidence level. Do not put launchers, patches, copy-ready
commands, model resources, or validation artifacts in this tree. If a
submission includes those assets, split them into a normal runnable community
entry and link the field report to it.

The contributor's submitted text remains recoverable from Git history.
Maintainers may reorganize and narrow a report before publication so that an
observation is not mistaken for a project recommendation or a controlled
comparison.

## Evidence Labels

Labels are defined in
[`docs/contribution-verification.md`](../docs/contribution-verification.md) and
are used unchanged here: `community-reported`, `B70-tested`, `B70-verified`,
`matching-hardware verified`, `invalid`, `superseded`.

Two fields are tracked separately in every `STATUS.md` and must not be
collapsed into one:

- **Evidence level** — what this lab has confirmed about the *claim*.
- **Patch review status** — whether the *content* has been read for safety.

A contribution can be safe to read and merge while its performance claim
remains entirely unverified. That is the normal state of a new entry.

## Validation Procedure

Local validation of runnable entries follows the eight-step procedure in
[`docs/contribution-verification.md`](../docs/contribution-verification.md).
Two points matter most in practice and are restated here:

1. **Protect current work.** `CURRENT.md` is authoritative for active lanes.
   Contributed work is validated only when the reference GPUs are free, in
   isolated trees, ports, and result directories, and never by disturbing an
   active runtime tree.
2. **Record negative results.** A contribution that fails to run here is
   evidence, not a non-event. Keep the logs in `validation/` and say plainly in
   `STATUS.md` what failed, on what host identity, and what remains unknown.

When a validation attempt is blocked by local infrastructure rather than by the
contribution itself, say so explicitly. "Not tested here because the box lacked
a container runtime" and "tested here and failed" are different findings and
must not be recorded the same way.

## Runnable Contribution Index

| Entry | Contributor | Source | Evidence level | Tested here |
| --- | --- | --- | --- | --- |
| [Qwen3.8 Flash-Next llama.cpp harness](bbeartheancient-flashnext-harness/STATUS.md) | [bbeartheancient](https://github.com/bbeartheancient) | [reviewed repository commit](https://github.com/bbeartheancient/flashnext-harness/commit/138cb88f326587d1cd9776510b2db0bd6a35455b) | `community-reported` | No contributed code/model run; full static read and clean patch apply check; no FP8 kernel transferable, MTP semantics retained as a cross-check |
| [Qwen3.8 27B Q4_K_M llama.cpp Docker](0xsero-qwen38-27b-q4km-docker/STATUS.md) | [0xSero](https://github.com/0xSero) | [public recipe at reviewed commit](https://github.com/0xSero/qwen38-b70/tree/17323a6b8948a7b4483633e24ba796df0fdb43a9) | `community-reported` | No container/model run; source read and both patch digests matched the lab artifacts; link-only because no source license was present |
| [Qwen3.6 27B FP8 TP2 Docker](dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md) | dominick253 | [PR #9](https://github.com/steveseguin/b70-optimization-lab/pull/9) | `B70-tested` | Yes; recipe runs at 30.171 tok/s median decode, inside the reported range |
| [Qwen3.6 35B UD-Q8_K_XL llama.cpp SYCL](dominick253-qwen36-35b-llamacpp-sycl/STATUS.md) | dominick253 | [PR #14](https://github.com/steveseguin/b70-optimization-lab/pull/14) | `B70-tested` | Yes; corrected MTP-off recipe, semantic/concurrency gates, 34,649-token retrieval, and cold fixed suite |
| [Qwen3.6 35B dynamic-FP8 vLLM Docker](dominick253-qwen36-35b-vllm-fp8/STATUS.md) | dominick253 | [PR #15](https://github.com/steveseguin/b70-optimization-lab/pull/15) | `B70-tested` | Yes; corrected exact-revision TP2 replay and functional gates; the contributor's 128–135 tok/s benchmark was not reproduced |
| [Qwen3.6 27B/35B INT4 vLLM Docker (B2, TP1)](dominick253-qwen36-int4-b2-1gpu/STATUS.md) | dominick253 | [PR #18](https://github.com/steveseguin/b70-optimization-lab/pull/18) | `community-reported` | No reference-lab model run; contributor artifacts preserved and offline-reviewed |
| [Qwen3.6 35B offline-FP8 vLLM B2 TP2](dominick253-qwen36-35b-fp8-b2-tp2/STATUS.md) | dominick253 | [PR #18](https://github.com/steveseguin/b70-optimization-lab/pull/18) | `B70-tested` | Yes; contributor reported 432.17 c12 tok/s; exact model/image/runtime replay reached 268.87 hardened and 286.00 contributor-privilege control; Gen4/Gen3 A/B did not explain the gap |
| [Qwen3.6 27B MTP Q4_K_M llama.cpp SYCL](dominick253-qwen36-27b-llamacpp-sycl/STATUS.md) | dominick253 | [PR #19](https://github.com/steveseguin/b70-optimization-lab/pull/19) | `B70-tested` | Yes; matching-name-and-size official artifact, exact engine commit, one greedy visible-output match, and 2K/32K/120K depth checks passed |
| [Qwen3.6 27B Q8_0 optimized llama.cpp SYCL fork](mndodd-qwen36-27b-llamacpp-sycl/STATUS.md) | [mndodd](https://github.com/mndodd) | [public fork](https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization) | `B70-verified` target-only TP1/TP2; speculative rows `B70-tested` | Yes; pinned fork plus separated lab patch, matched upstream-derived A/B, TP2 exact-output and TP1/TP2 logits gates, negative graph/profiler findings, and copy-ready build/launch/benchmark recipes |
| [Qwen3.8 27B GPTQ INT4 + native MTP vLLM XPU](sergiiob-qwen38-27b-vllm-xpu/STATUS.md) | SergiioB | [archived intake capsule](sergiiob-qwen38-27b-vllm-xpu/reported/source-manifest.json) | `B70-tested/performance`, `quality-rejected` as the no-loss default | Yes; native FP16 KV reached 34.1605 target-only and 87.6054 MTP4, with MTP parity to its target, but the GPTQ target failed a deterministic Python-result canary passed by Q8/Q4; [decision](sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md) |
| [Qwen3.8 27B Cold Fusion MTP llama.cpp SYCL](dominick253-qwen38-27b-coldfusion-mtp-llamacpp-sycl/STATUS.md) | dominick253 | [PR #34](https://github.com/steveseguin/b70-optimization-lab/pull/34) | `community-reported` | No reference-lab run; b10472 short probe 38.4 tok/s retained; 2026-08-18 refresh on b10488-7 / kernel 7.0.0-30 re-measured 22.73 tok/s |

## Field Report Index

| Collection | Contributor | Source | Evidence level | Reviewed here |
| --- | --- | --- | --- | --- |
| [TRX50 with Arc Pro B70/B60](field-reports/bosd/trx50-2xb70/README.md) | bosd | [PR #16](https://github.com/steveseguin/b70-optimization-lab/pull/16), [PR #17](https://github.com/steveseguin/b70-optimization-lab/pull/17) | `community-reported` | Documentation, links, semantics, and arithmetic only; benchmarks not reproduced |
| [Qwen3.8 on Arc Pro B65](field-reports/boyter/arc-pro-b65-qwen38/README.md) | boyter | X post relayed by maintainer; source URL/raw logs not captured | `community-reported` | Hardware specifications cross-checked; benchmark not reproduced and comparison identity incomplete |
| [mlx.fast Qwen3.8 27B Apple Silicon challenge](field-reports/kydo/mlxfast-qwen38-27b-mlx-challenge/README.md) | Kydo (`@0xkydo`) | X post relayed by maintainer 2026-08-21; original URL not captured | `community-reported` | Reviewed for transferable spec-decode ideas and scoring/gate design; Apple Silicon numbers not reproduced and not B70-applicable |
