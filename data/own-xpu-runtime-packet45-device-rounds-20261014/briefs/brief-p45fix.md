You are working in /home/steve/llm-optimizations (Git main only; never create branches; stage explicit paths only and commit with an explicit pathspec (`git commit -m ... -- <paths>`); never `git stash`; if the remote moved, `git fetch` and `git merge --no-edit origin/main` (no rebase of a dirty tree), then push). HOST RULES (no sandbox, binding): CPU only: never run a device binary, never open /dev/dri, never call Level Zero or SYCL device discovery, no sudo, no power/memory/swap/page-cache settings. GPU windows run on this host under the coordinator; do not launch any. Nice/ionice: every command `nice -n 19 ionice -c 3`, at most 2 compile jobs and at most 4 CPU-bound processes at any time, OMP_NUM_THREADS<=4, `python3 -B` only. DISK: check `df -B1 /` before every large write, stop with a clear message below 8 GB free. STATE. Packet 44 (stage2/packet44-context) is sealed; packet 45 = your own previous merge (stage2/packet45-merged3, commit 7b0ec5bb5 "Seal packet45 merged runtime on CPU").

# TASK: packet 45 fix — K1a adapter fixture case 54 fails on the real device

The coordinator ran packet 45's first device chain tonight (both card pairs, contexts 4096, draft ranks 0 and 1, fresh boots, sealed binaries). K0 passed on both pairs (device_executed, boot 13858eef). K1a then failed IDENTICALLY on both pairs:

```
actual adapter core mismatch case=54 version=0 buffer=5
```

Evidence (read it, do not rerun):
- experiments/own-xpu-runtime/stage2/packet45-merged3/build/c4096-dr0/K1a/{fixture0.log.gz,failure-before-teardown.json,kernel-window.txt,retention.json}
- experiments/own-xpu-runtime/stage2/packet45-merged3/build/c4096-dr1/K1a/ (same set)
- experiments/own-xpu-runtime/stage2/packet45-merged3/build/FAULT.json (boot fault latch; DO NOT delete or modify — the coordinator clears it during recovery after your fix)

Case decoding (verified against adapter_fixture.cpp lines 100-134): cases are counted 0-based in build order; case 54 is the third `make_hc_activation()` scenario (`scenario==2`, the one that pre-seeds the error buffer before the run), tested at implementation version 0, output buffer id 5. Packet 44's K1a passed this exact fixture on these same cards under this same boot, so this is a regression introduced by the packet 45 merge (kernel integrations: route production on rank32, gate/up packed, tiny-kernel reshapes, epilogue fusions; plus draft-on-rank-0 and the 22/26 rebalance).

Work:
1. Reproduce on CPU: the adapter fixture has a host/validation mode (fixture_validation::only) or an equivalent CPU gate you sealed with — find why case 54 scenario 2 version 0 was not caught by the CPU gates you ran (79 mini cases, 6 real-model cases, etc.). The pre-seeded error buffer propagation through the merged HC/adapter path is the prime suspect: check which packet-45 change touches that path (error-buffer handling, epilogue fusion, or the reshaped tiny kernels writing buffer id 5 for that case).
2. Fix the root cause in packet45-merged3 (not a fixture special-case; the fixture encodes runtime ABI truth).
3. Extend the CPU gates so this exact scenario (hc_activation with pre-seeded error buffer, version 0) is covered and fails before the fix / passes after. Show that evidence.
4. Re-run the full packet45 CPU gate suite you ran before (memory plan, seal binding, wrapper merge tests, context window gates) and re-seal. Keep WINDOW.md/coordinator_windows.sh commands unchanged unless the fix changes an ABI or identity input; if identity inputs change, say so explicitly in your final message so the coordinator discards partial chains.
5. Commit with explicit paths and push. Co-Authored-By: Codex <noreply@openai.com>.

Finish with: the root cause in three lines, why CPU gates missed it, the fix diff summary, the new gate and its before/after evidence, gate counts and runtime hashes after reseal, and whether the device binary identity (sealed hashes in window.py/build receipts) changed.
