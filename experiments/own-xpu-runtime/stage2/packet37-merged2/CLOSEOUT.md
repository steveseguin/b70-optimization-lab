# Packet37 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can packet32's two-rank pipeline retain exact target output and rollback while
using packet35's prepared host path and packet33's qualified kernel vocabulary?
The base is packet32-pipeline (`2e8ec7585c`), with the packet35 host changes
(`3f32fb1ad9`) and packet33 source techniques. The target is the quantized
compressed Qwen3.8 Flash-Next UD-IQ3_XXS release, unchanged arithmetic-v2 and
BF16 state/cache. No GPU was used and no model speed is claimed.

## Outcome

Both ranks capture stable launch commands after upload and dispatch selection.
Rank0 retains both alternate-buffer parities and swaps the prepared maps and
command vectors together with the state banks. Forced misses preserve packet32's
drain, rollback and redo rules. Independent argument reconstruction compares the
current unprepared bindings against the selected prepared commands, including
operation bytes, allocation identities and pointers. Generation guards reject
released owners. Rank0 retains lookup mappings and performs the native residency
pass after upload. Per-half receipts add preparation, enqueue, waits, page faults,
context switches, affinity and load to the inherited pipeline receipts.

The registry gains p33.down.select, p33.down.bank, p33.gate.restrict,
p33.dense.segment and p33.qsa.shape. Dense segment specializes all eligible runtime
class/format pairs and both reduction splits without changing their reduction
order. K2 retimes packet29 controls, p28/p33 candidates and the three small fusions;
a fusion wins only against the sum of its selected members in every covered
format/site. Ties retain members. Its measured map is emitted for both ranks,
with the second explicitly an alias of the one-card measurement.

## What worked

Final counts and exact binary identities belong to [cpu-tests.json](cpu-tests.json)
and [build-receipt.json](build-receipt.json). They are written only when every
required gate passes. Mini-model validation covers 130 GNU cases, seven Intel
cases and seven ASan/UBSan cases, including exhaustive short forced-miss patterns,
long mixed guesses, state bytes and disabled prompt overlap. The resident host
matrix adds 48 cases across compilers, timing modes, legacy/prepared issue and
none/ngram/all-hit/all-miss modes; its GNU audits compare 19,722 argument blocks.

The candidate suite completes 24,138,800 finite comparisons in four fresh
processes across both host compilers, covering 120 dense class/format pairs in
two splits. Dense exceptional-value comparisons agree on both compilers. Four
fresh combined fixture processes each check 114 fixtures, 3,024 GEMV comparisons,
196 small-GEMV comparisons and 51 adapter-only comparisons. The additional linked
dense fixture passed 1,296 comparisons in six fresh owners (two per compiler,
including ASan/UBSan), covering all 36 specializations in each owner.

The zero-allocation mock issue test covers 19 actual launch families and 387,072
measured launches. Owner invalidation, argument guards, cooperative fault
injection, controller/IPC rules, W0p host handovers, precise compile/link flags
and the 1,024-byte capture limit remain gated. There are 353 measured kernel
captures; the maximum is 744 bytes and the 1,025-byte negative case is rejected.

Full-model validation passed all eight fresh runs: four modes under each host
compiler, each producing 8/8 oracle tokens and 384/384 oracle layer fixtures
(64/64 tokens and 3,072/3,072 layers total). Both all-hit runs recorded seven
hits; both forced-miss runs recorded seven exact rollbacks and redos.
The GNU modes also passed 777,440 prepared/unprepared argument comparisons. The eight
real-*.json receipts and two real-campaign*.json receipts are the evidence;
CPU execution time is not a model performance measurement.

### Independent reviews and fixes

[review-prepared.md](review-prepared.md) covers parity selection, stale-pointer
risks, rollback and lifetime. [review-dense-independent.md](review-dense-independent.md)
covers reduction order and every extended dense family.
[review-k2-selection.md](review-k2-selection.md) covers the fusion-versus-members
rule. [review-linked-fixture.md](review-linked-fixture.md) covers the added complete
K1 template fixture. Findings were fixed, including independent argument recapture,
complete linked-template coverage and binding the linked-host fixture receipts
to their exact binaries. Admission tests also reject old journal incidents,
pre-launch fault latching and altered coordinator library paths.

## What failed or remains uncertain

No device binary was executed or used for discovery. K0, K1a/K1b, K2 and W0p
must qualify native JIT, exactness, dispatch selection and concurrent ownership
before W2s/W2n/W2d/W2c. Native allocation behavior, lookup residency, real overlap,
card memory and speed remain unmeasured. K2 output is not available until its
window. W2d is explicitly an all-hit diagnostic, never a speed result.

The inherited expert exceptional/NaN diagnostic remains unqualified; no tolerance
turns it into an exactness claim. The inherited p33 QSA specialization applies
to capacity128/budget2048 with one token; context256 uses the unchanged general
fallback.
Do not infer a W-window QSA gain from the fixed-shape K2 result. CPU argument
serialization uses GNU clear-padding; Intel separately checks tokens/state and
kernel identity. The allocation mock excludes SYCL/driver internals.

Packet36's rank1 draft provider and a native controller are not built here.
[INTEGRATE.md](INTEGRATE.md) gives the file inventory and integration obligations.

## Evidence and patches

Sources, immutable input identities, reviews, compact receipts, full candidate
results, verified gzip evidence and the binary seal are retained. Ignored build
outputs and coordinator inputs remain ready; preparation scratch is archived
with byte checks and removed.

## When to revisit

Reopen on a changed graph, allocation identity,
kernel, compiler or failed coordinator gate; never reuse old receipts across
those changes. This closes the CPU packet preparation, not the model lane.
