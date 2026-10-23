# Packet58-onecard-cache23-chain: one-card record chain of the max23 capacity screen (CPU-prepared, not launched)

**Status (2026-10-23 02:40 UTC): chain run on card 0 (unit `packet58-onecard-cache23-a`, 01:55-02:29 UTC), all 7 windows passed; WS128 36.602512 tok/s class-balanced, 12/12 exact; submitted and APPROVED as LocalMaxxing `cmvkcqznb002lng01fsrhjn7t` (+1.88 % over 35.926720). Chain receipts under `evidence/card0-cache23-a/`, bundle under `submission/prepared-a/`, window receipts under `lineage/window-20261023/`.**

**Status (2026-10-23, CPU only):** derived, gated and sealed; READY written last; nothing queued, launched, submitted
or committed by the preparation. The chain has not run: device exactness, the fresh WS128 rate and any submission are
pending. Lane A, card 0, Qwen3.8 Flash-Next 125B-A6B UD-IQ3_XXS (the quantized compressed version), 128-token capped
suite, oracle `iq3-p49-split32-v1`, BF16 KV, context 4096, target-only greedy (no draft), resident lookups.

## Coordinator ruling (quoted)

> packet58-onecard-cache23 is a screen winner on card 0 (2026-10-23 00:57–01:10 UTC): +1.72 % over every warm max
> view, fills −12.9 %, exact, no kill rule. The chain bar (+2 %) is not met, but the lanes are idle, which the chain
> policy allows; derive the one-card record chain from packet182c with the max23 selection and prepare it for a card-0
> window; the chain's WS128 must beat 35.926720 and pass every exactness gate before submission.

## What this packet is

packet182c-chain (the 35.926720 tok/s record chain, `cmvjejvoi03qcrf0138emu5a6`) re-derived from
`ops/packet58aj-orchestration` by the same generator (`ops/onecard_chain_derive.py`, with packet182's two repairs),
then changed in exactly the six items the ruling prescribes. A normalised byte comparison with packet182c-chain
(identity strings rewritten) finds 522 identical files; the 18 files that differ and the 3 new files are listed below
and in `evidence/cache23-chain-delta.json` (every edit with before/after digests) and
`ops/packet58c23chain-orchestration/capacity-patch.json`.

| # | Item | packet182c-chain | this packet | Source |
| --- | --- | --- | --- | --- |
| 1 | Selection | `--cache-cap max --cache-bytes 21552729600` | **`--cache-cap max23 --cache-bytes 23049601024`** on every model window (K1a/K1b keep the inherited fixture); `runtime-selection.json` / `views.py` sealed-selection literal / `suite_driver.py` argv + summary carry the same three keys; chain flags `--wait-policy spin --foreground-io kernel` unchanged | packet58-onecard-cache23 `memory-plan.json`, ruling |
| 1 | Device plan | bound 29,963,128,848; driver 536,870,912; transient 2,415,656,960; host 98,990,252,032 | **bound 29,828,911,360; driver allowance 671,088,640 (measured 604,827,916); transient 784,567,808 (2.65× the live peak); arena 23,049,601,024; host 100,487,123,456 = bound 91,897,188,864 + 8 GiB** | `admission.json` (`admission` block) and `memory_plan.py` copied from packet58-onecard-cache23's root harness; `MEMORY.md` |
| 2 | Engine | `1b41fb4d…` | **`083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a`** bound byte for byte from packet58-onecard-cache23 `build/device/own-rt-iq3` (no compile, no relink); host parser `03a2aa12…` from the same build; K1 fixture `ba49aa81…` unchanged | `engine-binding.json` (packet copies pinned; cache23 sources, native delta and build/identity/preparation/loader receipts as provenance), `ops/.../inputs` = the same record in the orchestration READY |
| 3 | Launcher host floor | 98,990,252,032 + 1 GiB | **100,487,123,456 + 1,073,741,824 = 101,560,865,280 B** `MemAvailable` | `launch_chain.sh`, `evidence/launch-limits.json`, `evidence/queue-gate.json` |
| 4 | Bars | 34.573038 (`cmvf31py4…`) | **35.92672010504166 (`cmvjejvoi03qcrf0138emu5a6`)**: the sealed validator and `--update-record` refuse anything at or below it and the live ledger | `record-threshold.snapshot`, `submission-policy.json` |
| 5 | Admission gate | generator bracket gate on the v5 summary | the generator's bracket gate **plus `evidence/admission-gate.json`**: the five screen views recomputed from 330 raw files read in place (tokens, timestamps, cache.jsonl, DRM samples, oracle), pinned by sha256 | `ops/packet58c23chain-orchestration/admission_gate.py` |
| 6 | DRM guard | 30.5 GB native after-load + supervisor | **unchanged** (never lowered); the screen's lifetime loaded DRM peak was 29,988,990,976 B, 511 MB under it | `evidence/admission-gate.json` |

Unchanged from packet182c: the seven windows K1a → K1b → KD → W2m → WS → WS128x → WS128 with 90 s gaps, the
whole-host hold, the quiet-host rule (codex frozen; the launcher refuses an active unfrozen `codex-*` unit), no
quiet-host rerun (one attempt), the drain spacing, the fresh fault review (exactly two known fault lines on this
boot), the oracle, every exactness gate, the submission path (shared CLI + `packet58_submission.py` validator).

Admission numbers (recomputed, `evidence/admission-gate.json`): A0/B0/A1/B1/A2 = max/max23/max/max23/max =
35.892 / **36.546** / 35.929 / **36.569** / 35.925 tok/s; minimum gain of both max23 views over every warm max view
**+1.717 %**; drift 0.010 %; 60/60 exact; fills per decode token 15.449 → 13.457 (−12.9 %); the chain bar
36.6452544 (+2 %) is not met by 0.2 %; no kill rule fired. Expected WS128: about 36.5–36.6 tok/s against
35.926720 (+1.7 %), an expectation, not a measurement.

## Files that differ from packet182c-chain

`.gitignore` (chain streams ignored), `MEMORY.md`, `admission.json`, `budget_gate.py`, `memory_plan.py`,
`packet58_submission.py` (max23 argv, full_cache_bytes 23,049,601,024, label/identity/notes disclose the capacity and
the 128-token scope, `immutableExpertWeightCacheBytes`), `rehearse_submission.py`, `restore-inputs.json` (engine
records), `runtime-selection.json`, `suite_driver.py`, `views.py`, `test_admission58e.py`, `test_memory_plan.py`,
`test_memory_sensor.py`, `test_ready.py`, `test_resident.py`, `test_submission.py` (the 21.55 GB record argv is a
refused value), `host-admission/seal.json` (the sub-bundle seal re-bound to this packet's path-rewritten copies, as in
182c). New: `engine-binding.json`, `lineage/inherited-58aj-README.md`, `lineage/inherited-58aj-DO-NOT-REPEAT.md`
(the packet58aj documents this harness inherits). The inherited gate scripts whose receipts were copied byte for byte
from the parent (`argument_gate.py`, `native_parser_gate.py`, `screen_gate.py`, `plan_queue.py` proposal text,
`screen-reader/views.py`) still spell the parent's 21.55 GB literals; none of them is on the launch path, which carries
max23 (`evidence/chain-flags.json`, `evidence/script-argv-check.json`).

## Gates (all CPU; `ops/packet58c23chain-orchestration/cpu_gates.py --check`)

| Gate | Result | Receipt |
| --- | --- | --- |
| Derivation (generator) | bracket gate, device/host `--help` under Landlock, real parser on every model window, pin relocation (275), seal, verify_ready, pin audit (0 parent pins), closure (84), pre-device 7/7, post-native on packet182c's real chain, temporary lanequeue plan | `ops/.../derivation.json`, `capacity-patch.json`, `derivation-READY-FOR-DEVICE.json` |
| Argument (script mode) | every model window's native argv carries the 2 chain flags and the 2 capacity flags exactly once | `evidence/script-argv-check.json` |
| Real parser (final sources) | cache23 host parser accepts each argv, refuses an invalid value, parses without each flag | `evidence/chain-flags.json` |
| Help | `--cache-cap 18GB\|max\|max23`, `--cache-bytes`, `--wait-policy`, `--foreground-io` listed by both binaries | `evidence/help-cache23.json` |
| Pre-device rehearsal | window.main of all 7 windows to the device boundary with the cache23 plan | `evidence/predevice-cache23.json` |
| Closure | runtime-read closure against the parent packet | `evidence/closure-cache23.json` |
| Post-native (cache23 plan) | `postload_observation` with this packet's WS128 plan on the screen's real 23 GB WSCREEN census equals the screen's receipt; K1a/K1b summaries equal | `evidence/postnative-cache23.json` |
| Drain fix | 2 FIXED, 0 UNFIXED | `evidence/drain-fix.json` |
| Launch limits | ldd of the 3 binaries under the closed loader env, RLIMIT_AS unlimited, chain command properties, planned writes 397,492,208 | `evidence/launch-limits.json` |
| Python | 137 tests OK (9 bracket-evaluation tests skipped on the generated verify_ready); packet182c scratch copy: 119 tests, 13 failures + 24 errors (its inherited classes) | `evidence/python-cpu-gates-cache23.json` |
| Admission | five views recomputed from raw data; screen winner; chain bar not met; record bar pinned | `evidence/admission-gate.json` |
| Engine binding | packet copies and cache23 sources re-hashed; 0 compiler runs | `evidence/engine-binding-check.json` |
| Submission rehearsal | 58ad real evidence replay with in-memory identity substitutions (max23/chain flags), final-location CLI `--dry-run`, notes 1,936 of 2,000 chars, record-update on a scratch ledger; packet182c's real bundle refused | `evidence/submission-rehearsal-cache23.json` |
| Queue | `queue_runner.py --plan` (host 100,487,123,456; 7 windows; 90 s gaps; timing windows on cores 0-3,16-19) and a temporary lanequeue plan | `evidence/queue-gate.json`, `ops/.../queue-plan.log` |
| Reseal | 546 sources, 26 gates, 3 artifacts; pin audit 55 manifests, 0 parent pins, 0 cross-packet mutable | `ops/.../reseal.json`, `build-receipt.json`, `submission-pins.json` |
| Final checks | pin census on the READY closure, private plan, launcher rehearsal (1 positive + 11 refusals, systemd-run never called), live `--dry-run` observed, verify_ready | `evidence/final-checks.json`, `evidence/final-pin-guard.json`, `evidence/launcher-rehearsal.json`, `READY-FOR-DEVICE.json` (written last) |

## Launch (coordinator only, by hand)

1. Stop the three owner endpoints (`qwen38-27b-fp8`, `qwen38-27b-fp8-tp1-test`, `qwen38-27b-vision`), archive
   `ops/lane-queue/PAUSE-A`, keep `PAUSE-B`, freeze or stop `codex-*` units, no lane job in flight.
2. `MemAvailable` ≥ 101,560,865,280 B; root free ≥ 25,397,492,208 B; no `/dev/dri` client.
3. `bash experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/launch_chain.sh --dry-run`
   (all guards, seal + verify_ready, a temporary fault-review capture; prints `would run: systemd-run ...`).
4. `bash experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/launch_chain.sh` — captures
   `evidence/fault-review-cache23-a.json`, runs exactly `ready.json.chain_command` (unit
   `packet58-onecard-cache23-a`), waits ≤ 120 s for the unit to be active, returns. Never retries.
5. Watch `systemctl --user is-active packet58-onecard-cache23-a`, `journalctl --user -u packet58-onecard-cache23-a`,
   `evidence/card0-cache23-a/queue.json` (`completed` grows window by window), `<W>/window.json`, `<W>.log`.
   About 35 minutes. Commit `summary.json`/`window.json`/`queue.json`/`*.log` right after; the bulky `run/`,
   `native-home/` and `*.jsonl` streams of each window are git-ignored (`.gitignore`), never untracked-and-unignored.
6. After the chain, restoring PAUSE-A and the endpoints is the coordinator's decision. On a fault: fault-halt rules;
   nothing here resets, restarts or retries.

Output: `evidence/card0-cache23-a` (the one-card harness, its queue runner and its submission validator register
`evidence/card0-<tag>`; the bulky device streams are ignored by `.gitignore`).

## Submission (after a finished, exact chain)

```bash
# 1. prepare (read-only on the chain; refuses unless WS128 is exact and > 35.92672010504166 and > the live ledger)
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/prepare_submission.py \
  --chain experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/evidence/card0-cache23-a \
  --output experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/submission/prepared-a </dev/null
# 2. local dry run (no key, no network); 3. coordinator: --server-dry-run; 4. coordinator: real submit (no flag)
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/submission.py \
  --payloads experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/submission/prepared-a/payload-queue.json --dry-run </dev/null
# 5. after an APPROVED id: append the record (improvement only)
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/prepare_submission.py \
  --update-record experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/submission/prepared-a/result.json --submission-id <ID> </dev/null
```

Receipts of `--server-dry-run` and the real submit go to `data/localmaxxing-responses/<date>-packet58-onecard-cache23-chain-a-onecard-ws128.txt`
with key lines filtered. The result packet and the notes disclose the 128-token capped scope (`realistic_final_gate.passed=false`,
no strict512 claim) and the capacity change (23.05 GB `max23`, +1.5 GB over the 21.55 GB record line; DRM guard unchanged).

## Not claimed

No device result, speed or record. The +1.7 % is the screen's in-load measurement, not a fresh-process chain
measurement. No strict512/full512 gate. The inherited parent gates (`postload-allocation-cpu`, `fullshape-submit-cpu`,
`resident-*`, `packet58ajb-preparation`) describe the parent harness engine; the cache23 engine's own allocation,
full-shape and production-shape proofs are packet58-onecard-cache23's receipts, pinned as provenance in
`engine-binding.json`. Research packet, not a public release.

[Boundaries](DO-NOT-REPEAT.md) · [Retention](RETENTION.md) · [Closeout](CPU-PREPARATION-CLOSEOUT.md) ·
[Memory](MEMORY.md) · [Window contract](WINDOW.md) · orchestration `ops/packet58c23chain-orchestration/README.md` ·
note `notes/2026-10-23-packet58-onecard-cache23-chain.md` · screen `../packet58-onecard-cache23/README.md`.
