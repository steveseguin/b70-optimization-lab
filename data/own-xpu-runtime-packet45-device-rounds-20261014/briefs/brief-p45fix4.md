You are working in /home/steve/llm-optimizations (Git main only; never create branches; stage explicit paths only and commit with an explicit pathspec; never `git stash`; if the remote moved, `git fetch` and `git merge --no-edit origin/main`, then push). HOST RULES (binding): CPU only — never run a device binary, never open /dev/dri, no Level Zero/SYCL device discovery, no sudo. `nice -n 19 ionice -c 3`, ≤2 compile jobs, ≤4 CPU-bound processes, OMP_NUM_THREADS<=4, `python3 -B`. DISK: `df -B1 /`, stop below 8 GB free. STATE: packet 45 device chain progress tonight (boot 13858eef, both card pairs): K0 ✓, K1a ✓ (218+216 checks), K1b ✓, then K2 fixture failed on device, identically on both pairs:

```
K2 actual adapter mismatch: route+gather     (6 occurrences = 3 versions x 2 ranks)
```

Evidence preserved (read, do not rerun): experiments/own-xpu-runtime/stage2/packet45-merged3/build/incident-20261014-k2-routegather/{FAULT.json,c4096-dr0-gpu/K2,c4096-dr1-gpu/K2}/ — fixture0.log.gz, failure-before-teardown.json, kernel-window.txt, retention.json.

# TASK: packet 45 fix 3 — route+gather fused dispatch mismatches on device

What is known:
- The failing fixture is adapter_fixture.cpp:152 (`make_case(3)`, fold_pair, "route+gather"), which drives the fused route+gather path through dispatch_registry.hpp:81 — implementation `p42.route.production_rank32` (the packet-42 kernel your merge integrated) against the packet18 reference. All three versions mismatch, both ranks, both card pairs: deterministic host/device divergence in the merged route+gather path.
- Same signature as the K1a case-54 failure you already fixed (HC NaN payload): same-build host agreement hid it from CPU gates. Your six-compiler gate caught the HC case; it did not catch this one — find out why (is the route+gather fixture case in the CPU gate's case list at all? adapter_cases() now shares construction — verify case 152's route+gather is exercised under the compiler matrix, with the same buffer fill, fold_pair and versions as the device fixture).
- Suspects: the rank32 route kernel itself (tail handling, work-group partitioning, or NaN/special-value propagation in route scores — the fixture case make_case(3) with fold_pair exercises specific edge values), or the fusion glue (gather reading route outputs in fused form vs reference layout — the registry's fusion/class consistency rules at dispatch_registry.hpp:95-97).

Work:
1. Root cause on CPU: reproduce the divergence via the shared adapter_cases() route+gather case under your compiler matrix (or explain precisely why CPU cannot diverge and identify the device-only semantic — e.g. fp contraction, subnormal handling, atomic order — then encode that semantic as a CPU-checkable invariant). Name the exact kernel/expression at fault.
2. Fix the root cause in the merged kernel or fusion glue — not the fixture, not a special case. Keep the packet18 reference path bit-identical.
3. Extend CPU gates so this case fails pre-fix and passes post-fix under the matrix; show both.
4. Re-audit the remaining fused entries in dispatch_registry.hpp (the other packet42/p39/p28 integrations) for the same divergence class — for each fused entry, state whether its adapter-fixture case actually exercises the fused path on CPU under the matrix, and add coverage where missing. The device chain costs hours per round-trip; this audit is the cheap gate.
5. Full CPU suite + 9/9 rehearsal chains (4096 dr0/dr1, 32768 dr0) + reseal. State explicitly whether device binary hashes change (a kernel fix will change them — say so, and confirm ABI unchanged or changed).
6. Commit with explicit paths, push, Co-Authored-By: Codex <noreply@openai.com>. Do not touch build/incident-*/ or any device-produced dirs.

Finish with: root cause in three lines, why the compiler matrix missed it, fix summary, new gate evidence (before/after), fusion audit table, gate counts, seal hashes, device-identity verdict.
