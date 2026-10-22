# Packet182: fill pacing priced and not built; the kernel-I/O win re-bracketed with a repaired chain (CPU only)

October 22, 2026. CPU preparation for the one-card IQ3 own runtime (Qwen3.8 Flash-Next
UD-IQ3_XXS, the quantized compressed version, one B70). No GPU, service, setting, PAUSE file or
live queue was touched; nothing was queued or committed. Packet:
`experiments/own-xpu-runtime/stage2/packet182-onecard-kio-rebracket/`. Proposal (not queued):
`experiments/own-xpu-runtime/ops/lane-queue/proposed-p182-one-card-A.txt`.

## 1. The resume-queue item (b) does not qualify

Item (b) of the October 19 owner-pause resume queue asked to price fill pacing/deferral because
"the p176 readout shows ~1.0 ms/token of wall outside the transfer window". That number is not
a fill cost:

- It is the pre-device packet176 pricing, (0.0666 - 0.0349) ms/MB x 30.63 MB/token = 0.97 ms,
  with both slopes fitted over filled tokens only. The device readout read at 12:00 UTC on
  October 19 printed no B-view slope; the resume line was written five minutes later.
- On packet171b's real spin streams (the same spin/copy configuration as packet176's A arm),
  unfilled tokens show the same 0.032 ms/MB slope against the next token's fill bytes. Fill bytes
  follow miss intensity, so the slope prices the misses, not the fills. Packet176's `moved_rule`
  also fires on packet171b, where nothing moved.
- Measured directly: a filled token costs 0.628 ms more than an unfilled one outside the transfer
  window, i.e. 0.313 ms/token. The kernel-I/O arm turned 1.095 of the 1.168 ms of removed transfer
  into wall gain, leaving 0.074 ms/token. If fills became completely free: 0.387 ms/token, +1.42%.
  Pacing or deferral moves the same bytes, so the realistic gain is 0 to +0.3% (the packet174 fill
  kick measured -0.02%).

Below the +2% chain rule; packet174's DO-NOT-REPEAT already forbids re-timing fills while total
bytes set the cost. Receipt: `evidence/fill-lever-price.json`; analyzer: `screen/mechanism.py`
`fill_split` (tested on the real packet171b streams).

## 2. What was built instead: the packet176 kernel-I/O win, re-bracketed, with a chain that works

The largest one-card gain the ledger supports is packet176's copy-engine-free token I/O: bracket
B 35.982/35.981 vs warm A 34.621/34.640 tok/s, +3.87%, 60/60 exact. It was never banked:

- chain 176-a ran the parent poll/copy line (31.83 tok/s) because the chain generator puts its
  flag wrapper after `suite_driver.py`'s `__main__` entry; `--predevice-check` imports the module
  and cannot see it. `ops/onecard_chain_derive.py` is still unfixed.
- On **2026-10-19 at 21:42 EDT an untracked-file cleanup removed** packet176's v5 tree (its
  bracket summary, digest `ad74c8ef...`), the packet176c, packet58aj and packet58as chain trees
  (except two WS128 summaries) and packet58as's v5 run tree. Only ignored trees (packet171b's)
  survived. No chain can be derived from the packet176 bracket any more, and the generator's
  post-native gate has no input anywhere on this host. The packet176 per-view numbers above come
  from the coordinator's session record of that readout.

Packet182 is a private copy of packet176 with the **same device engine
`1b41fb4da10a3c8c644f44f6288b9b1af0f46300847a06a254420796af921145`** (byte copy; only the
16 KB K1 exec wrapper was rebuilt so it runs this packet's core). Arms in one load:
A0/B0/A1/B1/A2 = spin (record line) / spin + kernel I/O. Expected: chain WS128 about
35.9-36.0 tok/s against the 34.573038 record, **+3.9 to +4.1%**.

Win-path chain, prepared and **not armed** (`chain/ARMING.md` has the exact `systemd-run`
command): `chain/p182-win.sh` waits for the v5, applies the chain rule (60/60 exact, minimum gain
>= +2%, slower B >= 1.02 x record), refuses while any owner endpoint is active, derives
`packet182c-chain` with `chain/derive_chain.py` (the ops generator with the flag block moved
before the entry guard, plus a carried post-native rehearsal), checks the native argv in script
mode on all five model windows, runs the generator's three checks, and launches through
`chain/p182-chain.sh`, which, unlike the quiet2 script, never deletes PAUSE-A/PAUSE-B.
The window driver must wait for `p182-win` to end before it restores the endpoints: the
2026-10-22 driver restores them right after the last queue row, which would put
`qwen38-27b-fp8` back on card 0 under the chain.

## 3. Gates (all CPU)

| Gate | Result |
| --- | --- |
| Production-shape startup: real WSCREEN argv through the device-define CPU probe under Landlock (no /dev/dri, no /mnt) | pass: 5 views, 60 requests, 130 reset sensors, 24 tail stores + 24 head loads; same counts as packet176 |
| Real launch path to the intercepted native exec, K1a/K1b/WSCREEN | pass (WSCREEN MemAvailable substituted with the endpoint-free 120.6 GB because the owner's endpoints run; disclosed per window) |
| Analyzer on real device evidence (packet171b, 60 exact requests) | pass; packet176 readout fields identical to its committed output |
| Python tests vs an unchanged packet176 copy | 106 vs 103, no new failure |
| Binary gates | carried by byte identity (5 binaries) |
| Chain rehearsal in a scratch repo root | packet176c-chain refused in script mode on 5/5 windows; derived packet182c: pin audit 0 parent pins, closure 84, pre-device 7/7, script mode 5/5; `--predevice-check` and `--closure-check` pass; `--postnative-check` refuses (no chain evidence on the host) and the carry (543 identical files vs packet176c) stands in |
| Waiter dry run | win: derive on the current boot, checks pass, stops before lock/launch; +1.93%: no chain; FAILED: exit 2; real endpoint active: exit 5 |
| Seal, proposal, plan after seal, `rehearse_entry --report`, pin guard | pass |
| `final_checks.py --ready` | READY written last; pin guard on the full READY closure: 1,224 pins, 54 manifests, 1,216 packet-local, 7 oracle targets, 1 own proposal, **0 cross-packet mutable pins**; private-copy live plan passed |

A first READY was withdrawn by me minutes after writing it, before anything used it, to add the
endpoint guard (kept under `evidence/withdrawn-ready-20261022/`).

## 4. Rows

| Row | Duration |
| --- | --- |
| `packet182-one-card-v5-A` (K1a, K1b, WSCREEN v5) | ~13-14 min (packet176: 13 min 20 s); plan 700-1200 s; watchdog 7200 s |
| win-path chain `packet58-onecard-182-a` (7 windows, 90 s gaps), only if the chain rule holds | ~35 min (chain 176-a: 35 min 2 s) |

## 5. Not done or not claimed

- No device run, speed or record. The re-bracket re-measures packet176's binary; it adds no new mechanism.
- `ops/onecard_chain_derive.py` itself is not fixed (outside this packet); the wrapper is packet-private.
- `--postnative-check` cannot pass on this host until a completed one-card chain tree exists again.
- The engine still reads `rope.bf16` from packet176's frozen inputs at runtime (compiled path; tracked,
  hash-checked at load); moving it would need a rebuild of the measured binary.
- Disk: packet182 is 152 MB on disk (119 MB ignored `build/`), 33 MB of committable files; root had
  34 GB free at the end.

Next one-card lever after this chain, by the ledger: nothing else prices at +2% (packet171 audit
items 2-5 are 0.05-0.3 ms each; packet170 MTP closed; fill pacing above). Once fills overlap compute,
what remains is the cost of the misses themselves, to be priced from routed IDs against published
pointers (packet58ai: never infer miss counts from fills), through publication lag or capacity, not
fill timing.
