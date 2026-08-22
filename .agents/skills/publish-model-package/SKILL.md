---
name: publish-model-package
description: Build, update, validate, and publish neural.download model packages and human-facing deployment guides from repository evidence. Use when adding a model, quantization, GPU topology, OS/container variant, reproducible recipe, featured benchmark, context-performance curve, package manifest, guide page, or contributor record; or when promoting an experiment or validated contribution into packages/, repro/, results/, or the public model library.
---

# Publish Model Package

Leave a runnable in-repository recipe, closed dependencies, honest measurements,
and a public guide that distinguishes what was measured from what remains pending.

## 1. Establish The Publication Boundary

1. Work from the repository root. Read `AGENTS.md`, `CURRENT.md`,
   `docs/neural-download-packet-standard.md`, `packages/README.md`, the relevant
   lane handoff/result/repro files, and the nearest existing package.
2. Inspect Git and active lab state. Preserve unrelated work, services, model
   downloads, and protected runtime trees.
3. Identify the exact package tuple: model revision, quantization, runtime and
   patches, card count/topology, OS/delivery form, cache/KV/speculation policy,
   and benchmark shape. Treat a material change as a separate operating profile
   or package rather than silently combining results.
4. Use `$review-model-contribution` first when outside work is being reviewed.
   Publish only the locally adopted delta and its exact credit; keep this
   repository authoritative for the maintained recipe.

## 2. Close The Recipe And Evidence

- Pin model and companion artifacts, runtime/image identity, patches, commands,
  environment, hardware, and validation inputs. Link every required patch or
  script directly from the guide; a user must not need chat history or an
  external cookbook to reconstruct the lane.
- Keep raw or structured measurements under `data/`, promoted summaries under
  `results/`, runnable recipes under `repro/`, and package discovery metadata
  under `packages/<id>/package.json`.
- State quality class, cache state, prompt/output shape, metric definition,
  repeats, dispersion, failures, and known limitations. Never turn an
  unverified report, synthetic diagnostic, or different precision/topology into
  a lab-verified package headline.
- Record missing clean-host or beginner-flow work explicitly. Do not make a
  candidate appear production-ready by omitting its gaps.

## 3. Publish Context Performance Without Inventing It

Apply these rules to decode, prefill, TTFT, memory, or any other curve:

1. Publish only measured points from the exact declared package or operating
   profile. **Never extrapolate, interpolate, simulate, or estimate missing
   context points.** Do not manufacture a zero-context point because a graph
   axis begins at zero.
2. A line may visually connect adjacent measured points, but every marker must
   be an observed aggregate at that exact actual prompt/context length. Describe
   it as measured points, not a continuous performance guarantee.
3. Do not derive a curve from a one-point headline, join unrelated experiments,
   mix requested context with actual token counts, or reuse another quant,
   runtime, card count, cache state, concurrency, output length, sampler, or
   speculative policy. Split differing profiles and label them plainly.
4. Keep test controls fixed across a profile. Prefer several lengths spanning
   short context through the supported maximum. Store each repeat and the
   aggregation method in evidence; expose the aggregate and sample count in
   `performance_profiles`.
5. Define every metric. Decode is after TTFT under the declared interval rule.
   TTFT is measured directly. Publish a derived prefill rate only when the
   numerator, denominator, formula, and approximation are disclosed in the
   evidence and guide.
6. Extract points programmatically from the cited evidence and verify the
   published values against every source row. Keep context values positive,
   unique, and ascending. Link the exact repository evidence from the profile.
7. If comparable measurements do not exist, omit `performance_profiles` and
   show **sweep pending**. Keep the one-point headline scoped to its benchmark;
   absence of a curve is more accurate than a plausible-looking guess.

## 4. Build The Human Guide And Credit

- Lead with model identity, cards/VRAM, quantization, runtime, status, and the
  measured headline. Explain that rows with different configurations are not
  automatically comparable.
- Provide copyable preflight, build/apply-patch, launch, health, benchmark, and
  stop/recovery commands. Include direct in-repository links to all patch and
  evidence dependencies.
- Present context graphs as an expandable detail layer with exact-value
  tooltips, zero-based axes where useful, evidence links, scope text, and a
  readable table in the package guide. Preserve accessible text when scripting
  or graph rendering fails.
- Carry exact contributor acknowledgement wherever an adopted delta is used:
  identity, contribution, status, measured effect or `not measured`, evidence,
  and optional profile links. Award a boost only from a matched quality-passing
  A/B; do not credit a repackaged collection for pre-existing lab work.

## 5. Validate And Publish

1. Regenerate and validate the package catalog:

   ```bash
   python3 tools/validate-repro-guides.py --write-package-catalog
   python3 tools/validate-repro-guides.py
   python3 -m unittest tools/test_validate_repro_guides.py
   ```

2. Validate any changed claims and the contribution record when applicable.
3. Inspect the rendered guide at narrow and wide widths, graph tooltips, copy
   controls, internal links, missing-profile state, and script-disabled text.
4. Inspect the diff, run `git diff --check`, commit focused paths on `main`, and
   push only after local validation passes.
5. Wait for package CI and Pages deployment, then fetch the public catalog and
   guide with a cache-busting query. Verify the live package/profile count,
   evidence links, graph labels, and pending states before reporting completion.

Report the exact package/profile added, evidence range and sample count, tests,
deployment state, remaining gaps, and commit. Never summarize a pending or
failed publication as complete.
