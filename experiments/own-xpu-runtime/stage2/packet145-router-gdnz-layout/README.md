# Packet145: router and GDN z load-time order

Vendored from packet142c, frozen at the commit and hashes in `lineage-inputs/vendor-origin.json`.
Only this new tree is edited. Immutable linked objects remain hash-bound; oracle
access is through `oracle-binding.json` and `shared_oracle.py`.

`router-order600` copies each complete fused router/shared tuple in kernel order:
router, shared expert gate, shared expert up, shared router. `gdnz-order600`
copies only GDN z projections in layer order. Rows stay contiguous and every
row byte is unchanged. Separate device allocations do not guarantee physical
adjacency. The 600 MiB per-rank bank is created once with bounded 32 MiB copies.
No weights are written or allocated at view boundaries. Six rollback bank-pair
captures are rebuilt and all mutable request state is reset.

Arithmetic is `iq3-p49-split32-v1`, including unchanged FP32 chains and reduction
order, BF16 KV, target weights and speculative verifier. GNU/Intel CPU proofs
use synthetic finite bytes at real matrix shapes. They are not device quality.

Only `v5/bracket_job.py` is a device entry. Both lanes are supported: A cards
0+1; B cards 2+3. Each variant/lane has its own 12×64 smoke and one-load five-view
12×128 production/candidate/production/candidate/production bracket. The bracket
requires that same variant's same-lane smoke. Lanequeue names are `screen-<job>`.
The closed environment is vendored from `ops/launch_env.py`; native pre-exec
getrlimit checks refuse inherited CPU address caps. CPU caps apply only in CPU
CLI processes. No automatic retry or queue write is performed.

`READY-FOR-DEVICE-router-A.json` authorizes only the router smoke on A after its
CPU gates. `READY-FOR-DEVICE.json` is the final all-proposal handoff. Both are
written last for their milestones. Actual device exactness and speed remain
pending; the 58.798 record is unchanged. Proposals are never enqueued here.

See [work note](../../../../notes/2026-10-18-own-runtime-packet145.md),
[boundaries](DO-NOT-REPEAT.md), [registration](preregistration.json), and
[CPU evidence](v5/evidence/). Historical copied receipts are provenance, not
packet145 passes. Only the current v5 composition seal defines readiness.
