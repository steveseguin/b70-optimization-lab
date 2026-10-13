# Packet45 coordinator windows

CPU preparation never runs these commands. They require the final packet45 seal and its own complete gates. Missing or pending gates refuse admission. No packet40/44 seal, old build hash or long-suite amendment authorizes this merged binary.

Run inside the coordinator's admitted systemd user unit, with its existing CPU affinity. K windows require nice19 and idle I/O. As in packet44, W windows require a nice0 coordinator parent; the CPU preparation agent remains nice19 throughout. Only supply existing LD_LIBRARY_PATH; its bytes are preserved and the wrapper supplies OMP_NUM_THREADS=2. No device-selector/cache/precision variables. `--card N` names the first card of the adjacent pair. Each context and draft placement needs its own fresh chain. No automatic retries.

The complete command sequence is below, also retained as [coordinator_windows.sh](coordinator_windows.sh). From repository root, the helper takes `CARD CONTEXT DRAFT_RANK [MANIFEST] [OUTPUT]`. Context is 256, 4096 or 32768; draft rank is 0 or 1. The default suite manifest generates 128 tokens. The 64-token manifest is `experiments/own-xpu-runtime/stage2/suite-inputs-20261012/suite-manifest.json`; the 32-token long manifest is `experiments/own-xpu-runtime/stage2/long-inputs-20261012/suite-manifest.json` (requires context at least 4096).

The immutable manifest input lengths are checked on CPU:

| Manifest cap | Prompt tokens | Prompts | Valid packet capacities |
|---:|---:|---:|---|
| 64 | 60–90 | 12 | 256, 4096, 32768 |
| 128 | 60–90 | 12 | 256, 4096, 32768 |
| 32, long | 598 and 2271 | 2 | 4096, 32768 |

A long-manifest attempt at capacity 256 must refuse before any launcher starts.

```bash
#!/usr/bin/env bash
# Coordinator only, from repository root inside the admitted nice-0 systemd user unit.
set -euo pipefail
packet45=experiments/own-xpu-runtime/stage2/packet45-merged3
packet45_card=${1:?first card of adjacent pair required}
packet45_context=${2:?context 256,4096,32768 required}
packet45_draft_rank=${3:-0}
packet45_suite=${4:-experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap 128/suite-manifest.json}
packet45_out="${5:-$packet45/build/c${packet45_context}-dr${packet45_draft_rank}}"
packet45_input="$packet45/build/input"
packet45_oracle=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
packet45_k=(nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet45/window.py" --authorized-device-window --card "$packet45_card" --context "$packet45_context" --draft-rank "$packet45_draft_rank")
packet45_w=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet45/window.py" --authorized-device-window --card "$packet45_card" --context "$packet45_context" --draft-rank "$packet45_draft_rank")
"${packet45_k[@]}" --window K0 --output "$packet45_out/K0"
"${packet45_k[@]}" --window K1a --output "$packet45_out/K1a" --k0 "$packet45_out/K0/window.json" --dispatch "$packet45/dispatch-p45.json"
"${packet45_k[@]}" --window K1b --output "$packet45_out/K1b" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --dispatch "$packet45/dispatch-p45.json"
"${packet45_k[@]}" --window K2 --output "$packet45_out/K2" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --dispatch "$packet45/dispatch-p45.json" --seconds 14400
"${packet45_w[@]}" --window W0p --output "$packet45_out/W0p" --k0 "$packet45_out/K0/window.json"
"${packet45_k[@]}" --window KD --output "$packet45_out/KD" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --input "$packet45_input"
"${packet45_w[@]}" --window W2m --output "$packet45_out/W2m" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --w0p "$packet45_out/W0p/window.json" --kd "$packet45_out/KD/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --input "$packet45_input" --oracle "$packet45_oracle" --controller native --retain-steps 1-8
"${packet45_w[@]}" --window WS --output "$packet45_out/WS" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --w0p "$packet45_out/W0p/window.json" --kd "$packet45_out/KD/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet45_suite" --controller native --repeat 1 --retain-steps 1-8
"${packet45_w[@]}" --window WSs --output "$packet45_out/WSs" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --w0p "$packet45_out/W0p/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet45_suite" --controller native --repeat 1 --retain-steps 1-8
```

The chain is K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs. Context, draft placement, cards, boot, exact binary/source seal, environment and child artifacts bind every prerequisite. The helper's first chain uses fresh output paths; run additional manifests with new paths rather than reusing an existing directory.

These retained-fixture W commands qualify exactness and report instrumented timing. Packet40 speed aliases remain available: `W2m-speed` needs a matching `W2m-exact`; `WS64` needs `WS64x`; `WS128` needs `WS128x`; `WSs --retain-steps none` needs a matching retained WSs. Every speed companion must use the same boot, context, draft rank, controller, prompt overlap, dispatch, manifest and cap. A speed window never silently omits its companion.

Suite cap comes from the manifest, independent of allocation capacity. Every emitted token is compared against its immutable oracle; retention controls layer comparisons. At cap 128 the submission rate is 99 intervals between events 1 and 100; cap 32 cannot provide that rate. The 512-token publication gate remains false. Missing actual long midprompt records are reported explicitly; oracle bindings remain checked.

K2 records a capacity-specific expected duration and refuses an expected duration plus 17 seconds above one quarter of its watchdog. The command above uses the 14400-second watchdog conservatively; DEADLINES.md records computed lower bounds. No running window is shortened merely because its estimate was optimistic.

CPU mocked success/failure orchestration and all three capacities/both draft placements are recorded in wrapper-merge-tests.json and context-window-gates.json. No GPU speed, output parity or residency is inferred from those rehearsals. Physical owner census, timing and fresh-owner exactness remain coordinator work.

A new GPU fault or failed owner after device contact preserves evidence and stops the chain. Storage/format/coordinator errors do not create a boot-fault latch. Compression errors retain raw evidence and the completed verdict.

KD runs isolated captured draft arithmetic on the selected physical draft card. Its capture harness retains logical rank1/shared-head setup; rank0 duplicate-head ownership and reverse handoff require W2m/WS on the actual two-rank runtime. A KD pass alone does not certify that protocol.
