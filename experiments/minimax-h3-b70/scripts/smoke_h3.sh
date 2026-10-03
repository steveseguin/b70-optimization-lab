#!/usr/bin/env bash
# MiniMax-H3 two-B70 smoke: one clip, twice, same seed, bytewise hash comparison.
#
#   ./smoke_h3.sh dry        CPU only -- configs + safetensors headers, prints the split plan.
#                            Safe to run any time, touches no GPU and no service.
#   ./smoke_h3.sh repeat     the real gate: two GPU runs at the same seed, hashes compared.
#   ./smoke_h3.sh one        a single GPU run (for iterating before the gate).
#   ./smoke_h3.sh probe-tiles    experiment E1: decode the first PROBE_TILES tiles on BOTH cards,
#                            twice, and hash them. Needs LATENTS_FROM=<run>/tensors.safetensors.
#                            No denoiser, no clip: a few minutes, and it is the gate that decides
#                            whether the two-card decode may be called bit-identical.
#   ./smoke_h3.sh decode-only    decode a previous run's saved latents (LATENTS_FROM), skipping
#                            encode/load/sample -- ~1.5 min instead of ~4. VAE_DECODE=single|
#                            two-card and VAE_AUTOCAST=off|fp16|bf16 select the decode under test;
#                            with single + off the four hashes MUST reproduce the source run's.
#
# GPU work runs under `systemd-run --user --scope`, per the lab rule: a clip is tens of minutes
# and the interactive harness kills long jobs, while a transient scope survives the shell and
# gives the run its own cgroup memory bound (this host has 15 GiB of RAM and about 10 GiB of it
# is held by the FP8 service when that service is up).
#
# PRECONDITIONS for the GPU modes. Since 2026-09-18 this script CHECKS them and refuses to start
# if they do not hold (it still never changes anything -- it stops, it does not fix):
#   1. Both B70s are free. They are NOT free while the FP8 service on 127.0.0.1:18124 is up.
#      Stopping it is a user decision (AGENTS.md); this script never touches a service. Checked
#      as: port 18124 not listening, and no running container.
#   2. /mnt/fast-ai/venvs/minimax-h3 exists with torch 2.14.0+xpu. Build it with setup-venv.sh
#      (it downloads; that needs explicit approval).
#   3. At least MIN_HOST_AVAIL_MIB (11 GiB) of MemAvailable. Less than that means the FP8 service,
#      a kernel-build container or another lane is still resident -- which is the exact
#      combination that took the desktop out on 2026-09-17 23:09 EDT
#      (../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md).
#   4. Nothing else memory-heavy: any running container aborts the run.
#   5. No uncleared GPU fault: a card with `/sys/class/drm/card*/device/devcoredump/data` still
#      present has faulted and the driver has not been cleared. The script names the card and
#      refuses. Clearing it (or rebooting) is a user decision (AGENTS.md); this script never
#      writes to the devcoredump node.
#
# ENVIRONMENT this script pins for every GPU run, both proven on 2026-09-18 (session 10):
#
#   PYTORCH_ALLOC_CONF=expandable_segments:True
#       With both cards visible and this unset, the probe matrix measured about 1 GiB of HOST
#       memory consumed per GiB placed on xpu:0 (8 GiB -> +8125 MiB filled, +7993 MiB copied);
#       with it, +54 and +149 MiB. That mirroring is what killed session 9 (watchdog at 1.2 GiB
#       MemAvailable with the runner's own RSS at 0.7 GiB) and, with a 4G cgroup cap, the
#       desktop session on 2026-09-17. See scripts/xpu-host-memory-probe.py and
#       notes/2026-09-18-gpu-fault-first-light.md.
#
#   B70_H3_XFER=host
#       Cross-card tensor moves are staged through host RAM instead of copied device to device.
#       Session 10 faulted the copy engine (bcs) on 0000:03:00.0 at the first denoise step, the
#       instant hidden states first crossed the block-24 split. Hypothesis, not proof -- but the
#       host route is the control that tests it, and it is bit-exact either way.
#
# Every GPU run is wrapped in `mem-watchdog.sh` at a 2048 MiB floor on MemAvailable. The watchdog
# kills THIS job, in its own process group, before systemd-oomd (50 % pressure for 20 s on
# user@1000.service) starts killing the user's session. `set -m` below is what gives the job its
# own process group, which is what makes the watchdog's group kill precise.
#
set -euo pipefail
set -m          # job control: each background job gets its own process group (see the watchdog)

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="${HERE}/run_h3_t2v.py"

WATCHDOG="${HERE}/mem-watchdog.sh"
MIN_HOST_AVAIL_MIB="${MIN_HOST_AVAIL_MIB:-11264}"   # 11 GiB: below this, something big is resident
WATCHDOG_MIN_AVAIL_MIB="${WATCHDOG_MIN_AVAIL_MIB:-2048}"

# Proven on 2026-09-18; see the header. Overridable for a deliberate A/B, but not by accident.
export PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF:-expandable_segments:True}"
export B70_H3_XFER="${B70_H3_XFER:-host}"
export B70_H3_WRAPPER=1  # lets run_h3_t2v/h3_duet/h3_vae_duet/h3_audio_proc know the watchdog is on duty

# Which denoiser: `pruned` (BF16 weights, rank-8 AdaLN fit) or `int8` (full INT8 ConvRot,
# unpruned AdaLN). `pruned` stays the default until it has rendered a clip; the int8 build is
# the second first-light candidate and the control that isolates the pruned AdaLN
# re-parameterisation. See the README's fidelity table.
export B70_H3_DENOISER="${B70_H3_DENOISER:-pruned}"

GPU_VENV="${GPU_VENV:-/mnt/fast-ai/venvs/minimax-h3}"
CPU_VENV="${CPU_VENV:-/mnt/fast-ai/venvs/minimax-h3-cpu}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/minimax-h3}"

# Start small. 124 frames is the smallest legal clip (17n+5, 5.167 s) and cannot be reduced, but
# the canvas can: 256x448 is ~1/26 of the packed sequence of the trained 768x1344 canvas, which
# is the difference between a first run that finishes and one that does not.
HEIGHT="${HEIGHT:-256}"
WIDTH="${WIDTH:-448}"
FRAMES="${FRAMES:-124}"

# The 8-step turbo LoRA, and the step count that goes with it.
#
# `--steps` is the number of SIGMA GRID POINTS, terminal 0 included, so it drives `steps - 1`
# transformer evaluations (MiniMaxH3Scheduler.set_timesteps, scheduling_minimax_h3.py L133-136).
# Upstream always quotes NFE, so every published number gets +1 here:
#
#   base model, no LoRA   50 NFE -> STEPS=51   (the lightx2v/ModelTC reference runner)
#                         20 NFE -> STEPS=21   (the official ComfyUI template, turbo off)
#   8-step turbo LoRA      8 NFE -> STEPS=9    (ModelTC "FL2VA Turbo 8-step v1.0"; 4 NFE also works)
#
# A short step count is only legitimate WITH the turbo adapter, so the two defaults move together:
# the LoRA defaults to the turbo file when it is on disk, and STEPS follows it. Set LORA= (empty)
# to run the base model, and STEPS then defaults to 51. There is no cfg to set at any step count --
# the checkpoint is CFG-distilled and every step is one forward pass.
# See ../notes/2026-09-18-steps-and-lora.md.
TURBO_LORA="/mnt/fast-ai/llm-models/minimax-h3-comfy/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
if [ -z "${LORA+x}" ]; then
  if [ -f "${TURBO_LORA}" ]; then LORA="${TURBO_LORA}"; else LORA=""; fi
fi
if [ -n "${LORA}" ]; then STEPS="${STEPS:-9}"; else STEPS="${STEPS:-51}"; fi
LORA_ARGS=()
if [ -n "${LORA}" ]; then LORA_ARGS=(--lora "${LORA}"); fi
SEED="${SEED:-42}"

# The decode experiments of ../notes/2026-09-19-speed-plan.md (levers 1 and 2).
#   LATENTS_FROM   a previous run's tensors.safetensors (written by --save-tensors). Its receipt.json
#                  next to it carries the hashes a decode-only run is checked against.
#   VAE_DECODE     single (default, the bytewise-gated path) | two-card
#   VAE_AUTOCAST   off (the only exact setting) | fp16 | bf16.  DEFAULT SINCE 2026-10-03 (user decision):
#                  `fp16` for the clip-making modes (one, batch, duet) -- the 5x faster picture decode,
#                  repeatable but NOT bit-identical to fp32 (mean 0.03/255, worst pixel 7.5/255; latents and
#                  audio are untouched) -- and `off` for everything that is an exactness gate: repeat,
#                  decode-only, probe-tiles, and any batch/duet run given a BATCH_REF_<i> bytewise reference.
#   EXACT          EXACT=1 forces VAE_AUTOCAST=off everywhere (the lossless goal track; old receipts reproduce).
#                  An explicit VAE_AUTOCAST=... always wins over both.
#   PROBE_TILES    how many tiles the E1 probe decodes on each card (default 3)
#   RUN_NAME       name the output directory instead of timestamping it (probe-tiles / decode-only),
#                  which is what lets decode-experiments-session.sh find each run's receipt.
LATENTS_FROM="${LATENTS_FROM:-}"
VAE_DECODE="${VAE_DECODE:-single}"
if [ -z "${VAE_AUTOCAST:-}" ]; then
  case "${1:-dry}" in
    one|batch|duet)
      if [ "${EXACT:-0}" = "1" ] || [ -n "${BATCH_REF_0:-}" ]; then VAE_AUTOCAST=off; else VAE_AUTOCAST=fp16; fi ;;
    *) VAE_AUTOCAST=off ;;
  esac
fi
PROBE_TILES="${PROBE_TILES:-3}"
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

# Refuse to start a GPU run on a host that is not actually free. Checks only; changes nothing.
preflight() {
  local fail=0 avail containers

  if [ ! -x "${GPU_VENV}/bin/python" ]; then
    echo "PREFLIGHT FAIL: ${GPU_VENV}/bin/python is missing -- build it with ./setup-venv.sh" >&2
    fail=1
  fi
  if [ ! -x "${WATCHDOG}" ]; then
    echo "PREFLIGHT FAIL: ${WATCHDOG} is missing or not executable; it is not optional" >&2
    fail=1
  fi

  avail="$(awk '/^MemAvailable:/ {printf "%d", $2/1024; exit}' /proc/meminfo)"
  echo "preflight: MemAvailable ${avail} MiB (need >= ${MIN_HOST_AVAIL_MIB}), \
some avg10 $(awk '/^some/ {sub("avg10=","",$2); print $2; exit}' /proc/pressure/memory)"
  if [ "${avail}" -lt "${MIN_HOST_AVAIL_MIB}" ]; then
    echo "PREFLIGHT FAIL: only ${avail} MiB available; the FP8 service, a build container or" >&2
    echo "  another lane is still resident. One host-RAM-heavy job at a time on this host." >&2
    fail=1
  fi

  if ss -ltn 2>/dev/null | grep -qE '127\.0\.0\.1:18124|0\.0\.0\.0:18124'; then
    echo "PREFLIGHT FAIL: something is still listening on 18124 (the FP8 service holds both cards)." >&2
    fail=1
  fi

  # An uncleared device coredump means a card faulted and nothing has cleared it. Read only:
  # this loop never writes to the node (writing is what clears it, and that is the user's call).
  local dump card
  for dump in /sys/class/drm/card*/device/devcoredump/data; do
    [ -e "${dump}" ] || continue
    card="${dump#/sys/class/drm/}"; card="${card%%/*}"
    echo "PREFLIGHT FAIL: ${card} has an uncleared device coredump at ${dump}" >&2
    echo "  (failing device: $(readlink -f "$(dirname "${dump}")/failing_device" 2>/dev/null || echo unknown))" >&2
    echo "  A GPU fault has not been cleared. Clearing it or rebooting is the user's decision." >&2
    fail=1
  done

  if command -v docker >/dev/null 2>&1; then
    containers="$(docker ps -q 2>/dev/null | wc -l)"
    if [ "${containers}" -gt 0 ]; then
      echo "PREFLIGHT FAIL: ${containers} container(s) running:" >&2
      docker ps --format '  {{.ID}}  {{.Image}}  {{.Status}}  {{.Names}}' >&2 2>/dev/null || true
      fail=1
    else
      echo "preflight: no containers running"
    fi
  fi

  if [ "${fail}" -ne 0 ]; then
    echo >&2
    echo "Refusing to start. Nothing was stopped or changed -- stopping the FP8 service or a" >&2
    echo "container is a user decision (AGENTS.md)." >&2
    exit 4
  fi
  echo "preflight: PYTORCH_ALLOC_CONF=${PYTORCH_ALLOC_CONF}  B70_H3_XFER=${B70_H3_XFER}"
  echo "preflight: VAE_AUTOCAST=${VAE_AUTOCAST} ($([ "${VAE_AUTOCAST}" = off ] && echo "exact fp32 decode" || echo "fast decode, not bit-identical to fp32; EXACT=1 restores it"))"
  echo "preflight: OK"
}

run_gpu() {   # run_gpu <run-name> [extra args...]
  local name="$1"; shift
  local rc=0 job wd
  local prompt_args=(--prompt "${PROMPT}")
  if [ -n "${PROMPTS_FILE:-}" ]; then
    prompt_args=(--prompts-file "${PROMPTS_FILE}")
  fi
  echo "=== GPU run ${name} ==============================================================="

  # The job goes to the background so it becomes its own process group (set -m), which is what
  # lets the watchdog group-kill exactly this run -- systemd-run, python and tee -- and nothing else.
  (
    systemd-run --user --scope --quiet --collect \
      --unit="h3-${name}-$$" \
      "${SCOPE_PROPS[@]}" \
      env PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF}" B70_H3_XFER="${B70_H3_XFER}" \
          B70_H3_DENOISER="${B70_H3_DENOISER}" B70_H3_WRAPPER=1 \
      "${GPU_VENV}/bin/python" "${RUNNER}" \
        "${prompt_args[@]}" \
        --height "${HEIGHT}" --width "${WIDTH}" \
        --frames "${FRAMES}" --steps "${STEPS}" --seed "${SEED}" \
        "${LORA_ARGS[@]}" \
        --vae-decode "${VAE_DECODE}" --vae-autocast "${VAE_AUTOCAST}" \
        --out-dir "${OUT_ROOT}" --run-name "${name}" \
        --save-tensors \
        "$@" \
        2>&1 | tee "${OUT_ROOT}/${name}.log"
  ) &
  job=$!

  "${WATCHDOG}" "${job}" "${WATCHDOG_MIN_AVAIL_MIB}" "${OUT_ROOT}/${name}.watchdog.log" &
  wd=$!

  wait "${job}" || rc=$?
  # The watchdog ends itself within one poll of the job disappearing, and logs its summary line
  # (poll count, low MemAvailable, peak pressure) on the way out -- so wait for it, do not kill it.
  wait "${wd}" 2>/dev/null || true

  if [ "${rc}" -ne 0 ]; then
    echo "run ${name} exited ${rc}" >&2
    if grep -q "KILL pid=" "${OUT_ROOT}/${name}.watchdog.log" 2>/dev/null; then
      echo "THE WATCHDOG KILLED THIS RUN -- host memory, not the GPU. See ${OUT_ROOT}/${name}.watchdog.log" >&2
    fi
  fi
  return "${rc}"
}

require_latents() {
  if [ -z "${LATENTS_FROM}" ]; then
    echo "set LATENTS_FROM=<run-dir>/tensors.safetensors (a run made with --save-tensors)" >&2
    exit 2
  fi
  if [ ! -f "${LATENTS_FROM}" ]; then
    echo "LATENTS_FROM=${LATENTS_FROM} does not exist" >&2
    exit 2
  fi
  echo "latents: ${LATENTS_FROM}"
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
    # BF16 checkpoint (qkv split order, SwiGLU half order) by comparing tensor slices, and on the
    # int8 path re-checks that dequantizing each sampled Linear reproduces `W R` to within the
    # int8 rounding floor. Both denoisers are checked, because both have to stay loadable.
    rc=0
    for d in pruned int8; do
      echo "################ dry run: --denoiser ${d} ################"
      "${CPU_VENV}/bin/python" "${RUNNER}" --dry-run --verify-remap --denoiser "${d}" \
        --height "${HEIGHT}" --width "${WIDTH}" --frames "${FRAMES}" --steps "${STEPS}" \
        "${LORA_ARGS[@]}" || rc=1
      echo
    done
    # The per-phase VRAM budget, for the smoke canvas and for the next canvas up. A dry run cannot
    # measure VRAM -- this is arithmetic over the split plan and the VAE headers, with a stated
    # bound for the decode activations (run_h3_t2v.py::plan_memory). It exists because the
    # 2026-09-19 control run denoised fault-free and then OOMed in `decode.video` with the denoiser
    # still resident: 18.797 + 9.700 + 0.564 + ~2 GiB on one 31.89 GiB card.
    echo "################ per-phase VRAM plan ################"
    for canvas in "${HEIGHT}x${WIDTH}" "544x960"; do
      h="${canvas%x*}"; w="${canvas#*x}"
      echo "---- ${h}x${w}x${FRAMES} ----"
      "${CPU_VENV}/bin/python" "${RUNNER}" --dry-run --plan-memory --denoiser "${B70_H3_DENOISER}" \
        --height "${h}" --width "${w}" --frames "${FRAMES}" --steps "${STEPS}" \
        "${LORA_ARGS[@]}" 2>/dev/null | sed -n '/^memory plan/,/^$/p' || rc=1
    done
    echo
    echo "################ INT8 ConvRot dequant unit test ################"
    "${CPU_VENV}/bin/python" "${HERE}/test_convrot_linear.py" || rc=1
    echo
    echo "################ LoRA merge / runtime-term unit test ################"
    "${CPU_VENV}/bin/python" "${HERE}/test_lora.py" || rc=1
    echo
    echo "################ pread tensor-reader unit test ################"
    "${CPU_VENV}/bin/python" "${HERE}/test_tensor_reader.py" || rc=1
    echo
    # The two-card decode reimplements the VAE's chunk and tile loops in the runner. This runs the
    # reimplementation against upstream's own methods (lifted out of the diffusers source with
    # `ast`) on a stub autoencoder, and fails if the diffusers file has moved under it.
    echo "################ two-card VAE tile-loop unit test ################"
    "${CPU_VENV}/bin/python" "${HERE}/test_vae_tile_loop.py" || rc=1
    exit "${rc}"
    ;;

  one)
    mkdir -p "${OUT_ROOT}"
    preflight
    run_gpu "smoke-$(date -u +%Y%m%dT%H%M%SZ)"
    ;;

  probe-tiles)
    # Experiment E1. Same preflight and the same watchdog as every other GPU mode: it loads the
    # 9.7 GiB video VAE on BOTH cards, which is the memory question the probe is measuring.
    require_latents
    mkdir -p "${OUT_ROOT}"
    preflight
    run_gpu "${RUN_NAME:-probe-tiles-$(date -u +%Y%m%dT%H%M%SZ)}" \
      --probe-tile-identity "${PROBE_TILES}" \
      --latents-from "${LATENTS_FROM}" \
      --vae-autocast "${VAE_AUTOCAST}"
    ;;

  decode-only)
    # Decode a previous run's latents. `--height/--width/--frames` are ignored (the canvas comes
    # from the latents); the run name records what is under test so the directory is self-describing.
    require_latents
    mkdir -p "${OUT_ROOT}"
    preflight
    run_gpu "${RUN_NAME:-decode-${VAE_DECODE}-${VAE_AUTOCAST}-$(date -u +%Y%m%dT%H%M%SZ)}" \
      --decode-only \
      --latents-from "${LATENTS_FROM}" \
      --vae-decode "${VAE_DECODE}" \
      --vae-autocast "${VAE_AUTOCAST}"
    ;;

  batch)
    # Lever 4 gate: one batch run over PROMPTS_FILE, then every prompt that also has a
    # standalone reference receipt (BATCH_REF_<i>=<run-dir>) is compared bytewise against it.
    # The first prompt SHOULD be the default prompt so it can be gated against a `repeat` run.
    if [ -z "${PROMPTS_FILE:-}" ]; then
      echo "batch needs PROMPTS_FILE=<path> (one prompt per line, or a JSON list)" >&2
      exit 2
    fi
    mkdir -p "${OUT_ROOT}"
    preflight
    name="batch-$(date -u +%Y%m%dT%H%M%SZ)"
    run_gpu "${name}"
    rc=0
    i=0
    while true; do
      ref_var="BATCH_REF_${i}"
      ref="${!ref_var:-}"
      [ -z "${ref}" ] && break
      echo
      echo "=== batch clip-${i} vs standalone ${ref} ================================================"
      compare_receipts "${name}/clip-$(printf %02d "${i}")" "${ref}" || rc=1
      i=$((i + 1))
    done
    [ "${i}" -gt 0 ] || echo "batch: no BATCH_REF_<i> references set; run only, no bytewise gate"
    [ "${rc}" -eq 0 ] || exit 1
    ;;

  duet)
    # Lever 5 gate: one duet run (two processes, one card each, clips staggered through the
    # block-24 split) over PROMPTS_FILE, then BATCH_REF_<i> bytewise comparisons exactly as
    # `batch`.  The first prompt SHOULD be the default prompt, gated against a `repeat` run.
    if [ -z "${PROMPTS_FILE:-}" ]; then
      echo "duet needs PROMPTS_FILE=<path> (at least 2 prompts)" >&2
      exit 2
    fi
    mkdir -p "${OUT_ROOT}"
    preflight
    name="duet-$(date -u +%Y%m%dT%H%M%SZ)"
    SPLIT_INDEX="${SPLIT_INDEX:-25}"  # equal-FLOP blocks: compute balance beats byte balance (426.5 vs 440.5 s/clip, exact)
    rc=0
    (
      systemd-run --user --scope --quiet --collect --unit="h3-${name}-$$" "${SCOPE_PROPS[@]}" \
        env PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF}" B70_H3_XFER="${B70_H3_XFER}" \
            B70_H3_WRAPPER=1 \
            B70_H3_DENOISER=pruned \
        "${GPU_VENV}/bin/python" "${HERE}/h3_duet.py" \
          --prompts-file "${PROMPTS_FILE}" \
          --height "${HEIGHT}" --width "${WIDTH}" \
          --frames "${FRAMES}" --steps "${STEPS}" --seed "${SEED}" \
          --vae-decode "${VAE_DECODE}" --vae-autocast "${VAE_AUTOCAST}" \
          ${SPLIT_INDEX:+--split-index "${SPLIT_INDEX}"} \
          --out-dir "${OUT_ROOT}" --run-name "${name}" \
          2>&1 | tee "${OUT_ROOT}/${name}.log"
    ) &
    job=$!
    "${WATCHDOG}" "${job}" "${WATCHDOG_MIN_AVAIL_MIB}" "${OUT_ROOT}/${name}.watchdog.log" &
    wd=$!
    wait "${job}" || rc=$?
    wait "${wd}" 2>/dev/null || true
    [ "${rc}" -eq 0 ] || { echo "duet run exited ${rc}" >&2; exit "${rc}"; }
    i=0
    while true; do
      ref_var="BATCH_REF_${i}"
      ref="${!ref_var:-}"
      [ -z "${ref}" ] && break
      echo
      echo "=== duet clip-${i} vs standalone ${ref} ================================================"
      compare_receipts "${name}/clip-$(printf %02d "${i}")" "${ref}" || rc=1
      i=$((i + 1))
    done
    [ "${i}" -gt 0 ] || echo "duet: no BATCH_REF_<i> references set; run only, no bytewise gate"
    [ "${rc}" -eq 0 ] || exit 1
    ;;

  repeat)
    mkdir -p "${OUT_ROOT}"
    preflight
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    run_gpu "repeat-${stamp}-a"
    run_gpu "repeat-${stamp}-b"
    echo
    echo "=== bytewise repeat check ========================================================"
    compare_receipts "repeat-${stamp}-a" "repeat-${stamp}-b"
    ;;

  *)
    echo "usage: $0 {dry|one|repeat|batch|duet|probe-tiles|decode-only}" >&2
    echo "  probe-tiles / decode-only need LATENTS_FROM=<run-dir>/tensors.safetensors" >&2
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
# and then the other denoiser, which is the control that isolates the pruned AdaLN fit from
# everything else -- same canvas, same seed, same conditioning, one difference:
#
#   B70_H3_DENOISER=int8 ./smoke_h3.sh one
#   B70_H3_DENOISER=int8 ./smoke_h3.sh one -- --denoiser-rotation none   # ConvRot control
#
# To hold the conditioning fixed while changing the denoiser, run once with --save-tensors, then
# feed the saved embedding back with --prompt-embeds.
# ---------------------------------------------------------------------------------------------
