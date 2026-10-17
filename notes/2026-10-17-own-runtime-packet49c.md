# Packet49c: packet49b plus packet51's exact winning kernels

CPU preparation is in progress on steve-b70s. This is a separate packet at
`experiments/own-xpu-runtime/stage2/packet49c-round2/`, derived from packet49b
at `192ee28f2` and the packet51 winners recorded at `c1ce0db7d`.
Neither predecessor is edited. The coordinator owns all GPU windows.
The packet49 oracle and waiting packet49b model units remain untouched.

## Registered scope

Keep split32 QSA, the p48b expert gate/up and down paths, SPEED6 dispatch,
23/25 target split, draft rank1, capacity4096, BF16 KV and existing memory
limits. Add only packet51 routing, HC attention/FFN gate and low projections,
and attention output/combine. Apply them at every matching production call,
including M=1 and both separately scheduled M=2 rows. Leave expsgate,
GDN QKV and HC injection otherwise unchanged.

Arithmetic remains `iq3-p49-split32-v1`. Reuse the existing packet49 CPU oracle
through a read-only symlink and hash binding; model-window receipts must bind
its completed manifest, determinism result, KD capture and completion receipt.
No new oracle is launched. Full-model agreement remains a coordinator gate.

## CPU preparation and storage plan

Build GNU host, Intel device code (compile only) and ASAN/UBSAN serially, with
`nice -n 19`, `taskset -c 4-15,20-31`, `OMP_NUM_THREADS=2`, and `python3 -B`.
Run fresh fixture, ownership, plan, snapshot, sanitizer and admission gates.
An independent reviewer checks integration, STOP behavior and the final seal.
No GPU, service, sudo, host setting or model payload operation is authorized
for this preparation.

The initial check found 20,984,156,160 root bytes free. The copied 2.5GB build
budget plus both chains would require 22,765,608,960 bytes: a 1,781,452,800-byte
shortfall. The new packet preserves the 8GB free floor, all 5,818,804,480 bytes
of packet49b's pending model writes, and 500MB oracle growth. Its own chain
has a 5,946,804,480-byte peak allowance, including128MB early receipts.
Preparation will reduce only its own regenerable compiler scratch and
sanitizer binary duplication. The proposed retained build cap is650MB;
actual final fit must pass a fresh check. CPU preparation may temporarily
use up to2.5GB while preserving the other chain and free floor. No unrelated
scratch is deleted.

## Coordinator handoff plan

Use a new `packet49c-round2/build/device-cards01-a` chain for
K0 → K1a → K1b → K2 → W0p. The model sequence is
KD → W2m → WS → WSs → WS128x → WS128, with `--wait-oracle`.
Both fresh K1 windows must include the new kernels' byte fixture.

Packet49b holds only its chain-local flock while waiting for the oracle.
The coordinator may write its chain's `STOP`, then verify the queue has exited
without starting KD before queueing packet49c's model phase. STOP releases
no storage reserve by itself. The old chain and its historical files remain.
Exact commands and checked switch tests will be included in the final runbook.

No integrated device speed is claimed. Packet51's operator gains do not prove
an end-to-end gain. The39.422 tok/s record is unchanged; WS128 is the matching
128-token comparison, not the separate512-token publication gate.
