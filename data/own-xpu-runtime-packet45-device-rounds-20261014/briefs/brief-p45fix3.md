You are working in /home/steve/llm-optimizations (Git main only; never create branches; stage explicit paths only and commit with an explicit pathspec; never `git stash`; if the remote moved, `git fetch` and `git merge --no-edit origin/main`, then push). HOST RULES (binding): CPU only — never run a device binary, never open /dev/dri, no Level Zero/SYCL device discovery, no sudo. `nice -n 19 ionice -c 3`, ≤2 compile jobs, ≤4 CPU-bound processes, OMP_NUM_THREADS<=4, `python3 -B`. DISK: `df -B1 /`, stop below 8 GB free. STATE: your owner-set fix (fd650dd1c) WORKED on device — K0 and K1a (218 + 216 checks) passed both card pairs tonight under boot 13858eef. The chains then died at K1b admission — BEFORE any device contact — on storage budget:

```
RuntimeError: Packet38 storage admission refused: free=31558537216, build=1552906002, reserve write=2500000000; require 8 GB free and build below 3 GB
(window.py:440 admit_output → storage.py:32 admit)
```

# TASK: packet 45 follow-up 2 — K1b's 2.5 GB retention reserve exceeds the 3 GB build-dir budget

Facts on the ground:
- packet45-merged3/build is 1,486 MB with every artifact seal-bound (asan 975 MB, fusion-fixtures 202 MB, device 96 MB, icpx-host 88 MB, gnu-host 62 MB, plus small test trees). Coordinator cannot delete any of it without breaking artifacts_sha256.
- K1b (and possibly later retained windows — check KD, W2m, WS, WSs, WS128x) projects a 2.5 GB reserve write into that same build tree; 1.49 + 2.5 > 3 GB → admission refuses. Packet 44 fit under the cap; the merged packet's retention plan does not.
- Root rehearsal gap (the third one found on device): window.py:440 substitutes a fake 64,000,000-byte projection under cpu_rehearsal, so your 9/9 rehearsal chains could never fail storage admission. The reserve write, projected_write_bytes() and the 3 GB cap were never exercised together.

Work:
1. Decide the correct design and implement it: either (a) make the merged retention plan fit the budget (smaller retained set for K1b/later windows, retention stored outside the capped build tree but still under the packet, or per-window budget accounting), or (b) amend the admission cap for the merged packet with an explicit written justification (disk headroom is 31.5 GB; the cap is packet38-era) — but treat the cap as a real safety invariant, not friction: if you raise it, bound it by something structural (e.g. df-derived headroom minus a reserve for the remaining windows), keep the 8 GB free-floor, and document the new arithmetic in CAPACITY.md/README. Do not weaken the free-space floor.
2. Close the rehearsal gap for real this time: cpu_rehearsal must use the TRUE projected_write_bytes() values (the fake 64 MB may stay only for the df-free check, with the real projection still validated against the cap). Then re-run the full 9-window CPU rehearsal chains (4096 dr0/dr1, 32768 dr0) and show each window's projected bytes vs budget as a table in your evidence.
3. AUDIT THE WHOLE ADMISSION PATH for the same class: admit_output consumers, projected_write_bytes per window vs actual measured writes from packet 44's sealed receipts (its window.json files record real write volumes — compare), memory_admission required_MemAvailable vs the merged plan, and any other budget constant that packet 44 happened to fit but the merge may not. List every constant checked with its verdict. This is the third stale constant found on device (fixtures count, owner count, storage cap); there must not be a fourth.
4. Re-run the complete CPU gate suite and reseal. State whether device binary identity changes (it should not — this is host-side), and whether artifacts_sha256 / window identity changes (it will — the coordinator will discard partial chains).
5. Commit with explicit paths, push, Co-Authored-By: Codex <noreply@openai.com>. Do not touch build/incident-20261013-k1a-case54/ or any device-produced window dirs.

Finish with: chosen design and why, the admission-path audit table, rehearsal proof with per-window projected-vs-budget numbers, gate counts, new seal hashes, and device-identity verdict.
