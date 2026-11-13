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

## sync + lat (`bcs_sync.cpp` / `sync.txt`, `bcs_lat.cpp` / `lat2.txt`, 21:30-21:33)

- **Kernel -> copy-engine ordering works three ways** (one card, kernel still running when the copy is queued, copy
  waited ~1 ms, all values right): the kernel's SYCL event's native handle as the copy's wait event; an own Level
  Zero event signalled on the SYCL queue's native immediate command list; the native handle of
  `ext_oneapi_submit_barrier()`.
- **Hand-off latency, one way** (pairs 0-1 / 2-3 / 4-5 at once, 2,000 round trips, payload then flag, the receiver
  polls a flag in its own memory): copy engine 7.9 / 7.6 / 7.1 / 7.6 us at 256 B / 4 / 16 / 64 KiB; EU stores into
  the peer 3.3 / 5.4 / 5.1 / 6.3 us. So the copy engine is for bulk prompt slices; small decode / check exchanges stay
  on the EU paths.
- Polling a flag in the PEER's memory never saw the update (the bench's "pull" mode timed out): flags must be polled
  in local memory, written by the peer (as the engine's XchgPull does).
- Open: EU stores to one peer moved 64 KiB in ~6 us one way here (>= 10 GB/s), against ~1 GB/s in the all-gather
  bench (`xchg_ce_bench`: five peers, SIMD32, back-to-back rounds). Not explained yet; does not change today's plan.
- 21:27:49 driver engine reset on card a3:00.0 when I killed an earlier hung version of `bcs_lat` mid-spin (my
  bench's bug above; evidence `dsv41-work/faults/engine-reset-20261112T2127/`, probe passed 21:28). The bench now
  skips every later wait after one timeout.

## ord + sg + sq (22:47-22:53): why EU pushes were slow, and the fix

- **Ordering holds** (`bcs_ord.cpp`, `ord.txt`): the receiver checked one word per 64-byte line of the payload the
  moment it saw the flag, 4 KiB to 1 MiB, 50-2,000 rounds per size: 0 words missing, for copy-engine pushes and for
  EU stores + system fence + flag.
- **The slowness is concurrent destinations** (`xchg_sg.cpp`, `sg.txt`): EU stores from one card into ONE peer:
  4.0 / 16.8 us for 64 / 640 KiB alone (16-40 GB/s), 9 GB/s per card with all six sending in a ring; into FIVE peers at
  once: ~0.87-1.1 GB/s, even with only one card sending. Sub-group size 16 or 32 and waiting between rounds change
  nothing.
- **One destination at a time is fast** (`xchg_sq.cpp`, `sq.txt`): five launches per exchange, each writing this card's
  slice to one peer (card c to c + p in launch p, so each card receives from one sender at a time): **41 GB/s per card
  at 640 KiB with all six cards** (pulls 36), 20-21 at 64 KiB (pulls 26), 6.4 at 16 KiB (pulls 7.6); values exact.
  One launch whose work-groups walk the peers in order is still slow (1.2 GB/s at 640 KiB): work-groups drift apart
  and the card again writes to several peers at once.
- Reading: all-gathers can be one-way posted writes at full speed if each card targets one peer at a time. That is
  the transport for the exchanges that are pulls today (no peer reads: the host-reset suspect), and an alternative to
  the copy engine for prompt slices (the copy engine still frees the EUs and overlaps compute).
