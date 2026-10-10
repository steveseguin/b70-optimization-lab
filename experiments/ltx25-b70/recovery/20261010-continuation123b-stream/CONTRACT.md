# Continuation packet 123b

CPU-prepared successor of sealed packet 123, manifest
`db5ea277d381c8a77c1bae94cc4e25b1e22035a084a7e3a33b7d10e5d68b340d`.
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

The numerical qualification IDs of all 220 parent variants are preserved,
including the 44 derived 169-frame variants. Runtime admission is narrower
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

See [design](../../notes/2026-10-10-continuation123b-storage.md),
[residency census](../../notes/2026-10-10-continuation123-residency-analysis.md)
and [launch reference](LAUNCH.md). Predictions are not measurements. Native
memory savings, cross-device exactness and 169 display timing remain open.

## Packet 123b storage contract

Parent: sealed 123, manifest
`db5ea277d381c8a77c1bae94cc4e25b1e22035a084a7e3a33b7d10e5d68b340d`.
Packet id is the string `"123b"`; names use `stream123b-`; numerical contracts,
auxiliary residency, atomic preview publication and exit-7 status remain 123's.

`LTX_RUN_WRITE_ALLOWANCE_GIB` accepts a canonical decimal integer from 1 to 64,
default 3. Empty, signed, fractional, padded and out-of-range values refuse.
The launch captures `run_write_allowance_bytes` in server options, status,
qualification verdict, chunk receipt, decode receipt and preview receipt. The
client defaults to expecting 3 GiB; `--expect-run-write-allowance-gib N` must
match a changed launch. Options cannot be changed by requests or later env edits.

Count `st_blocks * 512` under the run directory, all `output/stream123b-*`
entries, `output/validation/stream123b-*` entries and `requests/stream123b-*`
entries, including hidden temporary files inside those directories. Startup's
exclusive namespace collision check makes these paths belong to this run.
No baseline subtraction: qualification captures, anchors, logs and receipts all
count. Deleting consumed previews releases their retained allocated bytes.
Sparse holes do not count. The shared parent directories and other writers do
not count. The independent global free-space floor stays exactly 50 GiB.

A locked metadata walk caches directory membership by inode/mtime/ctime and
updates the total from per-path block deltas on each check around a chunk.
It re-stats cached files so in-place growth cannot evade the guard. It reads no
file payloads. Work and cache size are bounded at 200,000 visited entries and
32 nested levels; exceeding a bound refuses, as do symlinks, hard links, special
files or a different filesystem. Cost still grows with retained file count;
this is not an O(1) filesystem quota. In-flight writes become visible at the
next check; the check is not a transaction or a preallocation guarantee.

The HTTP 409 storage refusal and client exit 15 remain unchanged. Preview read
failures retain exit 7 and the single bounded status observation. Raw capture
count and payload limits are unchanged; this option never authorizes raw
stream captures. No GPU qualification or launch was performed.
