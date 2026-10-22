# Packet182: one-card kernel-I/O re-bracket with a repaired win-path chain

CPU preparation only. No GPU, service, setting, PAUSE file or live queue was touched; nothing
was queued. Lane A, card 0, Qwen3.8 Flash-Next 125B-A6B UD-IQ3_XXS (the quantized compressed
version), 128-token capped suite, oracle `iq3-p49-split32-v1`, BF16 KV, context 4096.

## Why this packet and not the fill lever

The owner's resume queue (CURRENT.md, 2026-10-19 12:02 UTC, item b) asked to price "fill
pacing/deferral" on the packet176c line because "the p176 readout shows ~1.0 ms/token of wall
outside the transfer window". Priced on the retained real evidence, it does not qualify
(`evidence/fill-lever-price.json`, `fill_price.py`):

| Quantity | Value | Source |
| --- | ---: | --- |
| "~1.0 ms/token" | (0.0666 - 0.0349) ms/MB x 30.63 MB/token = 0.970 | pre-device packet176 pricing; slopes over filled tokens only |
| Same outside-transfer slope on UNfilled tokens vs the next token's fill bytes | 0.0321 vs 0.0317 ms/MB | packet171b A1 real streams: it is miss intensity, not fill cost |
| Filled minus unfilled wall outside the transfer window | 0.628 ms per filled token (49.9% of tokens, 61.4 MB each) | packet171b A1/A2 real streams (same spin/copy config as the packet176 A arm) |
| Fill-attributable wall, A line | 0.313 ms/token | same |
| Transfer removed by kernel I/O / wall gained (packet176 v5) | 1.168 / 1.095 ms -> 0.074 ms/token not recovered | packet176 v5 per-view readout (transcribed; tree lost) |
| Ceiling if fills became free on the kernel-I/O line | 0.387 ms/token = **+1.42%** | sum of the two rows above |
| Realistic for pacing/deferral (same bytes) | 0 to +0.3% | packet174 fill kick -0.02%; DO-NOT-REPEAT |

Below the +2% chain rule, and packet174's DO-NOT-REPEAT already says total bytes, not their
placement, set the cost. Not built.

The next-best one-card lever the ledger supports is the one the resume queue assumed was
already banked: **packet176's copy-engine-free foreground token I/O** (`--foreground-io kernel`),
bracket B 35.982/35.981 vs warm A 34.621/34.640 tok/s, **+3.87%** minimum, 60/60 exact, drift
0.055% (2026-10-19 11:40-11:54 UTC). It never reached a correct record chain:

- chain 176-a ran the parent poll/copy line (31.83 tok/s): the chain generator appended the
  flag wrapper after `suite_driver.py`'s `__main__` entry;
- the packet176 v5 tree (bracket summary `ad74c8ef...`) and every completed one-card chain tree
  were removed with untracked files on 2026-10-19 21:42 EDT, so no chain can be derived from
  that bracket (the generator re-hashes the summary) and the generator's post-native gate has no
  input anywhere on this host.

**Expected gain:** chain WS128 about 35.9-36.0 tok/s against the 34.573038 record, **+3.9 to
+4.1%** (packet176 slower B 35.981 / 34.573 = +4.07%; the packet58as chain matched its bracket
B within 0.03%). Rule 8 (chain only at >= +2%) is met; the waiter re-checks it on the new bracket.

## What changed vs the parent (packet176 at HEAD `fb2b02559`)

| Item | Change |
| --- | --- |
| Device engine `build/device/own-rt-iq3` | **none**: `1b41fb4da10a3c8c644f44f6288b9b1af0f46300847a06a254420796af921145`, byte copy of the binary whose B arm measured +3.87% |
| K1 core, GNU/Intel host binaries, preparation probe | none (byte copies; `evidence/inherited-binary-gates.json`) |
| K1 exec wrapper `build/device/p58-cache-fixtures` | rebuilt (g++ -O2, one compile turn): `1b9ef8eb352c11b878d3efc1a5ffb132c99dd297761b3fe23ae9c7694a6bb411`; it now execs this packet's core instead of packet176's (`evidence/k1-wrapper.json`) |
| Harness | path/identity rewrites (10 files, `lineage/packet182-copy.json`), 2 seal pins re-bound (`rebind_pins.py`), lanequeue unit prefix `packet182-`, proposal name, readiness text |
| `screen/mechanism.py` | additive `fill_split` / `fill_lever_price` (filled vs unfilled tokens, unfilled-vs-next-fill control slope); packet176 fields byte-for-byte unchanged on real evidence |
| `screen/argument_gate.py` | CPU gate only: substitutes MemAvailable with the endpoint-free 120.6 GB (2026-10-22 packet181 window) when the owner's endpoints hold it below the bound; recorded per window |
| Chain path (`chain/`) | `derive_chain.py` (fixed flag placement + carried post-native rehearsal), `script_argv_check.py`, `chain_gate.py`, `p182-win.sh` (waiter), `p182-chain.sh` (launcher that never deletes PAUSE files), `ARMING.md` |

Runtime read outside this packet (disclosed, not pinned): the unchanged engine opens
`fs::path(__FILE__).parent_path()/"rope.bf16"`, compiled in packet176, i.e.
`packet176-onecard-kernelio/frozen-inputs/.../packet58j-onecard-port/rope.bf16` (tracked,
4,194,304 B, sha256 `92a8f392...`); the binary refuses at load if its hash differs. Rebuilding
to move it would change the measured binary.

## Arms (one load, one process, v5 A/B/A/B/A)

| View | Arm | Native selection |
| --- | --- | --- |
| A0 | `spin`: packet58as record line, `--foreground-io copy` (BCS foreground list) | exact warm-up, excluded from speed/drift |
| B0, B1 | `spin-kio`: spin + one CCS tail-store kernel and one CCS head-load kernel, no copy command | candidate |
| A1, A2 | `spin` | warm controls |

12 x 128-token requests per view (60), full packet58ah composition, resident lookups, 21.55 GB
cache, overlap maintenance, zero-copy misses. A third arm (fill variant) was not built: it is
priced below +2% and needs a native change plus a bracket-table change.

## Gates

| Gate (CPU) | Result | Receipt |
| --- | --- | --- |
| Copy + identity rewrites, 2 pins re-bound | 1,148 files, 10 rewritten, sealed packet176 artifacts byte-equal | `lineage/packet182-copy.json` |
| K1 wrapper rebuild + `--help` | pass | `evidence/k1-wrapper.json` |
| Inherited binary gates by byte identity | 5 binaries == packet176 receipts; 7 receipts carried as provenance | `evidence/inherited-binary-gates.json` |
| Production-shape startup: real WSCREEN argv through the device-define CPU probe under Landlock (no /dev/dri, no /mnt) | 5 views, 60 requests, 130 reset sensors, 24 tail stores + 24 head loads; prepared 6,774 / issued 66,648 (= packet176); peak RSS 1.14 GB | `evidence/preparation.json` |
| Real launch path (queue_runner -> window -> suite_driver -> intercepted native exec), K1a/K1b/WSCREEN | pass; old unit gate refused; WSCREEN MemAvailable substituted (live 98.18 GB) | `screen/evidence/argument-gate.json` |
| Analyzer on REAL device evidence (packet171b, 60 exact requests re-checked vs the oracle) | packet176 fields identical to packet176's committed readout; fill split on 5 views; spin-cq refused as kio | `evidence/analyzer-real-parent.json` |
| Python tests, differential vs unchanged packet176 | 106 vs 103 tests, no new failure; additions + unit-name + delta tests pass | `evidence/python-cpu-gates.json` |
| Drain-fix check | 2 FIXED, 0 UNFIXED | `evidence/drain-fix.json` |
| Chain rehearsal (scratch repo root) | packet176c-chain refused in script mode on 5/5 windows; derived packet182c passes bracket/help/parser/pin-relocation/seal/verify_ready/pin-audit (0 parent pins)/closure (84)/pre-device (7/7)/temporary plan; script mode 5/5 with both flags; `--predevice-check` and `--closure-check` pass; `--postnative-check` refuses (no chain evidence on host) and the carry (543 identical files) stands in | `evidence/chain-rehearsal.json` |
| Waiter rehearsal, dry run (`chain/p182-win.sh` in scratch roots, `P182_DRY_RUN=1`) | win case: chain rule CHAIN, derive WITHOUT `--cpu-rehearsal` on the current boot, script mode 5/5, pre-device + closure pass, post-native logged, `p182-chain.sh --check` ok, stops before lock/QUIET/launch; +1.93% case: no chain; FAILED event: exit 2, no derive; real owner endpoint active: exit 5, no derive | `evidence/waiter-rehearsal.json` |
| Fill lever price | not built: ceiling +1.42% | `evidence/fill-lever-price.json` |
| Seal, proposal, temporary plan, `rehearse_entry --report`, pin guard, READY last + pin guard again | see `READY-FOR-DEVICE.json` | `package_rows.py`, `check_queue_rows.py`, `final_checks.py` |

## Rows

| Row | What | Duration |
| --- | --- | --- |
| `packet182-one-card-v5-A` (proposal `ops/lane-queue/proposed-p182-one-card-A.txt`) | K1a, K1b, WSCREEN one-load v5 | ~13-14 min (packet176: 13 min 20 s); plan 700-1200 s; watchdog 7200 s |
| Win-path chain (not a queue row; `chain/p182-win.sh`, armed per `chain/ARMING.md`) | `packet58-onecard-182-a`: K1a, K1b, KD, W2m, WS, WS128x, WS128, 90 s gaps | ~35 min (chain 176-a: 35 min 2 s); launcher deadline 3 h |

Gate of the v5 (unchanged): both B >= +0.5% over every warm A, drift <= 3%, 60/60 exact.
Chain rule on top: minimum gain >= +2% and slower B >= 1.02 x the live record.

## Not claimed

No device result, speed or record; no new mechanism (this re-measures packet176's B arm with
the same binary). No strict512/full512 gate: 128-token capped suite and the record line's chain
windows only. The post-native rehearsal is carried, not re-run. The argument gate's WSCREEN host
admission ran on a substituted MemAvailable. The fill-lever ceiling is arithmetic on retained
evidence, not a measurement of a pacing build.
