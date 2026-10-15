You are working in /home/steve/llm-optimizations (Git main only; never create branches; stage explicit paths only and commit with an explicit pathspec; never `git stash`; if the remote moved, `git fetch` and `git merge --no-edit origin/main`, then push). HOST RULES (binding): CPU only — never run a device binary, never open /dev/dri, no Level Zero/SYCL device discovery, no sudo. `nice -n 19 ionice -c 3`, ≤2 compile jobs, ≤4 CPU-bound processes, OMP_NUM_THREADS<=4, `python3 -B`. DISK: check `df -B1 /`, stop below 8 GB free. STATE: your NaN fix (9b5a4ec70) WORKED on device — K1a ran all 218 fixture checks PASS and 216 p33-linked checks PASS on both card pairs. One gate remains stale.

# TASK: packet 45 follow-up — K1a sequential-owner teardown gate rejects the merged fixture set

Tonight's device run (fresh chains, fixed binary, boot 13858eef): K0 passed, then K1a was rejected by the window gate with:

```
K1 unsafe/missing sequential-owner teardown   (fixture_support.py:252, sequential_teardown(row,4))
```

The receipt at experiments/own-xpu-runtime/stage2/packet45-merged3/build/c4096-dr0-gpu/K1a/run0/receipt.json (and the dr1 twin) is healthy: passed=True, owner_cards=1, device_executed=True, fixtures=218, odd_lengths=20, ties=1, nan_routes=1, max_submission_ns=39351979 — and FIVE teardown rows, all status=complete, safe_to_exit=True, live_bytes=0, in_flight=0. The fifth owner is `p39-fixture-*` (2,673 frees) — packet 39's gate/up fixtures, which the packet 45 merge added to K1a's sequential owners. Packet 44's K1a had four owners (fixtures, actual-adapter, small-gemv, gemv-k2); the gate constant 4 is stale relative to the merged runtime.

Work:
1. Fix the gate in fixture_support.py so it validates the merged owner set instead of a hard-coded 4 — e.g. derive the expected owner sequence from the fixture list the window actually launches (nongemv, actual-adapter, small-gemv, gemv-k2, p39), keeping every safety invariant (owner_cards==1, exact owner-set match, all safe_to_exit, zero live bytes, zero in flight). Do not weaken it to `>=` or a bare count bump without the owner-set check.
2. AUDIT FOR SIBLINGS — this is the second stale-from-packet44 constant found on device; the next one costs another multi-hour chain cycle. Sweep fixture_support.py, window.py and any gate module for hard-coded counts, owner lists, binary names, fixture totals, or packet-44-era structure assumptions (e.g. fixtures=170-era expectations, children counts, per-window binary sets for K1b/K2/KD/W windows), and check each against the merged runtime's actual structure. Fix every one that is stale, with the same rigor.
3. Prove it on CPU before sealing: run the full coordinator_windows.sh chain (all nine windows) in cpu_rehearsal mode for BOTH draft ranks at 4096 and one rank at 32768, through the exact coordinator entry — every window gate must pass end to end. Your earlier wrapper-merge-tests did not catch this, so state precisely why (which rehearsal gap) and close that gap permanently in the test suite.
4. fixture_support.py is seal-hashed: re-run the complete CPU gate suite and reseal (24 gate receipts, 41 build artifacts). State the new runtime hashes and confirm whether device artifact hashes change again (they may not — this is host-side, but say it explicitly).
5. Commit with explicit paths, push, Co-Authored-By: Codex <noreply@openai.com>.

Do NOT touch build/FAULT.json history or build/incident-20261013-k1a-case54/ (preserved coordinator evidence). Do NOT rerun anything on a device.

Finish with: the gate fix diff summary, the sibling-audit findings (each constant checked and its verdict), the rehearsal-chain proof (windows passed per draft rank/context), new seal hashes, and whether device binary identity changed.
