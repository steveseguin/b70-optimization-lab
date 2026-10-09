# Flash-Next probe and host-pointer fix preparation — 2026-10-09
Prepared on CPU only; implementation commit: `392ddc22f`.
Built the indirect slab probe and the direct-host-pointer flag/wrapper using shared code.
The slab uses the overlay’s exact-size Torch pinned allocation path and all three allocator aliases.
The 3 MiB slab holds a [4,4096] interior view at byte 4096 filled with arange modulo 251.
One native UVA view feeds the production signed-offset table and CPU address reconstruction.
Each admitted run has one gather launch, one explicit sync, and exact rows [3,0,2,1].
Receipts retain pointer spans, layout, table values, hashes, IR paths and exact errors or signals.
Execution requires FLASHNEXT_PROBE_ADMIT=1 and the lane’s complete same-boot health receipt younger than six hours.
A CPU guardian retains crash evidence; the sole device worker has a hard 120-second OS alarm and no retry.
A bounded journal watcher must read a clean journal after worker exit before the receipt can pass.
The print-only Docker command pins the lane image, exposes one by-path render node, and disables network access.
The separate overlay-fix-hostptr patch and module copies pass and use host/resident bases, local rows and selectors.
The candidate retains K/N addressing and FP8 arithmetic; the active overlay and all 47 manifest hashes are unchanged.
CPU validation passed 237 tests: 213 existing lane, 15 probe, and 9 addressing; zero failures or skips.
Independent subagent review checked addressing, pointer use and the final journal handshake; no CPU-scope blocker remains.
Native USM-query availability, residency, JIT/codegen, GPU byte equality, full-model output and fresh-runtime repeats remain unverified.
No GPU, container, server, host-setting, LTX, /mnt/fast-ai or saved runs were changed; no credentials were accessed.
Coordinator preview: `bash experiments/qwen38-flash-next-fp8-b70/reopen-20261008/probe/run-probe-in-container.sh --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json --receipt-dir /PATH/TO/NEW-PROBE-RECEIPTS`.
Follow the [exact watcher/execution sequence and stop rule](../reopen-20261008/probe/README.md); any failure stops new submissions, with no chained direct probe or full load.
