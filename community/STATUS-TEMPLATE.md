# <Contribution title>

Copy this file to `community/<entry>/STATUS.md` and fill it in. Delete guidance
lines that do not apply. Mark unknown fields `unknown` rather than guessing;
a guessed field is worse than a missing one because it looks like evidence.

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` \| `B70-tested` \| `B70-verified` \| `matching-hardware verified` \| `invalid` \| `superseded` |
| Patch review status | unreviewed \| read, no execution \| read and executed here |
| Tested in reference lab | no \| partial \| yes |
| Safe to merge as documentation | yes \| no \| with changes |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor:
- Source PR or URL:
- Commits:
- Right-to-submit statement present: yes \| no
- Third-party material and attribution:

## Claim

State the contributor's claim in one sentence, with the number as they reported
it. Do not restate it as a lab finding.

## Contributor Environment

Fill from the submission. Missing entries are what to ask for first; the
required list is in
[`docs/contribution-verification.md`](../../docs/contribution-verification.md).

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | |
| OS / kernel | |
| GPU driver (`i915` / `xe`) and version | |
| compute-runtime / level-zero | |
| Engine / image and exact version | |
| Model repo and revision | |
| Quantization (weights / KV / activations) | |
| Command and environment variables | |
| Prompt / output / context lengths, concurrency | |
| Cache and speculation policy | |
| Metric definition, repeats, dispersion, TTFT | |
| Logs / JSON / durable links | |

## Reference Lab Environment

Record the local host identity whenever anything is executed here, even a
probe. Host identity is the usual explanation for a reproduction gap.

## What Was Actually Run Here

Be specific and bounded. Name what was executed, what was not, and why. If
nothing was executed, say so and give the reason.

## Findings

Separate confirmed observations from hypotheses. A version-gap theory that
predicts a failure is not the same as having reproduced the failure.

## Known Issues

Defects found by review, each with file and line. These are recorded here
rather than edited into the contributor's README.

## Open Questions For The Contributor

The specific things needed to raise the evidence level.

## Disposition

What happens to this entry now, and what would change it.
