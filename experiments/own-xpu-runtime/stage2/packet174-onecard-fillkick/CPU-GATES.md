## CPU gates (all pass; READY-FOR-DEVICE.json written last)

| Gate | Evidence |
| --- | --- |
| One `ops/compile_turn.py` turn: GNU host, device, Intel host, wait tests, K1 help, preparation probe | `evidence/build.json` (the probe binary from that turn is reused by `preparation_gate.py` after a missing-symlink resume, `probe_reused_from_single_compile_turn`) |
| GNU/Intel byte gates: 120 request resets and 10 view resets byte-equal to packet58aj; oracle refusal; parent poll/spin order refused | `evidence/cpu-exactness.json` |
| `--fill-kick`: on/off/default byte-equal (GNU+Intel); parsed in KD/W2m/WS/WS128x/WS128 argv; the parent binary refuses it (fails on old code); bracket/draft/old-order refusals | `evidence/fill-kick.json` |
| Source-delta test: passes here, fails on the parent source; fill/copy bodies and cache policy untouched | `evidence/fillkick-delta-test.json` |
| Real device-define CPU preparation: 5 view resets, 60 request resets | `evidence/preparation.json` |
| Analyzer on real packet58as and packet171b brackets: old identity refused; readout reproduces the same-token fill-byte law | `evidence/analyzer-real-parent.json` |
| Every native flag in `--help`; queue-runner argument replay | `evidence/flags.json`, `screen/evidence/argument-gate.json` |
| Imports under the closed launch env; temporary `lanequeue plan`; `rehearse_entry --report` (WARN: no shared preparation adapter for an unranked one-card argv); pin guard | `evidence/entry-imports.json`, `evidence/queue-plans.json`, `evidence/shared-entry-report-final.json`, `evidence/pin-guard.json` |

The inherited Python unit suite (`run_cpu_gates.py`) is not a READY input: like packet171b, the record-chain modules it imports were removed.

_Moved from README.md by the coordinator (2026-10-19 11:05 UTC): README.md is sealed by screen/build-receipt.json at e0424827…, and the pin guard refused the plan after this table was appended._
