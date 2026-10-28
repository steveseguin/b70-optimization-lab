Dedicated-provider first parity gate (2026-10-28)

CPU/offline helper only. No device, service or archive extraction actions.
Existing strict target/draft comparator sources and original manifests unchanged.
Reference: /dev/shm/pp4-overlap-gate-20261028/output/request-00-serial
Prompt1677, output32, target position1708, canonical provider pairs1707.
Canonical inventory: target2065 across48 layers; draft73 including scratch/pinned.

After candidate exits, coordinator may extract ONLY serial5 reference bundles
if RAM admission permits. Never extract while four candidate owners are loaded.

python3 prepare.py --plan /dev/shm/sc117-dedicated-3plus1-20261028-r1/plan-final.json --reference-request /dev/shm/pp4-overlap-gate-20261028/output/request-00-serial --out /dev/shm/dedicated-comparison-r1
python3 compare.py /dev/shm/dedicated-comparison-r1/inputs.json --out /dev/shm/dedicated-comparison-r1/proof.json

prepare.py requires all native owners to report passed FINISH before writing fresh
comparison manifests. It derives pair identity from actual command/proposal/reply
records; never invents matching identity from token-only traces. compare.py binds
raw native proposal hidden hashes to supplied pair traces, verifies ordered pair
parity, actual prompt/output token hashes, sealed target bytes/layouts/native
quiescence/bank identity, strict full draft allocation parity and idle teardown.
Request hashes/epochs stay actual: baseline epoch1; dedicated candidate epoch0.
Cross-partition equality compares semantic canonical names, not physical slots.

Scope: parity with prior baseline, not independent mathematical model correctness,
not throughput evidence. GPU candidate and full dump path have not been validated
by these CPU tests. Failed comparison must retain mismatch details and raw dumps.
CPU: python3 test_compare.py (19 tests: real-format pair success, hidden/serial/reply
mutation, raw fixture ordinals2/17/32 and bool-normalization refusal, missing/duplicate commands, actual DUMP path/manifests/fresh output; schema-specific large driver result and owner exit failure).

Actual r3 comparison PASSED; r3-comparison-receipt.json binds full proof and source hashes.

Optional dedicated_capture_ready plans require a single actual parent-captured command event before every provider completion; raw ACK128/Reply64 and real source FinalRecord identity are verified. Default plans forbid capture events. Existing r3 proof retains its original helper hash.
