# Packet 26 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the committed packet18 arithmetic and schedule retain exact v2 outputs with
less host bookkeeping, and can dedicated non-GEMV candidates be admitted one
class at a time? Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS quantized compressed
version. Arithmetic: `iq3-p17-detmath-v2`; pinned starting files are in
[source-proof.json](source-proof.json). Work date: 2026-10-11. Preparation is CPU
only; two-card B70 runtime measurements belong to the coordinator's windows.

## Outcome

The implementation, independent reviews and registered CPU gates are complete. The all-new streaming check matched all eight tokens and all 384 layer fixtures against v2. No device ran and no model speed
is claimed. Default dispatch retains packet18 kernels. A candidate is admitted
only by exact K1 and measured K2; each class must be below 0.9 times its control,
and all registered formats within a GEMV class must independently clear that bar.
Full final CPU gate results and binary identities are recorded in
[build-receipt.json](build-receipt.json) and [cpu-tests.json](cpu-tests.json).

## What worked

The identical owner-only CPU mock changed from 31.3621 ms to 0.200046 ms median
for 2,181 submissions. It measures owner bookkeeping, excluding SYCL and Engine
work; W2 must prove the <=12 ms host enqueue target. See
[host-issue-benchmark.json](host-issue-benchmark.json) and [HOST-PATH.md](HOST-PATH.md).

Dedicated compile-time operation/stage kernels preserve the complete-subtree
and original odd-tail trees. Independent arithmetic, write-range and interpreter
reviews found and fixed dispatch normalization, capture enforcement, temporary
capacity, fixture-output binding and optional GEMV bridge admission issues.
[Identity-tree tests](identity-tree-tests.json) cover 1,056 symbolic decompositions.
[Fixture gates](fixture-gates.json) compare both CPU compilers and fresh processes;
[sanitizer gates](sanitizer-mini.json) cover both dispatches, modes, card counts
and four work-item-order seeds. The default arithmetic/schedule carryover is
hash-bound in [carryover-proof.json](carryover-proof.json).

## What failed or remains uncertain

No device candidate is admitted yet. K0, K1a/b, K2, W0 and W2/W2m/W2c remain the
coordinator's work. Expected microseconds in README are hypotheses. Packet25
half-table/staged candidates are not linked; unsupported names are rejected.

The extra nonfinite GEMV diagnostic exposed NaN-sign disagreement inside the
unchanged baseline. Its original source and failure remain retained. GEMV
qualification uses strict finite fixtures; required NaN-route tests remain exact.
See [NONFINITE-GEMV.md](NONFINITE-GEMV.md). The independent wrapper audit also found a missing-workload-repetition case hidden by duplicate rows; K2 now fails it, with a retained regression test.

Invalid attention-index diagnostic
bytes in the historical baseline are work-item-order dependent; valid registered
model shapes remain subject to exact comparison and invalid inputs remain errors.

The literal two-total-copies/card/token gate is not met by the retained packet18
schedule. Peer fences, snapshots and readbacks are explicit. The separately scoped
H2D control budget is <=2/card/token and kernel-parameter uploads remain zero per
launch; [copy-budget.json](copy-budget.json) does not disguise that distinction.

## Evidence and patches

Source is local to this packet; imported older packets are read-only dependencies.
Focused `base-*.patch` files retain the default/new dispatch integration changes.
The [preparation findings](preparation-findings.json) retain failed CPU harness
attempts and their corrections; rejected nonfinite source/receipts are under
[evidence/gemv-nonfinite-diagnostic](evidence/gemv-nonfinite-diagnostic/receipt.json).
[WINDOW.md](WINDOW.md) contains exact commands, and [DEADLINES.md](DEADLINES.md)
separates expectations, submission budgets, wait limits and watchdogs. The complete four-process fixture receipts are preserved in
[evidence/fixture-gates-full.json.gz](evidence/fixture-gates-full.json.gz). Compression
was verified byte-for-byte before replacing the large repeated teardown listing
with summaries; `fixture-gates.json` records both hashes and restoration identity.
Build artifacts are ignored; `build.py` reconstructs them without executing a device.

## When to revisit

Run the coordinator's K0/W0/W2 control first to measure host enqueue time and
reproduce the scratch's roughly 12 tokens/s. Qualify K1a/b and K2 before choosing
any specialised class, then compare W2m and labelled W2c. The reference target
remains 28.49 tokens/s. Device results decide adoption; this preparation does not
close the model lane or infer a speed from launch count.
