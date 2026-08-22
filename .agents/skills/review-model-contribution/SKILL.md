---
name: review-model-contribution
description: Review, reproduce, benchmark, credit, and integrate outside model-optimization work in the B70 optimization lab. Use when a contributor submits or points to a patch, recipe, benchmark, model lead, issue, pull request, fork, or external optimization; when deciding whether a performance comparison is valid; or when updating community records, claims, guides, packages, result packets, and acknowledgements after review.
---

# Review Model Contribution

Leave an auditable result, a clear evidence classification, and durable credit
for the exact useful contribution. Keep this repository authoritative for its
maintained recipes, patches, and measurements.

## Apply The Ground Rules

- Credit concrete original work: a patch, technique, recipe delta, measurement
  packet, correction, or model-intake lead.
- Do not assign broad recipe or performance provenance to an external
  collection that republishes or combines pre-existing lab work.
- Keep contributor-reported claims distinct from reference-lab measurements.
- Preserve the submitted state and source identity even when maintainers adapt,
  correct, reject, supersede, or extend it.
- Treat evidence labels as statements about evidence, not about a person's
  trustworthiness.
- Do not promise execution, merging, ranking, support, or publication.
- Never expose credentials, private data, model weights, or unredistributable
  artifacts.

## 1. Establish Scope And Safety

1. Work from the repository root and read `AGENTS.md`, `CURRENT.md`,
   `docs/contribution-verification.md`, `community/README.md`, and
   `claims/README.md`. Read the relevant lane handoff, result, reproduction
   guide, package, and `community/STATUS-TEMPLATE.md` when applicable.
2. Inspect Git status, running jobs, active services, GPU use, storage, and the
   source trees named in `CURRENT.md`. Preserve unrelated and user-owned work.
3. Do not execute contributed code until its complete diff and commands have
   been read. Do not disturb an active lane to accelerate review.
4. State what the review covers: provenance only, static patch review,
   functional test, correctness reproduction, performance A/B, clean-host
   recipe replay, or some bounded combination.

## 2. Capture Intake Without Inflating It

Record unknown fields as `unknown`; do not guess.

Capture:

- contributor's chosen display name and optional public profile/site links;
- source issue or PR, base and candidate commits, patch checksum, and date;
- right-to-submit statement, license, and third-party sources;
- exact model revision, quantization, runtime, hardware, command, workload,
  metric, cache/speculation policy, quality gate, logs, and reported result;
- closest known-good baseline and the contributor's claimed intentional delta.

Place runnable outside work under
`community/<handle>-<model>-<topic>/`, beginning with `STATUS.md`. Preserve
original artifacts under `reported/`; place only local review output under
`validation/`. Put non-runnable observations under
`community/field-reports/`. Create or update a `claims/<id>.json` entry when a
performance claim has enough accepted identity to enter the claims lifecycle.
Do not promote intake directly into `repro/`, `results/`, a package, or a
landing-page recommendation.

## 3. Determine What Is Actually New

Build a simple provenance split before assigning credit:

| Part | Classification |
| --- | --- |
| Existing lab code, recipe, result, or documented technique | Pre-existing lab work |
| Exact submitted delta authored by the contributor | Contributor work |
| Imported dependency or third-party technique | Third-party work |
| Maintainer fixes, validation, packaging, or later optimization | Lab follow-up |

Compare source history, patches, and experiment dates. Similar output or a
newer polished recipe does not establish authorship. Classify the submitted
value as one or more of:

- original code or optimization technique;
- runnable recipe or portability improvement;
- reproducible measurement packet;
- correctness finding or negative result;
- model/intake lead;
- compilation or repackaging with no newly identified delta.

Give acknowledgement appropriate to the useful class. Reserve measured boost
credit for a concrete delta that survives a matched A/B.

## 4. Choose The Smallest Sufficient Validation

- **Model lead or informational report:** verify identity and usefulness; do
  not invent a benchmark obligation.
- **Documentation or portability recipe:** replay the documented path in an
  isolated environment. Measure performance only if the submission makes a
  performance claim.
- **Correctness or bug fix:** reproduce the failure, apply the smallest delta,
  and run targeted plus model-specific regression gates.
- **Performance patch or tuning:** require a matching control/candidate test
  after correctness passes.
- **Reported result without runnable identity:** retain as
  `community-reported`; request missing evidence rather than approximating it.
- **Different hardware or quality class:** record a separate observation. A
  B70 run does not verify another hardware class, and lower precision or a
  different target is not the same comparison.

Stop safely and record the blocker when licensing, source identity, unsafe
commands, unavailable hardware, model absence, active lab work, or missing
essential evidence prevents the planned review.

## 5. Reproduce And Benchmark Carefully

1. Use disposable source/build trees, isolated environments and ports, and a
   unique result directory.
2. Pin and record hardware topology, model bytes, runtime commits or image
   digest, patch set, dependencies, flags, and environment.
3. Reproduce the closest known-good baseline in the same window when feasible.
4. Gate correctness before speed. Apply the model-specific quality policy in
   `AGENTS.md` and the current result packet. Treat precision, KV, cache,
   speculation, prompt, or acceptance-policy changes as different quality
   classes unless equivalence is demonstrated.
5. Compare the complete submitted delta against the control. For close results,
   alternate control/candidate order, retain repeats and failures, and report
   dispersion rather than selecting the best run.
6. Preserve commands, logs, structured results, output hashes, and negative
   findings in durable repository paths.

Calculate a boost only for a like-for-like comparison:

```text
boost_percent = 100 * (candidate_metric - control_metric) / control_metric
```

Name the metric and report the control, candidate, absolute delta, relative
delta, repeats, and uncertainty. Do not calculate or advertise a boost when
model/checkpoint, quantization or quality class, GPU topology, runtime base,
workload, cache policy, metric window, or quality outcome differs materially.
Do not award boost credit from a single noisy run.

## 6. Classify The Outcome

Use the repository evidence labels unchanged:

- `community-reported`
- `B70-tested`
- `B70-verified`
- `matching-hardware verified`
- `invalid`
- `superseded`

Update the claims lifecycle separately when applicable: `submitted`, `queued`,
`reproducing`, `confirmed`, `confirmed-adjusted`, `refuted`, `stale`, or
`lab-verified`. Append history; never silently rewrite a prior outcome.

Distinguish recognition from evidence status:

- **Acknowledged:** useful report, model lead, correction, or negative result.
- **Credited:** a specific original patch, technique, or runnable recipe delta.
- **Validated boost:** a credited delta with a matching quality-passing A/B.
- **Integrated:** credited work adopted into a maintained lab recipe or package.

A contribution may be useful and credited without being integrated. An
unreproduced result may be acknowledged without receiving a validated boost.

## 7. Carry Credit Into Every Adopted Surface

Always update the contribution's `STATUS.md`, local validation artifacts, and
claim history if present. When work is adopted, also update every surface that
uses it:

- canonical source patch or pinned identity under `patches/`;
- experiment note and matching A/B evidence under `experiments/` or `data/`;
- promoted `results/` packet and `repro/` guide when promotion gates pass;
- the guide's direct patch/version/command links and dependency-closure table;
- relevant `packages/<id>/package.json` dependencies and patch list;
- `repro/guide-catalog.json` classification or dependencies;
- public model row only when its evidence and guide classification qualify.

At the point of use, include a compact credit record:

```text
Contribution: <exact patch, technique, recipe delta, or finding>
Contributor: <chosen display name and optional profile link>
Status: <acknowledged | credited | validated boost | integrated>
Validated effect: <control> -> <candidate> (<signed percent>), or not measured
Evidence: <repository path>
Included in: <guide, package, or result paths>
```

Update an existing contributor profile/index when the repository provides one.
Until then, make the contributor name, links, exact delta, and evidence
machine-findable in `STATUS.md` and every promoted result using the work so a
future profile generator can index them. Link externally to the contributor at
this exact credit point; keep the maintained guide and recipe in this
repository.

## 8. Close The Review

Run the validators affected by the change, especially:

```bash
python3 tools/validate-claims.py
python3 tools/validate-repro-guides.py
```

Inspect the final diff and report:

- exact contribution and provenance split;
- what was reviewed and executed;
- baseline, candidate, quality, and boost result if comparable;
- evidence and claim classifications;
- acknowledgement and integration locations;
- unresolved risks, missing evidence, and next validation step.

Do not imply that review is complete when required work remains, and do not
withhold acknowledgement merely because the measured result was neutral or
negative.
