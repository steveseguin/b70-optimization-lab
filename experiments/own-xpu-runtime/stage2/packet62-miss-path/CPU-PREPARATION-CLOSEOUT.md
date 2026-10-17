# Packet62 miss path — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can exact state placement and copy scheduling reduce packet61's speculative
miss cost? October 17, 2026; own runtime for the Unsloth Flash-Next UD-IQ3_XXS
quantized compressed model, packet49 target arithmetic/oracle, packet61
250 us spin plus HC fusion, native draft on rank1 and target split 23/25.
Preparation used CPU only on steve-b70s, nice19, cores 8–15 and 24–31,
OMP_NUM_THREADS=2 and Python `-B`. No model payload was read.

## Outcome

Five immutable selections share one device executable. Host and SYCL builds
pass. **70 changed-path CPU cases** pass (including 15 deliberate-corruption
controls that the state comparison rejects), across 86 fresh host rank pairs
plus five in-process reset repeats. All selections match packet56's **96 target
fixtures and 24 target tokens**. The flat copy fixture compares **11,899,255
bytes** including sentinel gaps across **975 descriptors**, using the same tile
routine compiled into the device kernel. The retained raw state equality pair
contains **409,200 bytes** per side.

All ten screen v3 CPU plans pass: five selections on lanes A and B. The packet
manifest records **357,437,560 logical bytes** including selection hardlink
views and **255,894,400 unique-inode bytes**. No GPU, service, sudo, reboot,
power, host-memory, swap or page-cache operation ran. No process outside this
preparation was stopped. Packet61's record chain and packet61x are untouched.

This closes CPU preparation only. Device exactness, speed, fit and full-chain
qualification remain unmeasured for packet62.

## What worked

The exact recurrent-bank write proof supports a third destination and six
prepared pointer-binding pairs. Hit, miss, mixed, cancellation, terminal,
abandoned redo, context-boundary and request-reset checks preserve complete
logical target state. Private storage is checked separately as zero; target
scratch and historical tails remain fully compared. Deliberate active-bank,
valid-QSA-prefix and omitted-stream restoration corruption stays visible.

Flat copy scheduling preserves the original copy-extent admission and reduces
source-accounted capture/restore submissions to one table upload plus one
kernel. Existing packet61 receipts show the exposed rollback is only about
0.74 ms and rank1 now limits the parallel halves. This changes the priority:
**screen `batch` against `control` first**.

## What failed or remains uncertain

The 11.4 ms miss penalty is not all rollback. The corrected target half takes
about 12.51 ms and remains required. Capture removal alone is expected to be
hidden behind rank1 in the current configuration. A complete rollback removal
would be only an optimistic 0.74 ms/miss ceiling; there is no measured or
justified point forecast for the new copy kernel.

Full scratch/QSA double buffering is not adopted: variable written prefixes
and historical tails need an additional exact preservation proof. The new
bank path rejects any recurrent writer lacking the existing full-write proof.
Controller dispatch is already measured in microseconds; only host bookkeeping
overlap is prepared.

Two CPU fixture/harness issues were corrected: runtime-overhead storage needs
process lifetime, and teardown receipts remain at the original launch path
after request reset. Earlier CPU attempts remain under the paths in
[RETENTION.md](RETENTION.md). There was no GPU fault or recovery operation.
A separate read-only source review found no concrete ownership, state-transition
or command-lifetime failure; tests remain the primary correctness evidence.

## Evidence and patches

- [Packet manifest and build sizes](packet.json)
- [Build receipt](build-device-receipt.json), [compile/link commands](engine-commands.json)
- [CPU gates](evidence/cpu-gates.json), [byte-fixture receipt](evidence/fixture.json)
- [Flat-copy fixture](evidence/flat-fixture.json)
- [Current miss attribution](evidence/diagnosis.json), [design](DESIGN.md)
- [Per-selection coordinator commands](WINDOW.md), [retention](RETENTION.md)

The independently written changes are the packet-local main/rank/state headers,
flat-copy fixture and selection parser. Parent source and compiled-object
identity remains hash-bound; no sealed parent was edited.

## When to revisit

The coordinator runs matched screens when the selected pair is available,
against the unchanged packet49 outputs. Inspect capture/restore counters and
hit/miss timing under the sealed selection. Only a matching exactness and speed
pass advances to the full record chain. Revisit broader double buffering only
with an explicit old-byte/tail proof, and revisit corrected-half scheduling as
the much larger remaining miss cost.
