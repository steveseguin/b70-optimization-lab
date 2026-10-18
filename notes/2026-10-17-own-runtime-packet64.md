# Packet64 record bundle — October 17, 2026

The CPU preparation is complete. Default selection is **24/24 target layers,
draft rank1, production draft, control rollback copies**. All eight selections
share one binary. Draft-HC and batch remain sealed options for the coordinator's
screen decision, followed by a fast reseal. No packet64 device speed is claimed.

## Identity and decisions

- Packet: `experiments/own-xpu-runtime/stage2/packet64-record-bundle`.
- Engine: packet61x spin/pure-spin + HC fusion; packet63 draft-HC selection;
  packet62 control/batch miss selection. Target arithmetic and BF16 KV unchanged.
- Device SHA256: `aeda7568a61544c344857e47ca03a35d1fcd77a5f25a2db45f4486ceed0b30de`.
- Current selection: `1-production-control`; native target split `0` means 24/24.
- Selection SHA256: `987b3b758a81be39e820bd1f5a1b16a5496bf8b42136185ba64f2f8230d2c6aa`.
- Packet61x chain fixes integrated from `53ffe4605`: packet-local KD host
  scratch, extended read/write closure, hash-bound early receipts and resume.
- Lane module integrated from `c495d1d6a`: lane A during exactness; whole host
  only for W2m, WSs and WS128. The new B-screen companion participates in the
  hold-lane-B protocol. Existing sealed packets and running jobs are untouched.

The task supplied a 52.260 tok/s lane-B screen for packet61x at 24/24 versus
51.106/51.307 at 23/25, with all 13 requests exact. Those are supplied parent
screen observations, not new packet64 measurements. Lane A and optional-kernel
screens remain the coordinator's final selection evidence.

## CPU results

- Target: 96 retained fixtures and 24 tokens equal packet56, for all four
  kernel combinations; two fresh draft runs agree on 27 proposals and five
  state files for each combination. Production-width synthetic draft repeats
  also agree.
- Controller: 1,123 cases pass; five mailbox fault gates and seven pure-spin
  wait checks pass. The exact flat-copy body passes 975 descriptors and
  11,899,255 bytes including unaligned tails and sentinel gaps.
- Memory: both placements pass per-rank admission. Batch descriptor bounds
  are 53,760 bytes at 24/24 and 51,392 at 23/25, within existing reserves;
  a conservative 64 KiB rank0 bound is retained. No extra rank1 allocation.
- Plans: all 16 selection/lane combinations pass in both new v3 wrappers
  (32 plans). Standalone wrapper: 32 tests. Lane-aware wrapper: 87 tests.
- Chain/submission/resume suite: 113 tests and seven subtests pass, including
  all eight payload identities and proof-tamper rejection.
- Both placements' extended checkers pass: **12,001 static input paths and
  352 write/scratch paths**, plus generated prerequisite edges, with zero
  errors. Model payloads were only statted, never read.
- Both eleven-window chain plans pass. Final storage precheck leaves about
  3.24 GB above the conservative chain budgets and free floor.
- Owned regular build/selection files: **351,825,567 bytes**,
  counting hardlinks once and excluding read-only parent symlinks; below
  400 MB. Binaries/objects and fusion fixtures use hardlinks where possible.
- Fast reseal: 1.357 seconds for the final default;
  no compilation or device access.

Review fixed resume destinations in the plan/submission entry points and
added early admission-sidecar hashes to preflight. All relevant tests pass.
The new lane integration is still CPU-qualified only; device overlap and
full-chain packet64 quality/performance are pending.

## Exact coordinator commands

[WINDOW.md](../experiments/own-xpu-runtime/stage2/packet64-record-bundle/WINDOW.md)
contains the complete lane-A and lane-B screen commands, all-combination
`--plan` loop, full K0..WS128 launch and explicit same-identity resume.

Fast reseal, before any packet64 chain starts:

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/fast_reseal.py" \
  --placement 1 --draft production --miss control
```

Full chain, inside the coordinator's admitted nice0 user unit, cores
`0-3,16-19`, `OMP_NUM_THREADS=2`, approved library path:

```bash
PREFIX=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet64-record-bundle/build/device-cards01-a
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$PREFIX/evidence/head-k-a/window.json" "$PREFIX/evidence/head-k-b/window.json"
```

The chain's selection, topology and K2 dispatch are sealed. Parent packet61x
early receipts cannot be imported into this different binary. Future resume
requires exact packet64 identity, same boot and every early file hash.

## Submission and retained evidence

[Submission commands](../experiments/own-xpu-runtime/stage2/packet64-record-bundle/SUBMISSION.md)
read the live floor from `scripts/packet49_record_threshold.json`. Payload
notes name prefix, controller spin, pure-spin waits, HC fusion and actual
placement, plus draft-HC/batch only if selected. Portable sidecar proofs bind
whole-host speed windows. The inherited 128-token scope stays explicit and
the strict 512-token gate remains false. Nothing was submitted.

[CPU validation](../experiments/own-xpu-runtime/stage2/packet64-record-bundle/cpu-validation.json),
[path reports](../experiments/own-xpu-runtime/stage2/packet64-record-bundle/evidence/input-checks.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet64-record-bundle/CPU-PREPARATION-CLOSEOUT.md),
[retention/restoration](../experiments/own-xpu-runtime/stage2/packet64-record-bundle/RETENTION.md).

All preparation used nice19, cores 8–15,24–31 and Python `-B`. No GPU,
sudo, health probe, service, power, memory/swap/page-cache setting or reboot
was used. The coordinator retains all device ownership.
