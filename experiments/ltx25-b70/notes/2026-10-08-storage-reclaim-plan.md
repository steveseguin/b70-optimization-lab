# Storage reclaim plan for the LTX results root (2026-10-08)

This is a read-only audit and a proposal for the owner. **Nothing was deleted, moved, renamed,
hashed in bulk or mounted.** No GPU, server or Git commit was involved. The only file written is
this note. Snapshot taken 13:00–13:35 UTC on 2026-10-08, while the coordinator was still working on
this root: the 113 stream stopped at 13:21:57 UTC (`data/resume-20261008/stream113-stop.json`),
its run01 output moved into `output/archive-stream113-run01/` at about 13:28 UTC, and a new 113
server (`continuation113c-storage-admission.json`) started writing at about 13:30 UTC. **Any
plan or apply step below has to re-scan the root first. These figures are for planning only.**

Root filesystem (`/dev/nvme0n1p2`, which `/home`, `/mnt/fast-ai` and `/tmp` all share):
57,627,459,584 bytes free (53.67 GiB). That is **3.67 GiB above the 50 GiB lab reserve**. A vLLM
XPU image pull needs about 20+ GiB above the reserve, and a build needs more.

## Headline

| Tier | What | Files | GiB reclaimable | Decision needed |
|---|---|---:|---:|---|
| A | Stream-01 preview MP4s (stopped run) | 5,309 | 0.23 | yes, but low risk |
| A (optional) | Stream-01 request histories, after a tar.zst archive | 11,094 dirs | ~0.45 net | yes |
| A | Already-receipted byte-identical duplicates | 0 | 0.00 | none: all 1,680 receipted paths are already gone |
| B | Old timed/endurance-arm tensor captures from packets ≤ 98 that duplicate a keeper | 5,053 | **89.31** | yes |
| B+ (optional) | Proof/warm-up captures from packets ≤ 98 | 485 | 6.92 | owner call |
| Q | `quarantine/` rejected model copies and partial downloads | 4 | **77.94** | owner call |
| C | Build outputs in clean, pre-September `/home/steve/src` worktrees (none are archived yet) | 96 trees | up to 9.44 | owner call; archive first |

**The brief's premise needs one correction.** Preview MP4s are *not* the bulk of `output/`. All
non-validation `output/` entries together take 1.03 GiB. The 135 GiB is in
`output/validation/*/tensors.safetensors`: F32 oracle captures of 17–20 MiB each for 256×256 runs,
and 70–136 MiB for 640×384 runs. Stream previews give back well under 1 GiB. The real levers are
Tier B (duplicate captures, already covered by the lane's established retirement practice) and
the 78 GiB quarantine.

## 1. Size map

`du -B1` (allocated bytes). Results root `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/`
is 228.14 GiB in total, across 713 top-level entries:

| Top-level | Entries | GiB |
|---|---:|---:|
| `output/` | 1 | 136.02 |
| ↳ `output/validation/` | 20,625 dirs | 134.99 |
| ↳ everything else in `output/` (previews, archives) | 14,087 | 1.03 |
| `quarantine/` | 4 files | 77.94 |
| `prepared-*` (sealed packets) | 127 | 7.79 |
| `encoder-server-*` (server run dirs, incl. `.failed-*` and `.run01-*`) | 298 | 4.74 |
| `requests/` | 22,418 dirs | 1.06 |
| other dirs (unlaunched packets, screens, boot-health, repair blocks) | 78 | 0.58 |
| `*.log`, `*.json` | 207 | 0.003 |

Family key: the trailing numeric/run suffix is stripped (`-NN`, `-rNN`, `-sNNNNNNNN`, `-cNNNNNN`),
so `f97-twowayw2b2p1dxpu2r2-timed-17` becomes `f97-twowayw2b2p1dxpu2r2-timed`. In the validation
table, per-fixture single captures are also folded together (`…-native-p1-<fixture>`).

### `output/` excluding `validation/` (1.03 GiB, 634 families)

| Family | Entries | GiB |
|---|---:|---:|
| `archive-stream112-run01` | 1 | 0.337 |
| `s97-twowayw2b2p1dxpu2-stream01` | 5309 | 0.234 |
| `f97-twowayw2b2p1dxpu2r2-timed` | 595 | 0.027 |
| `f97-twowayw2b4p1dxpu2r2-timed` | 589 | 0.027 |
| `f96-shard4aw3b2p1r3-timed` | 593 | 0.027 |
| `f97-twowayw2b1p1dxpu2r2-timed` | 346 | 0.015 |
| `baseline` | 3 | 0.009 |
| `f92p` | 158 | 0.007 |
| `f100b-twoway2028w2b1p1dxpu2s256x256-timed` | 118 | 0.007 |
| `f99b-twowayw2b1p1dxpu2s256x256-timed` | 118 | 0.007 |
| `resolution-full-20261007-timed` | 42 | 0.006 |
| `f77-endure` | 118 | 0.005 |
| *622 other families* | 6097 | 0.308 |

`archive-stream112-run01/` (0.34 GiB) holds 112's nine qualification captures plus 61 previews.
`archive-stream113-run01/` appeared during the audit. Both are protected.

### `requests/` (1.06 GiB, 1,298 families)

| Family | Entries | GiB |
|---|---:|---:|
| `s97-twowayw2b2p1dxpu2-stream01` | 11094 | 0.466 |
| `f96-shard4aw3b2p1r3-timed` | 600 | 0.025 |
| `f97-twowayw2b2p1dxpu2r2-timed` | 600 | 0.025 |
| `f97-twowayw2b4p1dxpu2r2-timed` | 600 | 0.025 |
| `f97-twowayw2b1p1dxpu2r2-timed` | 600 | 0.021 |
| `f96-shard4aw3b2p1r2-timed` | 600 | 0.014 |
| `resolution-full-20261007-timed` | 44 | 0.009 |
| `f100b-twoway2028w2b1p1dxpu2s256x256-timed` | 120 | 0.007 |
| `f92p` | 160 | 0.007 |
| `f99b-twowayw2b1p1dxpu2s256x256-timed` | 120 | 0.006 |
| `f91b-rep` | 120 | 0.005 |
| `f91c-rep` | 120 | 0.005 |
| *1286 other families* | 7640 | 0.309 |

The old packet request histories are each under 0.03 GiB. They are the per-request run record
(`identity/prompt/submission/history/result.json`), and the lane's receipts treat them as
evidence. Retiring them is not worth it, except possibly the stopped stream-01 set.

### `output/validation/` (134.99 GiB, 896 families)

The duplicate screen is metadata only. Each capture's `summary.json` records a SHA-256, shape and
dtype for each of its four tensors (`images`, `video_latent`, `audio_latent`, `waveform`). Two
captures with the same four-tensor key are screened as duplicates. A whole-file hash is still
required before any removal (see Tier B). Totals: 75.80 GiB match a **protected keeper's** key,
54.11 GiB match another unprotected capture, only 0.06 GiB is unique, and 4.86 GiB is protected
itself (the references, the 116 keepers still named in the receipts, and the 111–113 captures).

| Family | Dirs | Captures | GiB | Class | Tier B files / GiB |
|---|---:|---:|---:|---|---:|
| `f96-shard4aw3b2p1r3-timed` | 600 | 600 | 11.12 | Tier B after verification | 587 / 10.93 |
| `f97-twowayw2b1p1dxpu2r2-timed` | 349 | 347 | 6.45 | Tier B after verification | 334 / 6.27 |
| `f92p` | 160 | 160 | 2.95 | Tier B after verification | 148 / 2.77 |
| `f77-endure` | 120 | 120 | 2.20 | Tier B after verification | 108 / 2.01 |
| `f90c-ctl-endure` | 120 | 120 | 2.20 | Tier B after verification | 108 / 2.01 |
| `f83e-endure` | 120 | 120 | 2.20 | Tier B after verification | 107 / 1.99 |
| `f84-endure` | 120 | 120 | 2.20 | Tier B after verification | 108 / 2.01 |
| `f90c-endure` | 120 | 120 | 2.20 | Tier B after verification | 108 / 2.01 |
| `f89-endure` | 120 | 120 | 2.20 | Tier B after verification | 107 / 1.99 |
| `f83f-endure` | 120 | 120 | 2.20 | Tier B after verification | 108 / 2.01 |
| `f96-twowayw2b1p1-timed` | 120 | 120 | 2.18 | Tier B after verification | 107 / 1.99 |
| `f95b-twowayw2-timed` | 120 | 120 | 2.18 | Tier B after verification | 107 / 1.99 |
| `f91b-rep` | 120 | 120 | 2.18 | Tier B after verification | 107 / 1.99 |
| `f95-twowayw2-timed` | 120 | 120 | 2.18 | Tier B after verification | 107 / 1.99 |
| `f91c-rep` | 120 | 120 | 2.18 | Tier B after verification | 107 / 1.99 |
| `f95-shard4aw2-timed` | 120 | 120 | 2.18 | Tier B after verification | 107 / 1.99 |
| `f93c-wlean` | 120 | 120 | 2.18 | Tier B after verification | 107 / 1.99 |
| `f96-twowayw1b2-timed` | 120 | 120 | 2.16 | Tier B after verification | 107 / 1.98 |
| `f95b-shard4aw3-timed` | 120 | 120 | 2.16 | Tier B after verification | 107 / 1.98 |
| `f95b-shard3cw3-timed` | 120 | 120 | 2.16 | Tier B after verification | 107 / 1.98 |
| `f96-shard4aw2b2p1-timed` | 120 | 120 | 2.13 | Tier B after verification | 107 / 1.94 |
| `f96-twowayw2b2p1-timed` | 120 | 120 | 2.13 | Tier B after verification | 107 / 1.94 |
| `f97-twowayw2b2p1dxpu2-timed` | 120 | 120 | 2.13 | Tier B after verification | 107 / 1.94 |
| `f97-twowayw3b2p1dxpu1xpu2-timed` | 120 | 120 | 2.09 | Tier B after verification | 107 / 1.90 |
| `f96-shard4aw3b2p1r4-timed` | 120 | 120 | 2.09 | Tier B after verification | 107 / 1.90 |
| `f96-twowayw1b4p1-timed` | 120 | 120 | 2.09 | Tier B after verification | 107 / 1.90 |
| `f96-shard4aw3b2p1-timed` | 120 | 120 | 2.09 | Tier B after verification | 107 / 1.90 |
| `f96-shard3cw3b2p1-timed` | 120 | 120 | 2.09 | Tier B after verification | 107 / 1.90 |
| `f97-twowayw3b2p1dxpu2-timed` | 120 | 120 | 2.09 | Tier B after verification | 107 / 1.90 |
| `f97-twowayw2b4p1dxpu1xpu2-timed` | 120 | 120 | 2.01 | Tier B after verification | 107 / 1.83 |
| `f97-twowayw2b4p1dxpu2-timed` | 120 | 120 | 2.01 | Tier B after verification | 107 / 1.83 |
| `f90-endure` | 118 | 118 | 1.74 | Tier B after verification | 92 / 1.55 |
| `f87-endure` | 84 | 84 | 1.52 | Tier B after verification | 72 / 1.34 |
| `f91c-ctl` | 80 | 80 | 1.45 | Tier B after verification | 68 / 1.26 |
| `f94f-s3c-timed` | 80 | 80 | 1.43 | Tier B after verification | 67 / 1.24 |
| `f94f-s4a-timed` | 80 | 80 | 1.43 | Tier B after verification | 67 / 1.24 |
| `resolution-duration110-20261007-candidate-check` | 14 | 14 | 1.36 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| `resolution-duration110-20261007-timed-fast` | 14 | 14 | 1.36 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| `resolution-duration110-20261007-native-p2-<fixture>` | 10 | 10 | 1.36 | needs-owner-call (second native pass; p1 is the keeper) | 0 / 0.00 |
| `resolution-duration110-20261007-native-p1-<fixture>` | 10 | 10 | 1.36 | protected (native keeper/anchor) | 0 / 0.00 |
| `resolution-client-reverse-20261007-native-p1-<fixture>` | 10 | 10 | 0.70 | protected (native keeper/anchor) | 0 / 0.00 |
| `resolution-client-20261007-timed` | 14 | 14 | 0.70 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| `resolution-full-20261007-timed` | 44 | 14 | 0.70 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| `resolution-full-20261007-candidate-check` | 14 | 14 | 0.70 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| `f92a-s05a` | 40 | 40 | 0.70 | Tier B after verification | 28 / 0.51 |
| `f92a` | 41 | 41 | 0.70 | Tier B after verification | 28 / 0.51 |
| `resolution-client-20261007-native-p1-<fixture>` | 10 | 10 | 0.70 | protected (native keeper/anchor) | 0 / 0.00 |
| `resolution-client-20261007-native-p2-<fixture>` | 10 | 10 | 0.69 | needs-owner-call (second native pass; p1 is the keeper) | 0 / 0.00 |
| `resolution-full-20261007-native-p1-<fixture>` | 10 | 10 | 0.69 | protected (native keeper/anchor) | 0 / 0.00 |
| `resolution-full-20261007-native-p2-<fixture>` | 10 | 10 | 0.69 | needs-owner-call (second native pass; p1 is the keeper) | 0 / 0.00 |
| `f93b-ctl` | 40 | 40 | 0.68 | Tier B after verification | 27 / 0.49 |
| `f93c-lean` | 40 | 40 | 0.68 | Tier B after verification | 27 / 0.49 |
| `f93b-lean` | 40 | 40 | 0.68 | Tier B after verification | 27 / 0.49 |
| `f93c-ctl` | 40 | 40 | 0.68 | Tier B after verification | 27 / 0.49 |
| `f94f-ctl-timed` | 40 | 40 | 0.68 | Tier B after verification | 27 / 0.49 |
| `f77-tsh` | 30 | 30 | 0.51 | Tier B after verification | 18 / 0.32 |
| `f84-tsh` | 30 | 30 | 0.51 | Tier B after verification | 18 / 0.32 |
| `f81-tsh` | 30 | 30 | 0.51 | Tier B after verification | 24 / 0.43 |
| `f83c-tsh` | 30 | 30 | 0.51 | Tier B after verification | 18 / 0.32 |
| `f86-tsh` | 30 | 30 | 0.51 | Tier B after verification | 17 / 0.30 |
| `f82b-tsh` | 30 | 30 | 0.51 | Tier B after verification | 17 / 0.30 |
| `f91b-ctl` | 30 | 30 | 0.51 | Tier B after verification | 18 / 0.32 |
| `f73-samp2` | 24 | 24 | 0.45 | Tier B after verification | 14 / 0.26 |
| `resolution-duration109-20261007-candidate-check` | 7 | 7 | 0.41 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| `resolution-duration109-20261007-timed-fast` | 7 | 7 | 0.41 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| `resolution-duration109-20261007-native-p2-<fixture>` | 3 | 3 | 0.41 | needs-owner-call (second native pass; p1 is the keeper) | 0 / 0.00 |
| `resolution-duration109-20261007-native-p1-<fixture>` | 3 | 3 | 0.41 | protected (native keeper/anchor) | 0 / 0.00 |
| `f77-samp2` | 24 | 24 | 0.40 | Tier B after verification | 12 / 0.21 |
| `f74-samp2` | 24 | 24 | 0.40 | Tier B after verification | 12 / 0.21 |
| `f93c` | 26 | 26 | 0.38 | Tier B after verification | 14 / 0.19 |
| `f62-up` | 20 | 20 | 0.38 | Tier B after verification | 10 / 0.19 |
| `f64-fast` | 20 | 20 | 0.38 | Tier B after verification | 10 / 0.19 |
| `f58-pipe` | 20 | 20 | 0.38 | Tier B after verification | 10 / 0.19 |
| `f65-fastsave` | 20 | 20 | 0.38 | Tier B after verification | 10 / 0.19 |
| `f65-fast` | 20 | 20 | 0.38 | Tier B after verification | 10 / 0.19 |
| `continuation111-pass*-chunk2` | 2 | 2 | 0.27 | protected (111-113 qualification) | 0 / 0.00 |
| `continuation111-pass*-chunk0` | 2 | 2 | 0.27 | protected (111-113 qualification) | 0 / 0.00 |
| `continuation111-pass*-chunk1` | 2 | 2 | 0.27 | protected (111-113 qualification) | 0 / 0.00 |
| *40 smaller families* | 494 | | 6.94 | needs-owner-call (proof/warm-up) | 4 / 0.00 |
| *86 smaller families* | 2063 | | 6.09 | Tier B after verification | 190 / 0.35 |
| *358 smaller families* | 438 | | 5.26 | needs-owner-call (early, unnumbered) | 0 / 0.00 |
| *15 smaller families* | 122 | | 1.61 | protected (reference) | 0 / 0.00 |
| *13 smaller families* | 290 | | 0.87 | needs-owner-call (packet >98) | 0 / 0.00 |
| *3 smaller families* | 9 | | 0.33 | protected (111-113 qualification) | 0 / 0.00 |
| *7 smaller families* | 56 | | 0.21 | protected (native keeper/anchor) | 0 / 0.00 |
| *27 smaller families* | 163 | | 0.01 | needs-owner-call (101-110, receipt-anchored) | 0 / 0.00 |
| *86 smaller families* | 11194 | | 0.00 | protected/keepers only | 0 / 0.00 |

## 2. Classification and its basis

**Protected. Never in any tier.**

- `stability-01-{r01,r02,r03,w93c,b2,b4}-<fixture>` (60 captures). These are the reference
  clips. Prior plans name the `w93c`, `b2` and `b4` sets as protected references
  (`99b`/`100b`/`r2`/`packet97-b2`/`after109-b4-retirement-plan.json`, `protected_references`).
  `r01`–`r03` follow the `stability-01-*` rule.
- `f96-twowayw1b2-ref-*` and `f96-twowayw1b4p1-ref-*` (`-ref-` rule). Most of the old-arm
  duplicates match these keys.
- The 116 capture keepers still named by the ten completed receipts in
  `data/resume-20261007/`: the first ten timed captures kept per retired arm
  (`keep_first_per_fixture`), the `resolution-*-native-p1-<fixture>` keepers, and the 26 older
  restoration anchors carried in `protected_previous_anchors`. Every one of the 1,680 paths those
  receipts retired is still absent. That was rechecked read-only.
- `continuation111-*`, `validation/stream112-q*` (now inside the 113 archive),
  `output/archive-stream112-run01/` and `output/archive-stream113-run01/`. These are qualification
  captures of live or recent packets 111–113.
- Unique captures (0.06 GiB in 31 dirs; for example the `f99-…-self`, `f86-tsh`, `f83c-endure` and
  `f62-upsave` odd-ones). They are possible unique failed-run evidence.
- `prepared-*`, `encoder-server-*` (including `.failed-*`), logs, `unlaunched-prepared-*`, the
  boot-health and repair-block directories, and all `summary.json` files. These are the packet
  and run evidence. CURRENT.md and the notes link to them.

**Disposable after verification (Tier B).** Repeat captures from timed, endurance, `rep`, `tsh`,
`samp2`, `ctl` and `lean` throughput arms of packets ≤ 98. Each has a four-tensor key equal to a
protected keeper, or to the first emitted capture of the same fixture in the same arm. The
packet's per-run parity and throughput JSON is in Git (for example
`experiments/ltx25-b70/data/batch-96/shard4-a-w3-b2-p1-r3/f96-shard4aw3b2p1r3-timed-100-parity.json`,
`data/graph-capture-77/f77-endure-50-parity.json`). That is the evidence the notes cite. This is
the same class the lane already retired four times:

- `packet97-b2`: 583 files, 10.96 GiB;
- `99b`, `100b`, `r2`: 106 files each;
- `after109-b4`: 577 files, 10.86 GiB.

Each was retired under a verify-twice / intent / events / receipt protocol with an ordinary-copy
restore map (`2026-10-07-after109-storage-options.md`).

**Needs an owner call.**

- **`quarantine/` (77.94 GiB).** It holds:
  - `ltx-2.5-distilled-transformer-ad9eb77d.rejected` (39.13 GiB);
  - `gemma4-encoder-24ab21fc.rejected` (24.46 GiB);
  - `encoder-publisher-download-prefix.partial` (10.40 GiB);
  - `transformer-publisher-download-prefix.partial` (3.95 GiB).

  The README (`experiments/ltx25-b70/README.md`, about lines 200–237) keeps them as the
  September 13 corruption evidence. That evidence feeds the non-ECC RAM fault story. Both rejected
  files can be rebuilt exactly from data already in Git:
  - the transformer is the promoted file plus the 79 byte changes in
    `data/transformer-corruption-byte-delta.json`, which also records the rejected SHA-256
    `ad9eb77d…`;
  - the encoder is the promoted file plus the 112 byte changes in one 8 MiB block, in
    `data/encoder-repair-promotion.json`. The rejected SHA-256 `24ab21fc0b5c…` is in the README.

  The partials should be byte prefixes of the promoted publisher files. A streamed check proves
  all of this without writing anything: hash the promoted file with the recorded "before" bytes
  patched in, and compare it to the rejected SHA-256; `cmp -n` each partial against its promoted
  file. Once that check passes, the quarantine holds no unique bytes. Either archive it to the
  EX400U (section 4), or delete it with a receipt that names the reconstruction recipe.
- **Proof and warm-up captures of packets ≤ 98** (`*-proofs`, `*-proofn`, `*-wself`): 485
  captures, 6.92 GiB. They duplicate the `-ref` keepers by key, but they are each packet's
  qualification record. They are left out of Tier B unless the owner opts in.
- **Packets 99–110 captures** (`resolution-*`, `f99*`, `f100*`), about 9 GiB still present. They
  are receipt-anchored and their sealed proofs were rebuilt before earlier retirements. The
  remaining `native-p2` and the 109/110 `candidate-check`/`timed-fast` sets (about 3.5 GiB)
  duplicate their `native-p1` keepers, but each needs its own packet-specific plan, the way
  post105/106/107b did. They are not in this plan.
- **Early unnumbered families** (`tp*`, `tq*`, `g20b`, `compiler-*`, `cpu-probe`, `baseline`):
  5.26 GiB across 358 small families. No retirement receipts cover them.
- The stream-01 `requests/` histories (optional Tier A2, below).

## 3. Reclaim tiers

### Tier A: about 0.23 GiB (up to about 0.68 GiB with A2)

| Set | Count | Allocated bytes | Basis |
|---|---:|---:|---|
| A1 `output/s97-twowayw2b2p1dxpu2-stream01-NNNNNNN/preview_*.mp4` | 5,309 files | 251,498,496 (0.234 GiB) | Stream previews of the stopped stream-01 run (`stream01-stop.json`, 04:45:49 UTC). Their tensor hashes stay in `validation/s97-…/summary.json`, whose oracle tensors were already pruned. The `-proofs`, `-proofn` and `-wself` dirs are excluded. |
| A2 `requests/s97-twowayw2b2p1dxpu2-stream01-NNNNNNN/` (optional) | 11,094 dirs | 499,851,264 (0.466 GiB); net less after a small tar.zst | Request histories of the same stopped run. No note or receipt names an individual request. Archive first, then remove. |
| A3 receipted byte-identical duplicates | 0 | 0 | All ten receipts (`packet97-b2`, `99b`, `100b`, `r2`, `resolution103`, `post104`, `post105`, `post106`, `post107b`, `after109-b4`) are `completed`, and all 1,680 paths are absent. |
| `stream112-s*` preview window | 0 | 0 | Moved into `archive-stream113-run01/` during the audit. |

Tier A cannot unblock the image pull on its own.

### Tier B: 89.31 GiB (5,053 captures; 95,897,694,208 allocated bytes, 96,053,744,000 logical)

Selection rule, reproducible from metadata:

1. Take every `output/validation/<run>/tensors.safetensors` whose run name starts with
   `f<N>`/`s<N>` with N ≤ 98.
2. Exclude everything protected in section 2, every `-proof[sn]`/`-wself` family, and every
   capture without a readable `summary.json`.
3. Within each family, in emission (mtime) order, **keep the first capture of each distinct
   four-tensor key**. 1,272 keepers stay this way, which matches the prior
   `keep_first_per_fixture` practice.
4. Each later repeat is a candidate. It maps to the protected keeper with the same key if one
   exists (3,332 files, 57.12 GiB). Otherwise it maps to the family's first capture of that key
   (1,721 files, 32.19 GiB).
5. All 5,053 candidates were regular files with `nlink 1` at the snapshot.

By packet (GiB): 96 = 32.11, 97 = 20.78, 95 = 12.00, 90 = 5.57, 91 = 5.57, 93 = 4.52,
94 = 4.22, 83 = 4.33, 92 = 3.80, 77 = 2.54, 84 = 2.33, 89 = 1.99, 87 = 1.34. The rest (58–74, 81,
82, 86, 98) total under 2.5. The largest single arms are `f96-shard4aw3b2p1r3-timed` (600,
11.12 GiB; all of it matches the `f96-twowayw1b2-ref` keepers) and `f97-twowayw2b1p1dxpu2r2-timed`
(345, 6.45 GiB).

Checks to run before removal. The protocol is the same as the after109-b4 helper; extend
`recovery/20261007-after109-b4-retirement/` rather than inventing a new one.

1. Re-scan fresh. Confirm that no running packet (113 or later) or unit has a request name in a
   candidate family. Confirm every candidate is a regular file with `nlink 1` and is not open
   (`fuser`/`lsof` on the list).
2. **Whole-file SHA-256** of every candidate and every mapped keeper, done twice, with stable
   `(dev, inode, size, mtime_ns)` between the passes. Retire only on whole-file byte equality.
   A capture that matches per tensor but not as a whole file is dropped from the plan, not
   retired. (Earlier receipts found whole-file equality in every case.) The I/O is about 96 GB
   of candidates plus the keepers. That is a few minutes of NVMe reads, at most a few minutes of
   parallel SHA-256, and needs no extra disk.
3. Confirm each candidate's `summary.json` and its packet parity/throughput JSON in Git exist
   and record an exact verdict for that run name.
4. Write a fixed plan JSON listing every candidate → keeper path, both SHA-256s, size and stat,
   and pin its SHA-256. Then write a durable intent file, per-file events (fsync each), and a
   final receipt. Remove only `tensors.safetensors`; keep the run dir and `summary.json`.
5. **Restore map.** `restore --plan ABS --sha256 PIN --receipt NEW` makes an exclusive ordinary
   copy (no hardlinks) from the keeper to the original path, then fsyncs it. It refuses any
   existing destination and refuses unless there is 50 GiB plus the restore size of headroom.
   Replaying an old full raw proof requires a restore first. That is the same semantics as the
   prior receipts.
6. Do it in two or three per-packet batches (96, 97, ≤ 95) so each receipt stays reviewable.

## 4. Archive-first option (Corsair EX400U)

The device is `/dev/sda2`, NTFS, label `CorsairExternal`, partition UUID `4E0E66ED0E66CD91`, 3.6 TB.
It is unmounted now. It is **unqualified for reliability**: the October 6 USB reset and read error
happened after a SMART passthrough (`notes/2026-10-06-ex400u-backup-review.md`), and the drive
holds the October 7 research backup (61.45 GiB, which excludes validation outputs and the
quarantine). It must not be the only home of anything unique. Tier B and Q are reconstructible
from internal keepers or from in-Git deltas, so the external copy is a convenience, not the
primary copy.

The procedure follows the October 6 pilot:

1. Check that the mountpoint is empty and the UUID matches. Mount `ro,norecover` and read the
   free space (it is unknown now). Unmount.
2. Mount once, `rw,norecover,nodev,nosuid,noexec` (ntfs-3g).
3. Write **one tar per packet batch** into
   `/mnt/usb-models/lab-backups/steve-b70s-20261008-validation/`. Tar keeps the `0600` modes and
   names that NTFS would lose. F32 tensors compress poorly, so use plain tar or `zstd -1`. Fsync
   each file.
4. Unmount, remount `ro`, and run a full SHA-256 read-back plus `tar --compare` against the
   internal originals. Check the kernel log for USB or storage errors. Unmount.
5. Only then run the Tier B retirement above. Its receipt records the external archive path and
   SHA-256 as a second restore source.

Transfer estimate at about 150 MB/s NTFS write:

| Set | Bytes | Write | Read-back (assume ~150–300 MB/s) |
|---|---:|---:|---:|
| Tier B | ~95.9 GB | ~11 min | 5–11 min |
| Tier B+ proofs | ~7.4 GB | ~1 min | <1 min |
| Quarantine | 83.7 GB | ~9.5 min | 5–9.5 min |
| All three | ~187 GB | ~21 min | 10–21 min |

The internal hashing for the Tier B check (step 2 of section 3) can be reused for the read-back
comparison. Budget about an hour end to end for everything, including the mounts and log checks.

## 5. Tier A script (written, **not run**)

Save the script as `experiments/ltx25-b70/recovery/20261008-tier-a/tier_a.py`. Run it in three
steps:

1. `plan`: read-only. It writes a fixed list with SHA-256, size and stat for each file.
2. Review the plan.
3. `apply`, with the plan's SHA-256 pinned.

The script refuses if the stream-01 unit is active, if anything differs from the plan, or if a
path looks protected. It records intent before the first unlink and logs per-file events with
fsync, then writes a receipt. It never retries. With `--include-requests`, it first writes a
`tar.zst` of the A2 request dirs to `/home/steve/git-archives/` and verifies it with
`tar --compare` before removing anything. A1 previews are not restorable after removal, which is
acceptable under the rule for stream previews; their hashes stay in the receipt.

```python
#!/usr/bin/env python3
"""Tier A: retire stopped stream-01 previews (and optionally archived request dirs).
plan  : python3 -B tier_a.py plan  --out PLAN.json [--include-requests]
apply : python3 -B tier_a.py apply --plan PLAN.json --sha256 <plan sha> --receipt RECEIPT.json
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time

ROOT = "/mnt/fast-ai/bench-results/ltx25-baseline-20260913"
PREV_RE = re.compile(r"^s97-twowayw2b2p1dxpu2-stream01-\d{7}$")
PREV_FILE_RE = re.compile(r"^preview_\d{5}_\.mp4$")
REQ_FILES = {"history.json", "identity.json", "prompt.json", "result.json", "submission.json"}
PROTECT_RE = re.compile(r"stability-|-ref-|-ref$|proof|wself|archive-|/validation/|quarantine|prepared-|encoder-server-")
UNIT = "ltx97-stream01-server-20261008"
TAR = "/home/steve/git-archives/ltx-s97-stream01-requests-20261008.tar.zst"
RESERVE = 50 * 2**30

def die(msg):
    print("REFUSED:", msg, file=sys.stderr); sys.exit(2)

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def st(path):
    s = os.lstat(path)
    return {"size": s.st_size, "blocks512": s.st_blocks, "ino": s.st_ino, "dev": s.st_dev,
            "nlink": s.st_nlink, "mtime_ns": s.st_mtime_ns, "mode": s.st_mode}

def unit_inactive():
    r = subprocess.run(["systemctl", "--user", "is-active", UNIT], capture_output=True, text=True)
    return r.stdout.strip() != "active"

def free_bytes():
    v = os.statvfs(ROOT); return v.f_bavail * v.f_frsize

def fsync_write(path, obj, exclusive=True):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC), 0o644)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True); f.flush(); os.fsync(f.fileno())
    dfd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY); os.fsync(dfd); os.close(dfd)

def enumerate_targets(include_requests):
    files = []
    out = os.path.join(ROOT, "output")
    for d in sorted(os.listdir(out)):
        if not PREV_RE.match(d):
            continue
        p = os.path.join(out, d)
        ents = os.listdir(p)
        if len(ents) != 1 or not PREV_FILE_RE.match(ents[0]):
            die(f"unexpected contents in {p}: {ents}")
        files.append(("A1", os.path.join(p, ents[0])))
    reqdirs = []
    if include_requests:
        rq = os.path.join(ROOT, "requests")
        for d in sorted(os.listdir(rq)):
            if not PREV_RE.match(d):
                continue
            p = os.path.join(rq, d)
            if set(os.listdir(p)) - REQ_FILES:
                die(f"unexpected contents in {p}")
            reqdirs.append(p)
            for n in sorted(os.listdir(p)):
                files.append(("A2", os.path.join(p, n)))
    for _, f in files:
        if PROTECT_RE.search(f):
            die(f"protected-looking path selected: {f}")
        s = os.lstat(f)
        if not os.path.isfile(f) or os.path.islink(f) or s.st_nlink != 1:
            die(f"not a plain single-link file: {f}")
    return files, reqdirs

def cmd_plan(a):
    if not unit_inactive():
        die(f"{UNIT} is active")
    files, reqdirs = enumerate_targets(a.include_requests)
    entries = [{"set": k, "path": f, "sha256": sha(f), **st(f)} for k, f in files]
    plan = {"schema": "ltx.tier-a-stream01.v1", "root": ROOT, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "include_requests": a.include_requests, "request_dirs": reqdirs, "tar": TAR if a.include_requests else None,
            "counts": {k: sum(1 for e in entries if e["set"] == k) for k in ("A1", "A2")},
            "allocated_bytes": sum(e["blocks512"] * 512 for e in entries),
            "free_bytes_at_plan": free_bytes(), "files": entries}
    fsync_write(a.out, plan)
    print("plan", a.out, "sha256", sha(a.out), plan["counts"], plan["allocated_bytes"])

def cmd_apply(a):
    if sha(a.plan) != a.sha256:
        die("plan sha256 mismatch")
    plan = json.load(open(a.plan))
    if not unit_inactive():
        die(f"{UNIT} is active")
    cur, reqdirs = enumerate_targets(plan["include_requests"])
    if sorted(f for _, f in cur) != sorted(e["path"] for e in plan["files"]) or reqdirs != plan["request_dirs"]:
        die("current file set differs from plan (re-plan)")
    for e in plan["files"]:                       # verification pass: nothing removed yet
        s = st(e["path"])
        for k in ("size", "ino", "dev", "nlink", "mtime_ns"):
            if s[k] != e[k]:
                die(f"stat changed: {e['path']} {k}")
        if sha(e["path"]) != e["sha256"]:
            die(f"content changed: {e['path']}")
    if plan["include_requests"]:
        if os.path.exists(TAR):
            die(f"{TAR} exists; refusing to overwrite")
        rel = [os.path.relpath(d, ROOT) for d in reqdirs]
        subprocess.run(["tar", "--zstd", "-cf", TAR, "-C", ROOT, *rel], check=True)
        subprocess.run(["sync", TAR], check=True)
        subprocess.run(["tar", "--zstd", "--compare", "-f", TAR, "-C", ROOT], check=True)
    receipt = a.receipt
    intent = {"plan": os.path.abspath(a.plan), "plan_sha256": a.sha256, "tar": TAR if plan["include_requests"] else None,
              "tar_sha256": sha(TAR) if plan["include_requests"] else None,
              "free_bytes_before": free_bytes(), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    fsync_write(receipt + ".intent.json", intent)
    ev = open(receipt + ".events.jsonl", "x")
    done = []
    for e in plan["files"]:
        os.unlink(e["path"])
        ev.write(json.dumps({"unlinked": e["path"], "sha256": e["sha256"]}) + "\n"); ev.flush(); os.fsync(ev.fileno())
        done.append(e["path"])
    dirs = sorted({os.path.dirname(p) for p in done})
    for d in dirs:
        os.rmdir(d)                                # fails (and stops) if anything unexpected remains
    ev.close()
    fsync_write(receipt, {**intent, "status": "completed", "unlinked": len(done), "rmdir": len(dirs),
                          "free_bytes_after": free_bytes(), "events_sha256": sha(receipt + ".events.jsonl"),
                          "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print("completed", len(done), "files", len(dirs), "dirs")

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
p = sp.add_parser("plan"); p.add_argument("--out", required=True); p.add_argument("--include-requests", action="store_true")
q = sp.add_parser("apply"); q.add_argument("--plan", required=True); q.add_argument("--sha256", required=True); q.add_argument("--receipt", required=True)
a = ap.parse_args(); {"plan": cmd_plan, "apply": cmd_apply}[a.cmd](a)
```

Owner (or me, with permission), from `/home/steve/llm-optimizations/experiments/ltx25-b70`:

```bash
D=data/resume-20261008
python3 -B recovery/20261008-tier-a/tier_a.py plan --out $D/tier-a-plan.json        # add --include-requests for A2
sha256sum $D/tier-a-plan.json                                                       # review counts/bytes first
python3 -B recovery/20261008-tier-a/tier_a.py apply --plan $D/tier-a-plan.json \
    --sha256 <sha from above> --receipt $D/tier-a-receipt.json
```

Expected values at this snapshot are A1 = 5,309 files and 251,498,496 allocated bytes, and
A2 = 11,094 dirs (55,470 files) and 499,851,264 bytes. Only `preview_*.mp4` files, request JSON
files and the then-empty directories are removed. No validation, proof, reference, archive or
packet path can match the selectors, and `PROTECT_RE` is a second guard.

## Tier C: `/home/steve/src` (41.96 GiB, 141 trees) and `/home/steve/qwen38-current-main-runs` (8.4 GiB)

**Already archived in `/home/steve/git-archives/`: nothing, so Tier C is 0 GiB as asked.** The
archives there are:

- the eight `staging-consolidation-20261007` trees, originally `/home/steve/qwen38-gdn-poison-stage-20260822`,
  `qwen38-m6-head256-*` and `staged-xpu-commitfix*`;
- the four `cache-consolidation-20261006` caches;
- the `flash-next-rescue-20261007` A367/A394 dirs.

All of their sources were already removed after verification and none has reappeared, which was
checked. No `/home/steve/src` tree and no `qwen38-current-main-runs` dir has an archive.

Stale-looking candidates, which would have to be archived first (tar.zst with `--compare`, as in
`notes/2026-10-06-storage-and-recovery-followup.md`): 96 git worktrees that are clean
(`git --no-optional-locks status --porcelain` empty) with no change since before September 1.
Together they hold 20.57 GiB, of which **9.44 GiB is in-tree `build*`/`.deps` output**. Mostly
these are Laguna (July–August) and DeepSeek-V4 kernel lanes. The largest:

| Tree | Total GiB | Build GiB | Last change |
|---|---:|---:|---|
| `deepseek-v4-xpu-kernels-qnorm-routeportfolio` | 1.30 | 1.04 | 2026-07-19 |
| `laguna-xpu-kernels-int4-tile-record-replacement-20260803` | 0.89 | 0.88 | 2026-08-03 |
| `deepseek-v4-xpu-kernels-mwidth-mhc` | 1.14 | 0.86 | 2026-08-26 |
| `laguna-xpu-kernels-shared-elementwise-m12-20260731` | 1.13 | 0.85 | 2026-08-04 |
| `deepseek-v4-xpu-kernels-m2-event-chain` | 0.85 | 0.84 | 2026-07-17 |
| `laguna-xpu-kernels-width12-router-clean-20260726` | 0.94 | 0.67 | 2026-07-27 |
| `laguna-xpu-kernels-int4-wide-prefill-incumbent-20260803` | 0.62 | 0.62 | 2026-08-03 |
| `laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802` | 0.64 | 0.60 | 2026-08-02 |
| `laguna-xpu-kernels-qknorm-rope-m12-20260731` | 0.89 | 0.60 | 2026-07-31 |
| `laguna-xpu-kernels-attention-gate-m12-20260731` | 0.89 | 0.60 | 2026-07-31 |
| `laguna-xpu-kernels-tile12-20260728` | 0.86 | 0.56 | 2026-07-31 |
| `laguna-xpu-kernels-transposed-scale-prefetch-dist3-20260731` | 0.35 | 0.35 | 2026-07-31 |
| `laguna-xpu-kernels-grouped-onednn-int4-20260801` | 0.19 | 0.19 | 2026-08-01 |
| `laguna-xpu-kernels-scale-lane-dedup-20260801` | 0.19 | 0.14 | 2026-08-01 |
| `deepseek-v4-xpu-kernels-record-313156737` | 0.23 | 0.13 | 2026-08-26 |
| `laguna-xpu-kernels-exact-small-portfolio-20260801` | 0.38 | 0.09 | 2026-08-02 |

Reasons for an owner call rather than a tier:

- The memory notes say rebuilds do not reproduce the promoted binaries byte for byte
  ("rebuild reproduction traps", "fp-model=fast rebuilds"), so the build outputs behind past
  Laguna/DeepSeek records may be the only copies.
- `deepseek-v4-xpu` venv editable-installs `/home/steve/src/deepseek-v4-vllm-qnorm-routeportfolio`,
  and lab tests use that venv. It must stay.
- `/home/steve/qwen38-current-main-runs` (84 run dirs from Aug 24–26, the largest 0.67 GiB) is
  referenced by 196 files in the repo. Treat it as evidence and keep it.

## Totals and recommendation

| Option | Reclaim | Free afterwards (from 53.67 GiB) | Above 50 GiB reserve |
|---|---:|---:|---:|
| Tier A only | 0.23 (0.68 with A2) | ~53.9–54.3 | ~4 |
| Tier A + B | ~89.5–90.0 | ~143.4 | ~93 |
| Quarantine only (after streamed reconstruction check) | 77.94 | ~131.6 | ~82 |
| A + B + Q | ~168 | ~221 | ~171 |
| + B+ proofs + C builds | +6.9 / +9.4 | | |

One decision would be: **approve Tier A, plus Tier B with archive-first to the EX400U and
per-packet receipts.** That alone makes room for the vLLM XPU image and a build, with no unique
bytes lost, because every retired capture has a whole-file-identical keeper on the internal disk.
The quarantine is the next lever. It can be fully reconstructed from deltas in Git, but it is
hardware-fault evidence, so it is left to the owner.

## Surprises

- **The quarantine directory is 78 GiB, about a third of the root.** No earlier storage note
  mentions it, and it is fully reconstructible from deltas in Git.
- `output/` previews are only 1.03 GiB. The 135 GiB is validation tensor captures, and 96% of
  those already duplicate another capture by recorded tensor hash.
- 113 latched once at 09:02 UTC on a reused request name (CURRENT.md). During this audit the
  coordinator moved 113 run01's outputs into `output/archive-stream113-run01/` and a new 113
  server began writing into this root. Any reclaim must re-plan against a fresh scan, and must
  never run while an LTX unit is active on a name in the candidate set.
- Stream-01's earlier previews (`…-0000000` through `…-0005400`) and all its oracle tensors were
  already pruned by the stream receipt cleaner. Only 5,309 previews remain.
- There are no remaining "already receipted duplicates": all ten earlier retirements were
  applied in full.
