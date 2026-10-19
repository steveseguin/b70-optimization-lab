# Packet151d preparation refusal closeout

Question: why did the sibling smoke fail before its first timing row?
Identity: bundle8, `iq3-p49-split32-v1`, saved lane-B rank0 argv and selection
from `v5/evidence/device-sibling-smoke-B/`; no new GPU run.

The first paired operation was `blk.0.gdn.qkv`,
`ProductionDense<Q6_K,2560,1,false>`. Direct `q.submit` bypassed the native
preparation capture, and sibling selection was incorrectly active in prefill.
All five new submission sites now use `prepared_submit` with value captures;
prefill keeps the ordinary path.

[CPU regression](v5/evidence/preparation.json): old code fails at that exact
site. Fixed code traverses load, preparation, prefill positions 0/1 and decode
positions 2/31/32/33, both bank parities and context extents 32/64: 552 paired
native captures, 114 paired sites per decode schedule. Device compiler flags
and real rank arguments are used. Weight payload and inherited M=1 execution
are mocked; no GPU queue is constructed or submitted. Synthetic event timings
are transport fixtures, never measurements.

[Arithmetic](v5/evidence/pair-cpu.json): four runs, 1,478 byte checks each,
identical to the original reference hash. [State](v5/evidence/sibling-state.json):
two equal kept-state hashes, including rollback/reset and prefill exclusion.
The fixes change command preparation and selection, not model arithmetic.

The failed device smoke, old headers/rank source under
`lineage-inputs/p151d-before/`, CPU regression and build commands are retained.
Device quality and sibling cost remain unmeasured for this revision. Revisit
if a new paired operation bypasses capture, a shape-specific path is added,
or a device parity test fails. Packet132's cost decision remains pending.
