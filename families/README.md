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

Family-only research packets may carry a typed `featured_metric`, but it must
bind to one normalized `measurement_id` and one exact `sample_index` or
`point_x`. Its metric, value, unit, workload, and evidence must match that
measurement exactly. This exposes an existing result without pretending that
the packet is an installable catalog package or allowing presentation metadata
to manufacture a headline.

Every family with packets declares one `primary_packet_id` for its main action.
This is a deliberate editorial binding: the renderer never chooses a call to
action from raw decode speed. Model relevance, recipe usefulness, and evidence
maturity are resolved when curating the binding; all other packets remain one
click away in the complete packet list.

Optional family `featured_results` are presentation-only exact pointers. A
non-empty list has one `hero` and any number of `support` entries; every entry
binds a declared metric to one `measurement_id` and one exact `sample_index` or
`point_x`, and carries an explicit evidence-scope label. The renderer never
selects a raw maximum, equates `lab-measured` with a full quality gate, or
coarsens distinct runtime, graph, workload, and topology identities into one
variant/TP result. Families without this list fall back only to already-curated
packet featured metrics, not arbitrary measurement insertion order.

Optional packet `projection` metadata must pin both `prompt_tokens` and
`output_tokens` before any measured-vs-projected `OPT` grade is calculated.
The same fail-closed rule applies on family cards, package pages, and the home
page; generic planner defaults are never used for a captured measurement. A
heterogeneous benchmark suite retains its measured speed and shows `OPT —`.

Curated grades are deliberately narrow. `CAP` is a revision-scoped capability
or quality assessment and `EVID` is packet evidence maturity. Each needs a
scope, basis, review date, and evidence list. `OPT` remains separate: it is the
measured rate divided by the ML Bottleneck engine's projected tuned-run target
for the exact pinned workload. Popularity is a dated signal, not a grade.

The `EVID` rubric is fail-closed: **A** means a sealed, replayable packet with
exact identity, independent repeat evidence, full applicable quality gates,
and a clean-host or equivalent reproduction; **B** means strong exact lab
evidence and quality coverage with one disclosed sealing, determinism, or
replay limitation; **C** means bounded research evidence with material
promotion or provenance gaps; **D** means a valid measured snapshot whose
scope is too narrow for a deployment claim. A lower grade keeps useful work
visible; it never upgrades a speed observation into a supported recipe.

Measurements do not transfer across weight revisions. Source patches and
configuration findings may transfer when the manifest records the shared
architecture boundary and the later revision independently exercises the path.

Quantized exports of the same base weights are not separate weight revisions
or architecture siblings. They may be listed under the base revision as
`quantized_artifacts`; each child pins its quantization, repository, available
artifact revision, and evidence. Measurements and packets name that child with
`artifact_id` while retaining the common base `revision`. A missing artifact
revision stays explicitly unpinned rather than turning the quantized repository
into a surrogate model revision.

Allowed public coverage states are `lab-measured`, `lab-screened`,
`community-measured`, `estimated`, `closed`, `quarantined`, `unsupported`, and
`missing`. `lab-screened` means a bounded boot/canary observation without a
publishable performance measurement; a missing cell is unknown, not zero.
Graphs contain only lab- or community-measured curves. Screened, quarantined,
and estimated records stay out of measured SVGs.

Coverage matrices are exact Cartesian slices. Legacy matrices default to MTP
rows and TP columns. New matrices may set `row_axis`, `column_axis`, and
non-empty `fixed_selectors` to show other questions such as context × TP or
quantization × TP without creating a second schema. Every cell must be
explicit. A measured cell cites `evidence_id`; an estimated cell cites only an
`estimate_id`; a separate optional `packet_id` links a recipe without implying
that the recipe is measurement evidence. When a measured context cell comes
from one exact point in a measured curve, `point_x` must match both the row
or column axis and an existing `points[].x` value in that evidence record; the
displayed metric label is derived from the cited point rather than trusted as
free text.

Estimates are first-class, versioned records with selectors, metric, value and
interval, engine name/version/snapshot SHA-256, generation time, basis
measurement IDs, limitations, and a durable record path. They are always
`not_for_promotion`, never enter measured curves or featured metrics, and are
replaced by adding a superseding record rather than rewriting history.

`coverage-registry.json` is the fail-closed inventory of public evidence. One
canonical lane groups every package manifest, repro guide, promoted result,
and rapid snapshot that describes the same public deployment lane. A result
index spanning materially different profiles remains its own canonical
family-assigned lane instead of being attached to one profile. A lane maps to
either a published family, an explicitly named planned family, or an explicit
`archive`/`excluded` disposition with a reason. Planned-family assignment is a
coverage backlog marker only: it creates no measurement, estimate, packet, or
public family page.

The validator discovers package and repro artifacts from their catalogs and
result/snapshot entry points from `results/`. It rejects unmapped files,
duplicate artifact assignments, unknown families, and artifact-kind drift.
Coverage accounting uses canonical registry lanes; it never totals repeated
rendered cells from overlapping family matrix views.

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
