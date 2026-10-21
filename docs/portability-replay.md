# Portability Replay Standard

How a package's portability `missing` items — *clean-host replay*,
*non-originating-host replay*, *tested (clean-host) platform installation*,
*built and replayed container image*, *clean-host source build* — get closed.
The rule throughout: a portability claim is a receipt, not an intention.
One executed replay on one clean host closes the item **for that host class**
and is recorded as such; it does not generalize further.

## Definitions

- **Originating host**: the lab machine that produced the package's result.
- **Clean host**: a machine (or a fresh OS install / new bare user with no
  lab state) that has never run the lane. It starts from the published
  artifacts only — package page, repro guide, and the files those reference.
  Using lab-internal paths, caches, or undocumented knowledge invalidates
  the "clean" property; note the breach and classify the run as a
  non-originating-host replay instead.
- **Host class**: GPU model/count + driver major + OS major. A replay on a
  second B70 host closes "non-originating-host replay" for the B70 class
  only.

## Procedure (per package, per host class)

1. **Pick the package's delivery vehicle**, exactly as published:
   - portable source bundle (e.g. `repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70`:
     hash-pinned `native-sources.tar.gz` + `build-native.py` + BUILD.md);
   - container image (`built and replayed container image` items);
   - GGUF/guide lane (driver + oneAPI + llama.cpp per the package guide).
2. **Platform installation** — follow the package's stated driver/oneAPI/
   runtime steps verbatim. Record every deviation (versions, mirrors,
   kernel). This execution closes the *tested platform installation* item.
3. **Build/fetch** the runtime from the published artifacts. For hash-pinned
   bundles: verify every published checksum *before* building; record the
   verification output. A skipped checksum fails the replay.
4. **Run the package's own gate** — its documented replay/qualification
   command (the repro guide's replay script or the package's `commands`),
   at the package's measured configuration.
5. **Compare** against the package's published numbers under its own metric
   definition. Report both figures; a replay that is slower but bit-exact
   still closes the *replay* item (speed portability is reported, not
   gated), unless the package says otherwise.

## Receipt set (required fields)

Per replay, one directory `data/portability-replays/<date>-<host>-<package-id>/`
containing:

- `receipt.json`: host (GPU/count/VRAM, PCIe link), OS/kernel, driver,
  oneAPI/runtime versions, package id + catalog version, vehicle
  (bundle/container/guide) with its published hashes, verification output
  for every checksum, exact commands, deviations from the guide (or `none`),
  gate result, measured figures vs published, exactness result where the
  package defines one, wall time, `passed: true|false`.
- Raw outputs: build log, gate output/logs, and the checksum verification
  transcript. Raw bytes, not summaries.
- `environment.json`: the clean-host definition evidence (fresh install /
  fresh user; what state was present).

Missing receipt fields are marked `unknown`, never guessed — same rule as
[contribution-verification.md](contribution-verification.md).

## Closeout path (per package)

1. Receipt lands under `data/portability-replays/` and is committed.
2. Remove the closed item from the package's `missing` list in
   `packages/<id>/package.json`; add the receipt path to the package's
   `evidence`. Host-class scope stays in the item text if only one class is
   closed (e.g. "clean-host replay (B70 class)").
3. Regenerate the catalog and model pages (`tools/build-model-pages.py` and
   the catalog generator); run the doc-link and manifest-path validators.
4. If the replay **failed**, the package's `missing` item stays, and the
   failure receipt is linked from the package — failures are evidence, not
   blockers to hide.

## Current burn-down order (by leverage)

1. **qwen38-flash-next-iq3xxs-ownrt-tp1/tp2** — portable bundle exists and
   is hash-pinned end to end; supported-host device qualification rides
   packet178 (device window); clean-host replay follows on the second B70
   host. This is the template execution for this standard.
2. **qwen38-27b-fp8-vllm-tp1 / tp2** — container+docker lanes with the
   largest user base; platform-install + container replay.
3. **qwen35 family + qwen38-27b-autoround-int4** — `clean-host replay` items
   on measured vLLM lanes.
4. llama.cpp GGUF lanes (q8/q4km variants) — driver/oneAPI install +
   guide replay per package.
