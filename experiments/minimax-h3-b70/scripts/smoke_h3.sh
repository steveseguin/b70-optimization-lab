#!/usr/bin/env bash
# MiniMax-H3 two-B70 smoke: one clip, twice, same seed, bytewise hash comparison.
#
#   ./smoke_h3.sh dry        CPU only -- configs + safetensors headers, prints the split plan.
#                            Safe to run any time, touches no GPU and no service.
#   ./smoke_h3.sh repeat     the real gate: two GPU runs at the same seed, hashes compared.
#   ./smoke_h3.sh one        a single GPU run (for iterating before the gate).
#
# GPU work runs under `systemd-run --user --scope`, per the lab rule: a clip is tens of minutes
# and the interactive harness kills long jobs, while a transient scope survives the shell and
# gives the run its own cgroup memory bound (this host has 15 GiB of RAM and about 10 GiB of it
# is held by the FP8 service when that service is up).
#
# PRECONDITIONS for the GPU modes -- check them, this script does not:
#   1. Both B70s are free. They are NOT free while the FP8 service on 127.0.0.1:18124 is up.
#      Stopping it is a user decision (AGENTS.md); this script never touches a service.
#   2. /mnt/fast-ai/venvs/minimax-h3 exists with torch 2.14.0+xpu. Build it with setup-venv.sh
#      (it downloads; that needs explicit approval).
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="${HERE}/run_h3_t2v.py"

GPU_VENV="${GPU_VENV:-/mnt/fast-ai/venvs/minimax-h3}"
CPU_VENV="${CPU_VENV:-/mnt/fast-ai/venvs/minimax-h3-cpu}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/minimax-h3}"

# Start small. 124 frames is the smallest legal clip (17n+5, 5.167 s) and cannot be reduced, but
# the canvas can: 256x448 is ~1/26 of the packed sequence of the trained 768x1344 canvas, which
# is the difference between a first run that finishes and one that does not.
HEIGHT="${HEIGHT:-256}"
WIDTH="${WIDTH:-448}"
FRAMES="${FRAMES:-124}"
STEPS="${STEPS:-50}"          # ASSUMED -- no default is declared anywhere on this host.
SEED="${SEED:-42}"
PROMPT="${PROMPT:-A slow dolly-in on a rain-slicked city street at night; neon signs reflect in the puddles, a lone figure with an umbrella walks away from camera. Ambient rain, distant traffic, a low synth drone.}"

# Transient-scope bounds. NO memory ceiling (2026-09-18): the loader mmaps 27-40 GB of safetensors and
# the page cache it touches is charged to this cgroup; a MemoryHigh/MemoryMax below that working set
# (the 3G/4G "tripwire" of the first version) made the cgroup reclaim-thrash, which is exactly the
# memory PRESSURE systemd-oomd kills on: it killed the desktop and then the user manager on the
# 2026-09-17 23:09 EDT run. Global reclaim handles the page cache fine when nothing else heavy runs.
# PRECONDITION 3: nothing else memory-heavy on the host (no kernel build container, no FP8 service).
SCOPE_PROPS=(
  --property=MemorySwapMax=0
)

run_gpu() {   # run_gpu <run-name> [extra args...]
  local name="$1"; shift
  echo "=== GPU run ${name} ==============================================================="
  systemd-run --user --scope --quiet --collect \
    --unit="h3-${name}-$$" \
    "${SCOPE_PROPS[@]}" \
    "${GPU_VENV}/bin/python" "${RUNNER}" \
      --prompt "${PROMPT}" \
      --height "${HEIGHT}" --width "${WIDTH}" \
      --frames "${FRAMES}" --steps "${STEPS}" --seed "${SEED}" \
      --out-dir "${OUT_ROOT}" --run-name "${name}" \
      --save-tensors \
      "$@" \
      2>&1 | tee "${OUT_ROOT}/${name}.log"
}

compare_receipts() {   # compare_receipts <name-a> <name-b>
  local a="${OUT_ROOT}/$1/receipt.json" b="${OUT_ROOT}/$2/receipt.json"
  "${CPU_VENV}/bin/python" - "$a" "$b" <<'PY'
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
keys = ["video_tensor_sha256", "audio_tensor_sha256", "video_latents_sha256", "audio_latents_sha256"]
bad = 0
print(f"seed {a['seed']} vs {b['seed']}   steps {a['num_inference_steps']} vs {b['num_inference_steps']}")
for k in keys:
    same = a["hashes"][k] == b["hashes"][k]
    bad += 0 if same else 1
    print(f"  {'MATCH   ' if same else 'DIFFERS '} {k}  {a['hashes'][k][:16]}... / {b['hashes'][k][:16]}...")
print()
for name, run in (("run A", a), ("run B", b)):
    t = run["timings_seconds"]
    print(f"{name}: sample {t.get('sample', 0):.1f} s, total {sum(t.values()):.1f} s, "
          f"{run['seconds_per_second_of_video']:.1f} s of wall per s of video")
print()
print("REPEAT GATE: " + ("bytewise-equal" if not bad else f"NOT bytewise-equal ({bad}/{len(keys)} differ)"))
sys.exit(1 if bad else 0)
PY
}

mode="${1:-dry}"
case "${mode}" in
  dry)
    # No GPU, no diffusers, no transformers: configs and safetensors headers only.
    # `--verify-remap` additionally re-checks the Comfy -> diffusers key remap against the full
    # BF16 checkpoint (qkv split order, SwiGLU half order) by comparing tensor slices.
    exec "${CPU_VENV}/bin/python" "${RUNNER}" --dry-run --verify-remap \
      --height "${HEIGHT}" --width "${WIDTH}" --frames "${FRAMES}" --steps "${STEPS}"
    ;;

  one)
    mkdir -p "${OUT_ROOT}"
    run_gpu "smoke-$(date -u +%Y%m%dT%H%M%SZ)"
    ;;

  repeat)
    mkdir -p "${OUT_ROOT}"
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    run_gpu "repeat-${stamp}-a"
    run_gpu "repeat-${stamp}-b"
    echo
    echo "=== bytewise repeat check ========================================================"
    compare_receipts "repeat-${stamp}-a" "repeat-${stamp}-b"
    ;;

  *)
    echo "usage: $0 {dry|one|repeat}" >&2
    exit 2
    ;;
esac

# ---------------------------------------------------------------------------------------------
# Follow-ups, in order, once `repeat` passes at 256x448:
#
#   HEIGHT=320 WIDTH=576  ./smoke_h3.sh one
#   HEIGHT=544 WIDTH=960  ./smoke_h3.sh one
#   HEIGHT=768 WIDTH=1344 ./smoke_h3.sh one      # the trained canvas, ~37k video rows
#
# and the two arithmetic A/Bs the pruned form leaves open (same seed, compare hashes and frames):
#
#   ./smoke_h3.sh one -- --adaln-out-dtype fp32   # modulation kept in float32
#   ./smoke_h3.sh one -- --te-rotation none       # ConvRot control; expected to be garbage
#
# To hold the conditioning fixed while changing the denoiser, run once with --save-tensors, then
# feed the saved embedding back with --prompt-embeds.
# ---------------------------------------------------------------------------------------------
