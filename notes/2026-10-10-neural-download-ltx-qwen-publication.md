# LTX and Qwen publication, October 10, 2026

This CPU-only pass adds the [LTX reproduction guide](../repro/ltx25-continuation-stream-b70-145f-20261010/README.md), [package](../packages/ltx25-continuation-stream-b70-145f-20261010/package.json) and generated [video details](../models/ltx25-continuation-stream-b70-145f-20261010.html). The guide carries frozen timing arrays, native qualification receipts, model/runtime pins, recovery commands, a progression table and a deliberately blocked promotion attestation. The existing live service and all run directories were left untouched.

The result is 5.2415 seconds per six new video seconds in each of two 52-period early windows for packet135. The 5.248/0.875 figure is the earlier raw delivery-cadence summary. Neither proves sustained unthrottled speed. Packet137 has a saved startup identity and CPU tests, but no retained native qualification verdict in this snapshot. It receives no borrowed timing. Seam/audio acceptance remains open even though the recorded tensor/output comparisons pass.

The [Flash-Next family](../models/qwen-flash-next.html) now leads with the A367 certified 46.854250 tok/s result, replacing its diagnostic 48.53 figure. This is four B70s and the 125B-A6B model. The [one-card Qwen27B guide](../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md) and [two-card guide](../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) now identify their current image digests, build chains, source-closure limits and verification procedures. The two-card 875 tok/s result belongs to Qwen27B MTP0 with 64 short requests, not Flash-Next. Its two passes are same-server, output-exact capacity evidence; `speed_gated` is false. Public copy and separate curves retain that scope. Borrowed prefill figures were removed from current-profile tables.

## Generation and deployment

The source inputs are package manifests, `repro/guide-catalog.json`, family manifests, `families/catalog.json` and the family coverage registry. The package catalog and HTML are generated, not hand-edited:

```bash
python3 tools/validate-repro-guides.py --write-package-catalog
python3 tools/build-family-pages.py
python3 tools/build-model-pages.py
python3 tools/sync-public-result-summary.py
```

The authenticated GitHub Pages API reports `build_type=legacy`, source `main:/`, custom domain `neural.download`. This matches the repository's prior site commits. Push the verified commit to `main`; Pages builds automatically. Deployment and live bytes can be checked without a model server:

```bash
git push origin main
gh api repos/steveseguin/b70-optimization-lab/pages/builds/latest
```

Fetch the public catalog, home page, LTX page and Qwen pages with a cache-busting query after the Pages build reports that commit. No owner credential or manual deploy is required by the observed setup.

## Checks and remaining work

[CPU validation receipt](../data/neural-download-publication-20261010-validation.json) records the workflow commands. Local and remote recipe-publication validation passed for the two existing manifests; that does not confer public source closure on LTX or Flash-Next. LTX's offline verifier audits 19 file hashes, 29 timing windows and 15 public rows. Catalog, generator, evidence, unit, browser-logic and link/path checks cover the new publication. The browser check executes the real catalog JavaScript without a browser or server. Visual rendering at phone/desktop widths was not exercised because no device-isolated browser was available under this task's no-GPU/no-server restriction.

The literal-pin audit reported 231 already-drifted historical pins out of 318, chiefly frozen Flash-Next clients. No old receipt pin was rewritten to hide this. The Flash-Next guide points to the frozen verifier identity and keeps the historical host-control wrapper outside current operating instructions.

Publishing these pages is distinct from certifying a fresh-host recipe. Remaining work:

1. LTX: publish the complete sealed parent/runtime inputs with immutable URLs and hashes; make the source reconstruction portable; qualify a clean supported host; obtain the owner's seam/audio judgement; retain matched unthrottled repeats and packet137 native evidence. Only then create and validate a real recipe-publication.v2 manifest and consider changing the strict headline.
2. Flash-Next: publish the missing model-tree metadata (or full equivalent file manifest), an installable environment lock and exact rebuilt kernel stage; provide a compliant portable launcher; complete independent replay. The existing native result stays valid within its recorded scope.
3. Qwen27B: retain the digest-pinned image route while closing the driver/clean-host and full source-build gaps already listed in each guide. A multi-user speed headline additionally needs matched fresh-server performance qualification.

No GPU, server, systemd, port8188 or `/dev/dri` operation was used. Commands ran at nice19 with `OMP_NUM_THREADS=2`. Temporary validator/test directories were automatically removed; this task created no persistent `/tmp` scratch.
