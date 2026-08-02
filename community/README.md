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
  README.md      the contribution as submitted
  validation/    logs, JSON, and commands from any local validation attempt
```

`STATUS.md` is mandatory and is the first file a reader should open. Copy
[`STATUS-TEMPLATE.md`](STATUS-TEMPLATE.md) to start one. An entry without a
current `STATUS.md` is incomplete regardless of how good its README is.

The contribution `README.md` is preserved as submitted. Corrections belong in
`STATUS.md` under "Known Issues", not silently edited into the contributor's
text. If the recipe is later fixed, record the fix and its author explicitly.

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
| [Qwen3.6 27B FP8 TP2 Docker](dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md) | dominick253 | [PR #9](https://github.com/steveseguin/b70-optimization-lab/pull/9) | `B70-tested` | Yes; recipe runs at 30.171 tok/s median decode, inside the reported range |
| [Qwen3.6 35B UD-Q8_K_XL llama.cpp SYCL](dominick253-qwen36-35b-llamacpp-sycl/STATUS.md) | dominick253 | [PR #14](https://github.com/steveseguin/b70-optimization-lab/pull/14) | `community-reported` | No |
| [Qwen3.6 35B dynamic-FP8 vLLM Docker](dominick253-qwen36-35b-vllm-fp8/STATUS.md) | dominick253 | [PR #15](https://github.com/steveseguin/b70-optimization-lab/pull/15) | `community-reported` | No |

## Field Report Index

| Collection | Contributor | Source | Evidence level | Reviewed here |
| --- | --- | --- | --- | --- |
| [TRX50 with Arc Pro B70/B60](field-reports/bosd/trx50-2xb70/README.md) | bosd | [PR #16](https://github.com/steveseguin/b70-optimization-lab/pull/16) | `community-reported` | Documentation, links, and arithmetic only; benchmarks not reproduced |
