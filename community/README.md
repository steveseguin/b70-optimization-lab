# Community Contributions

This tree holds work contributed from outside the reference lab. It exists so
that contributed evidence can be preserved and credited without being mixed
into the promoted ledger before it has been checked here.

Nothing in this directory is a lab result. A recipe here may be correct,
partially correct, hardware-specific, or wrong. Read the `STATUS.md` of an
entry before running anything from it.

## Boundary Rule

| Directory | Contains | Who may add |
| --- | --- | --- |
| `results/` | Promoted, closed-out result packets | Maintainer, `B70-tested` or better |
| `repro/` | Copy-ready recipes for promoted results | Maintainer, `B70-tested` or better |
| `community/` | Contributed work at any evidence level | Anyone |

A contribution enters `community/` first. It moves into `repro/` or `results/`
only after it reaches `B70-tested` or higher in this lab, and the move is a
separate maintainer commit that records what was actually run. A
`community-reported` entry never enters those directories, however useful it
is.

This boundary is about evidence provenance, not contributor trust. A careful
contributor with no B70 access produces `community-reported` work by
definition, because the reference hardware is here.

## Entry Layout

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

Local validation follows the eight-step procedure in
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

## Index

| Entry | Contributor | Source | Evidence level | Tested here |
| --- | --- | --- | --- | --- |
| [Qwen3.6 27B FP8 TP2 Docker](dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md) | dominick253 | [PR #9](https://github.com/steveseguin/b70-optimization-lab/pull/9) | `community-reported` | Partial; multi-GPU runtime probe passed, recipe not run |
