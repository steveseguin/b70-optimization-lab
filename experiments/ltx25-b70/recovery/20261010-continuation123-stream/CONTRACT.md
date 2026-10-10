# Continuation packet 123

CPU-prepared successor of sealed packet 122, manifest
`8b576c863ec5896fe356e5a264728ddafe368ef2fe90608c9b5bc164687cb7fa`.
This packet is not GPU-qualified. No launch or live preflight was performed.

`LTX_AUX_RESIDENCY=legacy|xpu2` defaults to `legacy` (121/122 residency).
The opt-in mode constructs the audio VAE/vocoder on xpu: 2 and changes only the
unloaded BF 16 upsampler patcher's load target to xpu: 2. It retains sampler
blocks 0–19 on xpu: 0, 20–47 on xpu: 1; text 24/24 on xpu: 2/3; video VAE on 3.
It changes no numerical operator, precision, seed, schedule or output geometry.
The native ownership and full-residency checks follow the selected role map.
The upsampler's CPU inventory must be exactly 995, 735, 808 bytes before retargeting.

Auxiliary mode admits only 145/169 frames, two-way 20-28, frame anchor, dg 0,
cone and display xpu: 3.169 requires auxiliary mode. Auxiliary plus display
replica is refused: its combined workspace estimate lacks margin.145 dg 1 with
display replica is also refused. Other 122 options retain their grammar.
The 8/8/2/9 GiB floors remain. New auxiliary operations additionally require
4.75 GiB free on 2 before work (floor 2 + workspace 2 + screening .75) and 2.75 GiB
on completion. These are boundary observations, not isolated peak claims.

The numerical qualification IDs of all 176 parent variants are preserved;
44 derived 169 variants add geometry identities. Runtime admission is narrower
than the enumerated graph grammar. A separate `residency_qualification_id`
binds the numerical ID, selected mode and both component devices. Status,
every receipt and the frozen verdict bind that identity. All three chains,
measured geometry, unchanged target bytes, per-chunk cone/display byte checks,
no-eviction and fault/latch gates remain.145 uses all seven recorded output
hashes from packet 121's eager qualification; its verdict and six receipts are
embedded and hash-bound in `reference-frame-145-provenance.json`.169 has no
memory-admissible legacy run and therefore no measured 169 cross-placement oracle.

Preview MP 4 and preview JSON now use exclusive same-directory temporary files,
fsync, atomic `renameat2(RENAME_NOREPLACE)` and directory fsync. A final name is
never overwritten. The strict single-link, inode/size/mtime/ctime reader remains.
Only an uncommitted preview receipt's identity race may retry once after 50 ms;
completed evidence violations fail immediately. Linux exclusive-rename support
is required; a failure closes the writer without unsafe fallback.
The client records one bounded status snapshot on exit 7, preserving the original
failure and exit code. It retries neither the failed request nor the server.

See [design](../../notes/2026-10-10-continuation123-stream-design.md),
[residency census](../../notes/2026-10-10-continuation123-residency-analysis.md)
and [launch reference](LAUNCH.md). Predictions are not measurements. Native
memory savings, cross-device exactness and 169 display timing remain open.
