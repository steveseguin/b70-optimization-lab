# Packet104b: TARGET gate/up tile16 screens

The coordinator explicitly overrides the original 15% micro gate for
`target-gate-tile16` and `target-gate-halfcache-tile16` only. Their measured
operator time ratios are 0.898048 and 0.892953. **Neither passed the original
micro gate.** Seven other arms are closed in [DO-NOT-REPEAT](DO-NOT-REPEAT.md).
This packet prepares screens; it claims no model speed or full-model quality.
See [the override](screening-override.json) and [micro closeout](micro-closeout.md).

## Exact baseline and candidates

`p104b-parent-selection.json` snapshots packet97's selected route-fast,
rec-both-plus, E1 half-cache and draft choices. Every screen adds packet100's
down-tile16. Production keeps E1. The plain gate-tile16 candidate removes E1;
the gate-halfcache-tile16 candidate retains it. Thus only the half-cache arm
isolates the gate transpose against this control. Half-cache is an exact FP32
cache of decoded weight scales; KV stays unchanged at full 16-bit precision.

Active screen views are under `selections/`. Earlier `views/` and
`integration-plan.json` describe the old, unqualified packet100-baseline
preparation and are not screen inputs.

## CPU evidence and boundary

- [Byte identity](evidence/cpu-byte-identity.json): GNU and Intel, two fresh
  runs per view. Each run checks 36 cases, 13,824 raw FP32 chains, 432 trees,
  401,587,200 layout bytes and all 65,536 half-scale patterns. All three views
  produce the same bytes. [The unchanged down proof](evidence/down-proof104b.json)
  binds packet100's separate repeated GNU/Intel checks to the identical local
  source; full-shape tests check both operators' actual selected consumers.
- [Full-size startup and admission](evidence/full-shape.json): all six
  view/rank combinations; 24 short/misaligned gate and down bank refusals,
  21 unsupported-mode refusals and five malformed-selection refusals.
  The tightest arena margin is 630,519,094 bytes. Driver residency is unmeasured.
- [All-window startup](startup97e.json): all three views through K0, K1a,
  K1b, K2, W0p, KD, W2m, WS, WSs, WS128x and WS128. KD exercises host and
  device-argument startup on CPU and matches the resident draft identity.
  K0 is a structural CPU shim; it does not execute a SYCL JIT. W0p runs the
  actual CPU handshake. Model startup uses real shapes, parser and allocation
  code while mocking payloads/backend; no model weights or GPU are read.
- [Protocol tests](evidence/python-tests104b.json): incomplete/reordered B
  grids, inexact output, changed acceptance, nonfinite rates, control losses,
  absent B results and wrong baseline/KD choices are refused.

No record chain is registered. Model exactness, unchanged acceptance, fresh
controls, speed transfer and lane-A confirmation remain device work.

## Proposals and reproduction

The two new files under `experiments/own-xpu-runtime/ops/lane-queue/` are
`proposed-p104b-B-grid.txt` and `proposed-p104b-A-confirm.txt`.
B runs production / gate-tile16 / gate-halfcache-tile16 / production.
A execution refuses before its first control until the complete exact B grid
has a winner that beats both fresh controls with unchanged per-prompt acceptance.
A planning may show both possible winners, explicitly pending B. These files
are proposals, not live queue entries.

Run CPU preparation with `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`: `prepare104b.py`, `build104b.py`, `cpu_gate.py`, `down_proof104b.py`,
`full_shape.py`, `startup97e.py`, `test104b.py`, `seal104b.py`, then
`queue_plan104b.py`. Compilers serialize through packet94's turn and yield to
whole-host record windows. The build ceiling is 200 MB; address space is 8 GiB.
Seals bind local selections and immutable source/object inputs, never parent
live selection, readiness or orchestration outputs. Preserve existing seals;
rebuilding after qualification requires a new evidence generation.

[Work note](../../../../notes/2026-10-18-own-runtime-packet104.md),
[retention and restoration](RETENTION.md), [handoff](HANDOFF.md).
