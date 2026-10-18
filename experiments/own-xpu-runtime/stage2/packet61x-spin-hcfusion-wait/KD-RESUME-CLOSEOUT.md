# KD scratch repair and pinned early-window resume — 2026-10-17

<!-- experiment-closeout -->

The original chain passed K0, K1a, K1b, K2 and W0p, then failed KD's
host-reference retention with `KD host scratch outside packet`. Its STOP and
all original evidence remain untouched. No GPU, service, model payload read,
host-setting change or process termination was performed in this repair.
Device model qualification remains pending with the coordinator.

## Cause and change

`draft_window.archive_host_reference` compared the resolved scratch directory
against the source-local `P/build`. Packet61x's chain outputs instead live in
`/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build`.
The repair checks that admitted build root before starting the host owner and
again before retention. It rejects symlinks in scratch and hardlinks with
members outside the inspected tree. The sealed CPU and device binaries,
screen seal, arithmetic, selection and dispatch are unchanged.

`check_inputs.py` now inventories 286 write/scratch paths per packet, including
owner directories, dynamic fixture descendants, KD host reference, retention,
queue state and temporary files, driver caches, and per-prompt suite scratch.
Existing trees are inspected for escaping links. `--packet` audits packet61
and packet56w using their own modules and current KD boundary rules; neither
sibling packet was edited. Shared read-only model inputs keep their existing
input rules, separate from writable scratch.

The new `--resume-from` mode permits only the five explicitly pinned early
windows. It copies their 106 files (about 55 MB), preserves original receipt
bytes and writes `resume-manifest.json` in the fresh `device-cards01-b`.
`resume-pins.json` also pins the original queue state, prefix prerequisites and
STOP: 109 source files in total. The manifest binds the source, boot, old and
new wrapper seals, unchanged screen seal/binaries, dispatch and every copied
file. The old wrapper seal is retained under `evidence/`.

The new wrapper seal admits only that exact old early receipt identity.
Normal prerequisite validation still checks all receipt contents, retained
artifacts, execution scope and environment. Changed boot, original/current
seal, binary, dispatch, source/copy hash or inventory refuses admission.
KD, W2m, WS, WSs, WS128x and WS128 always run fresh. Early-phase resume,
existing selected outputs and a new STOP refuse; there is no retry mode.

## CPU evidence

- [Resume validation and storage admission](evidence/kd-resume-validation.json):
  all five real copied receipts pass the actual window prerequisite validator
  against the new wrapper identity. All six model output directories are absent.
- [Prepared manifest](evidence/kd-resume-manifest.json),
  [frozen source pins](resume-pins.json), and
  [extended input/scratch summaries](evidence/kd-scratch-summaries.json).
- Full resolved inventories: [61x](evidence/kd-scratch-p61x.json.gz),
  [61](evidence/kd-scratch-p61.json.gz),
  [56w](evidence/kd-scratch-p56w.json.gz).
- [CPU-only command plan](evidence/kd-resume-plan.txt): KD first, then exactly
  W2m, WS, WSs, WS128x, WS128; no early window launch.
- 50 focused tests and six subtests passed. Coverage includes changed boot,
  seals, binaries, dispatch, missing/modified receipts, modified import
  manifests, extra files, source/copy separation, symlink and hardlink escapes,
  KD external-build retention, queue boundaries and existing submission tests.
  The shell wrapper passes `bash -n`; `git diff --check` passes.

The extended check passes packet61x and packet56w. It deliberately **refuses
packet61**: that sibling still has the old KD boundary error. Its three errors
name `KD/host-reference`, `KD/host-reference.jsonl.gz` and its `.tmp` destination.
Repairing that sibling is outside this packet-only task.

Submission packaging was not extended to consume mixed wrapper-seal receipts;
a later exporter must preserve and validate the resume manifest before any
promotion. This repair grants only the coordinator chain admission, not a
speed result or public submission.

## Exact coordinator command

Run only inside the coordinator's admitted nice-0 user service on cores
0–3,16–19, with its existing approved library path and `OMP_NUM_THREADS=2`:

```bash
packet_path=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
head_packet=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
result_build=/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build
bash "$packet_path/coordinator_windows.sh" --phase all \
  --output-root "$result_build/device-cards01-b" \
  --resume-from "$result_build/device-cards01-a" --wait-oracle \
  --prefix-windows "$head_packet/evidence/head-k-a/window.json" \
                   "$head_packet/evidence/head-k-b/window.json"
```

The fresh folder is already prepared on CPU. The coordinator revalidates it
before launch. It never modifies `device-cards01-a` or imports its failed KD.
This command is invalid after a boot or pinned identity change.

CPU-only repeat checks, from the repository root:

```bash
packet_path=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
result_build=/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build
nice -n 19 taskset -c 8-15,24-31 python3 -B "$packet_path/check_inputs.py" \
  --window KD --resume-from "$result_build/device-cards01-a"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$packet_path/check_inputs.py" --packet packet61-spin-hcfusion
nice -n 19 taskset -c 8-15,24-31 python3 -B "$packet_path/check_inputs.py" --packet packet56w-chain
```

The packet61 audit is expected to return exit status 1. Do not override it.
Future layouts or new windows must extend the write inventory and its boundary
tests before device admission. A new model result still requires all fresh
model windows and the lane's ordinary quality/performance gates.
