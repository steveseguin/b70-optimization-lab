# Packet 37: pipeline, prepared launches and exact p33 kernels

This packet starts from packet32-pipeline (`2e8ec7585c`), ports packet35-hostpath
(`3f32fb1ad9`) and integrates the already gated packet33 kernels. It targets the
quantized compressed Unsloth UD-IQ3_XXS release of Qwen3.8 Flash-Next with the
unchanged `iq3-p17-detmath-v2` arithmetic and full BF16 state/cache. No device ran
during preparation. No model speed is claimed.

Each native rank owns one card and one in-order queue. Rank 0 owns the lookups
and first 24 layers. Rank 1 owns the second 24 layers, final mixer and target
argmax. Packet32's shared-byte transport, speculation, target verification,
rollback, sticky errors and cooperative ownership protocol remain in place.

## Prepared host path

Both ranks capture launches after upload and dispatch selection. Rank 0 captures
both recurrent-state parities. Swapping banks also swaps the prepared operation
map and captured command vector; a miss drains and swaps them back. It never
rebuilds bindings during rollback. Owner generation guards reject released or
invalidated allocations. The per-launch application success path has no strings,
map lookup, allocation or device query. Real events remain tracked and drained;
only redundant in-order dependencies are removed.

The independent GNU argument audit reconstructs operations from the current
buffer map, rather than comparing two copies of a potentially stale capture.
It compares allocation IDs, addresses and serialized operation members with the
selected captured command after parity changes. Intel-host runs independently
check arithmetic and state; argument serialization uses GCC clear-padding.
The CPU mock issue benchmark covers the original 14 families and five p33 paths.
Its allocation hooks cannot establish allocation behavior inside SYCL or a driver.

Rank 0 requests lookup read-ahead and touches each mapped page after uploads.
Mappings remain alive until shutdown. This is not pinning and does not guarantee
future residency. CPU full-model gates use bounded layer streaming and skip the
large lookup-residency pass. Every rank half records prepare/enqueue/wait time,
faults, process/thread context switches, affinity and load. Family enqueue times
are present only in class mode, avoiding clocks at each normal token launch.

## Kernels and selection

The registry adds `p33.down.select`, `p33.down.bank`, `p33.gate.restrict`,
`p33.dense.segment` and `p33.qsa.shape`. The slower route.rank4 candidate is not
adopted. Dense segment covers every runtime dense family and eligible Q6/Q8/F32/
BF16 format, with separate split1/split4 arithmetic. See [KERNELS.md](KERNELS.md).

K2 retains 200 repetitions, full-size rotating buffers for payloads above 8 MB,
and exact byte comparison on the card. It retimes the packet29 incumbents and
p28/p33 alternatives. Each small fusion must beat the sum of its selected member
costs in every covered format/site; members win ties. HC attention and FFN sites
are checked separately. Missing measurements fail admission. The measured map
is written for both ranks; the second map is an alias of the single-card timing,
not a claim of independently measured second-card speed.

`dispatch-p33.json` is a CPU correctness exercise, not a measured choice.
`dispatch-incumbent.json` retains the historical packet29 baseline identity.
Only the coordinator's K2 output establishes this packet's measured dispatch.

## CPU gates and handoff

[build-receipt.json](build-receipt.json) is the final source/binary/gate authority;
[BINARY-HASHES.md](BINARY-HASHES.md) lists retained coordinator binaries. Historical
receipts under `inherited-packet32/` are provenance only. The new receipts cover
mini-model guess patterns, forced misses, rollback bytes, both host compilers,
sanitisers, failure injection, argument limits, precision flags at compile/link,
prepared-owner invalidation, zero-allocation mock issue and real eight-token runs
against the unchanged v2 oracle: all eight runs passed, totaling 64/64 tokens
and 3,072/3,072 layer outputs. The mini suite passed 144 cases; the resident
host matrix passed 48. Device identity and speed remain unmeasured.

The expanded kernel CPU suite passes 24,138,800 finite comparisons across four
fresh processes. It covers 120 eligible class/format pairs in both splits. Every
dense exceptional-value comparison also agrees on both compilers. An additional
linked fixture covers all 36 dense template instantiations, with 216 exact
comparisons per fresh owner; K1 repeats it on the card. Inherited
expert NaN diagnostics remain unqualified; no tolerance upgrades them to exact.

[WINDOW.md](WINDOW.md) contains exact K0, K1a, K1b, K2, W0p, W2s, W2n, W2d and
W2c commands. W2d is an all-hit diagnostic, never a speed result. W commands need
a nice-0 coordinator parent; affinity and its exact LD_LIBRARY_PATH are retained.
No wrapper treats historical journal lines as new faults or latches a pre-launch
refusal. [DEADLINES.md](DEADLINES.md), [LIFETIME.md](LIFETIME.md) and
[ROLLBACK.md](ROLLBACK.md) retain the admission and graceful-stop rules.

[INTEGRATE.md](INTEGRATE.md) inventories the changes against packet32 for the
later packet36 draft-provider merge. A native controller is described there but
not implemented here. Packet36 and all other packet directories remain read-only.

## Rebuild on CPU

Run from the repository root with inherited affinity. `device` is compilation
only. Never execute its binaries during CPU preparation.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet37-merged2/build.py all
```

The build driver uses one compiler job per build. Full-model CPU campaigns run
one pair of host ranks at a time and monitor aggregate anonymous memory below
9 GiB. No power, host-memory, swap or page-cache setting changes are made.

## Retention

The full p33 CPU gate JSON exceeds 1 MiB because it preserves each class/format/
split/tail result in four fresh processes. Keep it: a summary cannot reconstruct
its per-case checks or exceptional diagnostics. Reproduce it with
`p33_candidate_gates.py` and the generated fixtures. Scratch logs are archived
with byte-verified member hashes before deletion. Ignored build trees, input
manifests, fixture inputs and sealed binaries remain available for coordinator
windows; no outside evidence is removed. [ARTIFACTS.md](ARTIFACTS.md) explains
the retained large argument logs and their byte-verified restoration.
