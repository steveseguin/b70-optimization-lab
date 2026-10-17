# Packet49b storage and retention

All new builds/evidence live under `/home/steve/own-xpu-runtime-results/packet49b-gemv/`
on the root filesystem. This is not extra disk capacity. The packet's `build`
and `evidence` links point there. `oracle` points to the existing packet49
oracle; no output, source or binary is copied or changed there.

The inherited 32K reserve did not fit beside the new build and K2 peak.
This packet instead budgets its exact eleven-window 4K chain:

| Item | Bytes |
| --- | ---: |
| Root free-space floor | 8,000,000,000 |
| Packet49 pending KD/W2m/WS/WSs/WS128x/WS128 | 5,818,804,480 |
| Additional oracle-growth allowance | 500,000,000 |
| Packet49b build budget | 2,500,000,000 |
| Packet49b retained early evidence limit | 128,000,000 |
| Packet49b model chain, no compression credit | 5,818,804,480 |
| Total initial requirement | 22,765,608,960 |

Without early fixture retention the complete chain projects 10,582,804,480
bytes. K2's 2.5 GB scratch peak is smaller than the model-phase envelope.
The inherited retention implementation verifies oversized generated fixture
hashes, records binary/argv/dispatch restoration bindings and retains logs
before discarding those fixture bytes. The queue enforces the early 128 MB
cap on the five early window directories plus root logs/metadata. This is a
bounded single chain, not permission for unlimited retries or concurrent chains.

`storage_precheck.py` reports current free space and the remaining full
budget. `storage.py` also checks the floor, protected allowance and finite
packet build/output cap before every write stage. A failed check stops before
new work. No existing files were deleted to obtain this fit. Packet49's own
larger sealed admission policy is unchanged; it may still refuse a later
window and must be handled separately.

Keep source, gate/build/seal receipts, compact evidence, review and runbook in
Git. Binaries, objects and complete fixture outputs stay in the external
result tree, bound by receipts. The p45 metadata, fixture inputs and 4 MiB
RoPE table are read-only inherited links. Restore them from retained p45
artifacts; do not regenerate them with different arithmetic. Never invoke
copied historical cleanup/reseal helpers against protected predecessor trees.
