# Round 19, card-to-card transport benches (ce + bcs, 2026-11-12 21:10-21:14)

Two short six-card benches (seconds each, no faults) to choose the transport for prompt exchanges.

## ce (`xchg_ce_bench.cpp`, `ce.txt`)

Peer pushes by EU stores with every store cache hint the compiler offers (`write_hint` L1 uncached / streaming /
write-through, L3 uncached / write-back), against EU pulls and the runtime's `queue.memcpy`, under four copy-path
settings (default, `UR_L0_USE_COPY_ENGINE_FOR_D2D_COPY=1`, plus `..._FOR_IN_ORDER_QUEUE=1`, `UR_L0_USE_COPY_ENGINE=0`).

- **EU stores into a peer: ~1.0 GB/s per card with every hint** (64 KiB to 4 MiB slices, 20 or 64 work-groups);
  the hints change nothing.
- EU pulls: 26-38 GB/s. `queue.memcpy`: 25-31 GB/s all six at once, 50-56 GB/s one card alone, the same under all
  four settings (so the setting is not honoured or not the limit). All values exact.

## bcs (`bcs_bench.cpp`, `bcs.txt`)

Level Zero immediate command list on the copy-only queue group (each card: group 0 compute + copy, 1 engine;
group 1 copy only, 1 engine), own slice -> five peers, all six cards at once:

| slice | copy engine push | SYCL memcpy | busy kernel alone | busy kernel + push |
|---|---|---|---|---|
| 64 KiB | 12.1 us (27.2 GB/s) | 14.9 us | 4,269.7 us | 4,252.9 us |
| 640 KiB | 113.4 us (28.9 GB/s) | 118.2 us | 4,259.4 us | 4,273.6 us |
| 4 MiB | 699.9 us (30.0 GB/s) | 771.4 us | 4,254.0 us | 4,391.5 us |

Values exact at every size. **The copy engine runs beside compute:** a 20 MiB-per-card push (700 us alone) adds
~0.14 ms to a memory-bound 4.26 ms kernel.

## Decision

Prompt exchanges move to copy-engine pushes as an opt-in (`OWN_PX_BCS`, helper bcs, `dsv41-work/bcs/`): no EU
time, true overlap with compute (one compute engine per card limited the EU-pull overlap), and posted writes instead
of peer reads (the reset suspect). EU-store pushes stay out for bulk data.
