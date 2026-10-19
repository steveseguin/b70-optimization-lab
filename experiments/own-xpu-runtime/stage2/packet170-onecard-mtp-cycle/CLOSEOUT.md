# Packet170 complete one-card MTP accounting — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet166's causal M2 layer mechanism support a conservative complete
cycle at least 3% faster than packet58aj's one-B70 31.966820 tok/s record?
October 19 CPU-only review, Unsloth UD-IQ3_XXS quantized compressed target,
unchanged `iq3-p49-split32-v1`, context4096, BF16 KV. Historical official-derived
INT8/group16 91,392-prefix draft; complete target verification remains required.

## Outcome

Close without a build. At acceptance .787 the complete-cycle budget is
54.273508 ms. Current record class shares and a supported full-cycle bound
are absent. The explicitly charged sensitivity is 63.613909 ms (28.0913 tok/s),
but is not measured speed or proof of a hardware limit. The favorable
free-feedback/free-selection case cannot satisfy the evidence gate.
Declared memory accounting fits at 18.216 GB target cache and 103.314 GB host
requirement, including conservative exclusion of blocks53–57. No implementation
lifetime census or new model-quality gate is claimed.

## What worked

Packet166's independently exact causal per-class ratios are retained. The
reproducer checks all twelve current-record streams and discovers that their
device class fields are placeholders. Native cache-size timing, actual 18 GB
misses, historical route replay and CPU expert costs are kept distinct.
Full-cycle drain amortization and a drain-free baseline are accounted for.
The memory table includes current resident lookups, private state and all
reserves, without reviving the obsolete 121.65 GB host objection.

## What failed or remains uncertain

No measured packet58aj M1 class distribution exists in these receipts.
Complete M2 embedding/PLE, full head, exposed host issue, wrong-proposal
cache service, feedback frequency and target selection cost remain unknown.
The shared-cache design's draft misses/pollution have no supported price.
Historical two-card class mappings and capacity normalization cannot bound
those unknowns. Missing data are JSON null, not free work.

## Evidence and patches

[Analysis](README.md), [decision contract](PREREGISTRATION.md),
[cycle.py](cycle.py), [cycle.json](cycle.json),
[negative audit](dnr-audit.json), [grep](dnr-scan.txt),
[new negative row](DO-NOT-REPEAT.md),
[dated note](../../../../notes/2026-10-19-own-runtime-packet170.md).
All inputs are repository text/JSON, hash-bound in cycle.json. The 16 ignored
native receipts are retained as exact gzip snapshots under `inputs/`, with
original and archive hashes in [inputs.json](inputs.json). No runtime patch
or unavailable external model artifact is needed for this calculation.
Existing trees, shared screens and operational files were not edited.

## When to revisit

A distinct mechanism with supported current-line per-class costs and complete
cycle ≤54.273508 ms at .787 acceptance, including cache shrink, incorrect
proposals, serialized drafting, feedback/repair and state selection. Reprice
against a drain-free baseline if applicable. Prove private-state/extents and
staging lifetime inside the declared memory bounds, and retain excluded RAM,
reserves, original target verification and fresh-process exactness gates.
This closeout does not authorize a diagnostic launch or reopen old mechanisms.
