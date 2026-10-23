# Packet58-onecard-cache23-chain: the max23 capacity screen as a one-card record chain (CPU only)

October 23, 2026. CPU preparation for the one-card IQ3 own runtime (Qwen3.8 Flash-Next UD-IQ3_XXS, the quantized
compressed version, one B70, card 0, lane A). No GPU, /dev/dri, service, setting, PAUSE/STOP/queue file, sudo or
secret was touched; nothing was queued, launched, submitted or committed. packet182c, packet182, packet58aj and
packet58-onecard-cache23 trees are untouched (read only). Packet: `experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/`;
orchestration: `experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/`.

## 1. Why

packet58-onecard-cache23 (the 23 GB expert-cache capacity screen on the packet182c record line) won on card 0 on
2026-10-23 00:57–01:10 UTC: max/max23/max/max23/max = 35.892/**36.546**/35.929/**36.569**/35.925 tok/s, +1.72 % of
both max23 views over every warm max view, fills per token 15.449 → 13.457 (−12.9 %), 60/60 exact, drift 0.01 %, no
kill rule. The +2 % chain bar (36.645) was missed by 0.2 %; the coordinator ruled that the idle lanes allow the chain
and ordered the one-card record chain derived from packet182c with the max23 selection: "the chain's WS128 must beat
35.926720 and pass every exactness gate before submission".

## 2. What was built (changed from packet182c-chain exactly as ruled)

1. **Selection** `--cache-cap max23 --cache-bytes 23049601024` on every model window (K1a/K1b keep the inherited
   fixture); `runtime-selection.json`, the `views.py` sealed-selection literal and the `suite_driver.py` argv/summary
   carry the same three keys; the chain flags `--wait-policy spin --foreground-io kernel` are unchanged. **Device
   plan** copied from packet58-onecard-cache23's root harness: bound 29,828,911,360; driver allowance 671,088,640
   (measured 604,827,916); transient 784,567,808 (2.65× the live peak); arena 23,049,601,024; host admission
   **100,487,123,456** = bound 91,897,188,864 + 8 GiB (every number sourced in that packet's `memory-plan.json`).
2. **Engine** `083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a` bound byte for byte from
   packet58-onecard-cache23 (`engine-binding.json`: packet copies pinned, cache23 sources/native delta/receipts as
   provenance; `restore-inputs.json` gained the two engine records; 0 compiler runs, no relink); host parser
   `03a2aa12…`; K1 fixture `ba49aa81…` unchanged.
3. **Launcher host floor** `MemAvailable` ≥ 100,487,123,456 + 1,073,741,824 = **101,560,865,280 B**.
4. **Bars** record 35.92672010504166 (`cmvjejvoi03qcrf0138emu5a6`) in the pinned ledger snapshot, policy, validator and
   `--update-record`; chain bar 36.6452544 recorded as not met.
5. **Admission gate** `evidence/admission-gate.json`: the five screen views recomputed from 330 raw files read in place
   (result tokens + timestamps, timings/prefill streams, cache.jsonl, DRM samples, suite order, packet49 oracle),
   pinned by sha256 as provenance records; every number equals the screen's summary/decision; lifetime loaded DRM peak
   29,988,990,976 B (511 MB under the guard; 45 MB above the plan's projection).
6. **DRM guard** 30.5 GB unchanged.

Derivation: `ops/onecard_chain_derive.py` through `derive_cache23_chain.py` (packet182's two repairs: flag block
before the entry guard, post-native rehearsal on packet182c's real chain evidence; a prefix rule; and the capacity hook,
because the cache23 engine refuses the parent argv: "single admitted maximum allocation required"). The result is
packet182c-chain byte for byte modulo identity, engine and the four capacity literals (522 identical files); then
`apply_cache23_chain_delta.py` (40 logged edits, `evidence/cache23-chain-delta.json`), `cpu_gates.py` (13 receipts),
`reseal.py` (548 sources, 26 gates, 3 artifacts; 0 parent pins, 0 cross-packet mutable), `final_checks.py --ready`
(READY written last; final pin census 587 pins / 57 manifests / 0 cross-packet mutable; launcher rehearsal 1 positive +
11 refusals with systemd-run never called; live `--dry-run` refused rc 4 as expected while the owner endpoints run).

## 3. Gates (all CPU, all passed)

Script-mode argv (5/5 windows carry the 4 flags once), real parser on the final sources, device/host `--help` lists
max23, pre-device rehearsal 7/7 with the cache23 plan, closure, post-native with the 23 GB plan on the screen's real
WSCREEN census, drain fix 2/0, launch limits (ldd under the closed env, RLIMIT_AS, command properties, planned writes
397,492,208), Python 137 tests OK (9 skipped with reason; a packet182c scratch copy shows the inherited failure
classes: 13 failures + 24 errors), admission gate, engine binding, submission rehearsal (58ad real replay, final-location
CLI `--dry-run`, notes 1,936/2,000 chars, packet182c's real bundle refused), queue plan (host floor 100,487,123,456;
temporary lanequeue plan passed).

## 4. Launch and submission (coordinator, by hand)

`bash experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/launch_chain.sh --dry-run`, then without the flag.
Refuses unless the endpoints are stopped, PAUSE-A archived / PAUSE-B kept, no lane marker or unit, codex frozen,
`MemAvailable` ≥ 101,560,865,280, root free ≥ 25,397,492,208, no `/dev/dri` client, fresh output and fault review,
final READY + seal + verify_ready + command digest; captures the fault review, runs exactly `ready.json.chain_command`
(unit `packet58-onecard-cache23-a`, 7 windows, 90 s gaps, ~35 min), never retries, never touches a PAUSE file or a
unit. Output `evidence/card0-cache23-a` (bulky streams git-ignored). Submission: `prepare_submission.py --chain … --output
<packet>/submission/prepared-a`, `submission.py --payloads … --dry-run` / `--server-dry-run` / real, then
`prepare_submission.py --update-record … --submission-id <ID>`; receipts in `data/localmaxxing-responses/` with key lines
filtered; the notes and result packet disclose the 128-token capped scope and the 21.55 → 23.05 GB capacity change.

## 5. Deviations and not claimed

- The chain output stays at `evidence/card0-cache23-a` (the harness's queue runner, the generator and the sealed
  validator register `evidence/card0-<tag>`); the bulky `run/`, `native-home/`, `*.jsonl` streams are git-ignored.
- The orchestration directory is `ops/packet58c23chain-orchestration` (not `ops/packet58-…`): the pin guard globs
  `ops/<prefix>-*` into every `stage2/packet58-*` packet's closure.
- The generator's post-native rehearsal ran on packet182c's real chain with the parent plan (the only completed chain
  on this host has the 21.55 GB arena); the 23 GB plan is rehearsed on the screen's WSCREEN census.
- The carried 58ah a/b submission disclosure is compacted (facts kept) to stay under the 2,000-character cap.
- `--server-dry-run` needs the key: coordinator step. No device result, speed or record; +1.7 % is the screen's
  in-load measurement. Root free 30.9 GB at the end (26 GB floor kept); packet 121 MB (49 MB ignored build).

## Device result and submission (2026-10-23, chain 01:55-02:29 UTC, unit packet58-onecard-cache23-a): NEW RECORD 36.602512 tok/s, APPROVED

All seven windows passed on card 0 (K1a, K1b, KD, W2m, WS, WS128x, WS128), exact. WS128: **36.602512 tok/s** class-balanced (median of prompt-class
medians; all-prompt median 37.433, p10 34.75; class medians analysis 38.11, code 36.14, documentation 36.89, operations 35.52, prose 36.31), 12/12 prompts
and 1,536 tokens exact vs `iq3-p49-split32-v1`, timing-claim eligible; TTFT median 1.79 s, wall rate 24.6 tok/s.

`prepare_submission.py --chain … --output submission/prepared-a` (under `taskset -c 4-15,20-31`) -> `submission.py --dry-run` (passed) -> `--server-dry-run`
HTTP 200 `{"valid": true}` -> real submit **HTTP 201, run `cmvkcqznb002lng01fsrhjn7t`, APPROVED** (+1.88 % over `cmvjejvoi03qcrf0138emu5a6` 35.926720) -> `--update-record`
(threshold 36.60251162011413, result sha `6791845c…`). Receipt `data/localmaxxing-responses/2026-10-23-packet58-onecard-cache23-chain-a-onecard-ws128.txt`.

Host: endpoints idle since the restore16 validations (01:19 UTC); root 31 GB free after archiving packet124c/136 chain outputs; endpoints restored
afterwards as `*-20261023-restore17`; PAUSE-A re-armed, PAUSE-B untouched. Window receipts: `lineage/window-20261023/` in the packet.
