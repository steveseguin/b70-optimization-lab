# Portable rolling release gates after the f300 source export

Recorded 2026-10-25 while the bounded lab rolling GPU proof is active. This is
a work plan, not a build receipt or a claim that the active proof passed. No
build, GPU execution, publication or frozen source change was performed for
this note. The coordinator must close the proof and its durable archive before
admitting the next resource-consuming task.

## What exists

| Artifact | Established scope | Missing scope |
| --- | --- | --- |
| Public source `9d6320c1b291b5835be9b6019bcf694a799deb48` | 294-file source recipe, generated-overlay build, accepted portable live PP4 32-output target/draft proof | Clean supported host, portable service, portable full-suite performance |
| Source `f30087882ab7cdd420b82858236d81a6489296ab` | Strict committed-source export, native/Python runtime closure, isolated extracted imports | Extracted native build, generated-build replay, portable rolling entrypoint, standalone v6 audit closure |
| Current rolling controller/native proof | Separate lab research configuration using the retained pending-provider native build and actual existing-MTP proposals | Terminal qualification still pending when this note was written; no speed or portable claim |

Keep the existing [public 9d source download](https://neural.download/downloads/own-engine/ownrt-source-9d6320c1b.tar.gz)
and its checksum identity unchanged. Its source archive SHA256 is
`e6a61c628da59bb02d92ac83329a78d8f41f0d1259e5a7ea8d1955820d0c8208`.
The accepted portable proof is
[`portable-live/pp4-proof/RESULT.md`](../../research/continuation-2026-10-25/portable-live/pp4-proof/RESULT.md):
32 outputs, 2,065 canonical target buffers/layouts, 73 canonical draft buffers,
117 true pairs, and retained proposal checks. This proves the named generated
deployment against the accepted lab reference, not independent CPU-reference
agreement or installation on another host.

The f300 archive is `/dev/shm/ownrt-source-f30087882-closure.tar.gz`, 2,585,661
bytes, SHA256 `2ab0893e39c2f658d05b6415d3e647c1eca31a90591aff97629b7cfcd3447c17`.
All 423 manifest-listed payload hashes and the 424-member archive inventory were
checked. Twenty explicit dynamic dependencies and isolated imports passed.
The [export receipt](evidence/source-bundle-f30087882-closure.json) records the
unbuilt, unpublished status. The extracted root is
`/dev/shm/ownrt-source-f30087882-extracted/own-xpu-runtime-source`.

## 1. Stage an extracted CPU build after the proof closes

This can use the existing frozen extraction; it does not need another native
source edit or any device execution. Recheck its manifest and archive hashes,
available RAM/tmpfs space, root storage floor, and installed compiler/runtime
inventory before admission. Use a fresh tmpfs output, four compilation jobs,
nice 19, idle I/O and a single `Restart=no` unit. Do not install packages,
change host settings, or retry automatically. Retain complete logs, exit status,
compiler/package/library inventory and the generated build receipt.

The already authenticated local deployment is
`/dev/shm/sc117-portable-deployment-20261025`; its trusted profile SHA256 is
`369ea09fc13015721df09a02841d5ef368d24455f25957d8fc2187e07a96999a` and its binding
SHA256 is `bfd016aa02b31f6183cd9c739d6d30e5449704268a8f4b136d3ff45302805fdf`.
Check these local inputs still exist and their metadata/artifact identities
remain valid. Do not repeat the full model hash just for a source rebuild.
Moved or changed payloads require a newly authenticated binding.

Proposed command, **not executed or queued**; run from the extracted root in
the separately admitted bounded unit:

```sh
python3 build.py /dev/shm/engine-build-portable-f30087882 \
  --jobs 4 \
  --generated-include /dev/shm/sc117-portable-deployment-20261025/include \
  --profile-sha256 369ea09fc13015721df09a02841d5ef368d24455f25957d8fc2187e07a96999a \
  --deployment-sha256 bfd016aa02b31f6183cd9c739d6d30e5449704268a8f4b136d3ff45302805fdf
```

[`build.py`](../build.py) compiles and links without running the engine. Its
dependency receipts must show the generated authority header was used and the
canonical host-bound header was not. Preserve the extraction for runtime use:
the pinned RoPE binary is a source-relative runtime asset. Capture the new
executable and authority hashes; a successful build does not inherit the 9d
portable proof or the lab rolling native binary's proof.

This build is useful even before a portable rolling adapter exists. If later
native changes are required, export and build that new committed revision;
never silently replace or relabel f300.

## 2. Close offline v6 replay separately from runtime source

[`release/source_bundle.py`](../release/source_bundle.py) now packages the
ring/live/pending/rolling runtime and the `rolling_provider` package. That is
not a complete standalone qualification packet. The v6 audit currently also
needs these lab-relative resources:

- `engine/tools/compare_pipeline_state.py`, `compare_draft_state.py`,
  `compare_provider_survival.py`, `compare_rolling_provider_survival.py`, and
  their relevant v6/negative tests.
- `gsq-rco-iq3s/state-bundle/reader.py`, dynamically loaded by the target-state
  comparator from outside the engine source root.
- Under `research/continuation-2026-10-25/`: `finalize_rolling_provider_proof.py`,
  `rolling_provider_trace_audit.py`, `finalize_pending_provider_proof.py`,
  `pending_provider_trace_audit.py`, `finalize_ring_live_proof.py`,
  `finalize_ring_proof.py`, `finalize_live_proof.py`, and
  `finalize_wavefront_proof.py`, plus the matching regression tests.
- The archive/recovery dependency chain: `archive_rolling_provider_proof.py`,
  `archive_pending_provider_proof.py`, `archive_ring_live_proof.py`,
  `restore_ring_live_archive.py`, and `restore_reused_state.py`, with tests.
- Hash-bound offline inputs: `recursive-provider-reference-v2.json`, its
  reference construction evidence, accepted target/draft manifests and sealed
  state payloads, and `live-draft-legacy-prefix.json`. These remain audit inputs
  only; the rolling executor must never consume expected answers or guesses.

Audit the exact transitive file set when creating the packet rather than treating
this list as an unchecked substitute for import/resource closure. The current
rolling archive helper includes helper files under `proof/` and source files
under `source/`; several helpers derive repository paths from `__file__`.
File inclusion alone therefore does not establish an executable extracted
layout. Preserve the expected layout or add explicit validated root/resource
parameters, then test without the original checkout on `sys.path`.

A separate versioned replay kit can preserve the f300 source artifact unchanged.
Alternatively extend the exporter at a new commit with explicit dependencies,
missing/untracked-input refusal and isolated import tests. In either case:

1. Extract only the published-candidate inputs into a fresh directory, with no
   fallback to the originating checkout or absolute lab files.
2. Restore and re-hash every sealed state and its metadata, then rerun the v6
   finalizer, journal/proposal provenance audit and survival comparison there.
3. Run the existing adversarial tests for stale/mutated wire metadata, lineage,
   cursor/pending mismatches, missing restore checks and wrong draft identity.
4. Retain exact raw 192-byte proposals, 360-byte final records, transport
   replies, ordered issue/completion journals and native logs. Do not replace
   raw witnesses with decoded summaries.
5. If a compact archive reuses an older archive, publish every required base
   archive by immutable URL/size/hash and verify restoration from those public
   objects. A USB path or a source URL is not closure for missing state bytes.

Explicit relocation may map hash-verified evidence inputs; it must not rewrite
the original run authority, source identities or recorded native receipts.

## 3. Add portable rolling admission without changing stable entrypoints

The current [`tools/rolling_ring_driver.py`](../tools/rolling_ring_driver.py)
is a lab controller. Packaging it does not remove its recorded adapter-plan and
lab observer dependencies. The existing
[`deployment/portable_live.py`](../deployment/portable_live.py) demonstrates
the separate portable lifecycle, but runs the earlier live wavefront scheduler.

Prefer a new `deployment/portable_rolling.py` with its own config/plan/result
schemas and tests. Generate native argv from authenticated model profile,
deployment binding, independently pinned launch policy, generated-build receipt,
explicit local BDFs and runtime library paths. Reuse reviewed rolling transport
with the portable Guard/lifecycle injected. Do not call the lab planner, Guard
or credential-dependent observer. Preserve existing portable live and lab
controllers and their defaults.

Admission must bind the actual draft manifest and model identities, EOS set,
context/output bounds, every runtime module including package initializers,
native capability and full binary receipt. Keep all diagnostic verification on
for the first bounded proof. Require explicit run admission, complete passive
holder/fault inventory, independently pinned observer invocation and cooperative
stop ownership. A model profile is not authorization to use devices. Private
credential brokers remain outside the source package; unknown inventory fails
closed. Add negative tests proving no lab planner/observer is invoked, unknown
capabilities cannot be enabled and the adapter imports/runs CPU planning from
the extracted tree.

Then qualify the new generated build/controller with bounded actual-MTP target,
canonical draft, true-pair, raw proposal and v6 journal checks. Report natural
coverage actually observed; do not borrow the forced pending gate's histogram.
Two/four-card results apply only to measured configurations. Six-stage CPU
fixtures and generic ring interfaces are not six-card GPU qualification; the
current pipeline controller does not admit one stage. Future quants/models keep
separate trusted profiles and must pass the onboarding gates in
[`reusable-onboarding-audit.md`](reusable-onboarding-audit.md).

## 4. Publish the exact qualified scope

After terminal proof/archive closure, update the stale opening status in
[`deployment/LIVE.md`](../deployment/LIVE.md) to link the accepted 9d portable
PP4 evidence while separately listing the new build/rolling gates. Add a rolling
guide only when its concrete commands and dependencies exist. Keep the public
9d recovery path available. Update the repository's
`docs/sc117-engine-review.md`, relevant neural.download source/recipe page and
package metadata, and skindeep's `content/own-runtime.html` through its generator
with explicit source, recipe and evidence links.

Use the publication skill and repository publication standard. The current
`native-text-lab-replay` manifest contract deliberately forbids `published`;
do not set its certification booleans merely because an archive is downloadable.
A completed native text build/asset contract needs explicit validator coverage.
Until then publish source/evidence with honest research or candidate status and
nonempty missing gates. Binary distribution additionally requires complete build
logs, toolchain/runtime inventories, section/RUNPATH checks and source closure;
do not turn a host-local executable into a portable binary claim.

Run the recipe/package validators, rendered desktop/mobile checks and focused
CI. Fetch each new public artifact and verify its bytes/hash before recording
remote verification. Keep all reuse dependencies publicly obtainable. No new
permission pause is implied: the owner authorized publishing, while the current
proof freeze and coordinator resource admission determine action order.

The bounded rolling diagnostic has no headline speed claim. A later matched
persistent twelve-prompt workload can measure decode intervals separately from
TTFT/full response, require uncached prompts and all 5,965 output IDs, and retain
bounded state qualification. Do not use fresh-server chains. Portable service,
clean-host certification, other model support and the six unresolved CPU
near-ties remain separate gates; no training is part of this work.
