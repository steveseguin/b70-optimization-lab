# Model-family coverage data

The public model library is organized around model families, not around
individual quantized files. A weight update is a revision of a family; a GGUF,
AutoRound, FP8, or other compression is a deployment variant of that revision.
Architecture-distinct siblings may share a publisher/version family only when
their transfer boundary is explicit; they remain separate model variants and
never share measured performance.

Family manifests use `neural-download-model-family-v1`. They keep these claims
separate:

- **lineage**: architecture geometry and which implementation work transfers;
- **measurements**: exact revision, quantization, runtime, topology, flags,
  workload, metrics, quality, and evidence for each observed arm;
- **closed cells**: combinations that are impossible, unsupported, quarantined,
  or deliberately stopped by a preregistered gate;
- **estimates**: model projections with an engine and snapshot identity; an
  estimate is never a measurement or evidence for packet promotion;
- **packets**: runnable or audit-oriented artifacts at their honest maturity;
- **views**: compact projections of the measurements into the public mini
  graphs and coverage matrices.

Measurements do not transfer across weight revisions. Source patches and
configuration findings may transfer when the manifest records the shared
architecture boundary and the later revision independently exercises the path.

Allowed public coverage states are `lab-measured`, `lab-screened`,
`community-measured`, `estimated`, `closed`, `quarantined`, `unsupported`, and
`missing`. `lab-screened` means a bounded boot/canary observation without a
publishable performance measurement; a missing cell is unknown, not zero.
Graphs connect only homogeneous states within the same metric identity;
estimated series are visually distinct and never joined to measured series.

The generator also enforces site-wide assignment: every package in
`packages/catalog.json` must belong to exactly one family, and its family
packet ID must match the referenced package manifest. Research-only packets
may additionally appear in a family without entering the public package
catalog.

Regenerate the pages with:

```bash
python3 tools/build-family-pages.py
python3 tools/build-model-pages.py
```

Validate without writing with:

```bash
python3 tools/build-family-pages.py --check
```
