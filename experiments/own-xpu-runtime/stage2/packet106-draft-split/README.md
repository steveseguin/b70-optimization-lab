# Packet105: exact target head row split

CPU-only implementation in progress, copied from packet97 after the committed
97e startup repair (386faa9ee). Parent packets and orchestration remain frozen.
Rank1 keeps rows [0,202240); rank0 evaluates [202240,248320) from the verified
current normalized final.mix, after its own target half. No speculative hidden
state or draft arithmetic changes. Compute-queue and copy-engine transfer
placements are separate candidates. All device quality and speed are pending.

The 1.0685% gain is packet87t’s prediction, never a measured result.
