#!/usr/bin/env bash
# The decode experiments of ../notes/2026-09-19-speed-plan.md, in one session, with their gates.
#
#   E1  two-card tile identity probe        does a tile decode the same on both cards?
#   E2  fp16 autocast decode                how fast, how repeatable, how different?
#   and the build the two of them gate: the two-card tiled decode (lever 2).
#
# Every step decodes the SAME saved latents -- the 960x544 pruned run of 2026-09-19 -- so the only
# thing that changes between runs is the decode itself. That is what makes "reproduces the source
# run's video_tensor_sha256" a gate rather than a coincidence. Each run costs a decode (~1.5 min),
# not a clip (~4 min), because `--decode-only` skips encode, load and sample.
#
# PRECONDITIONS, none of which this script will create for you:
#
#   * THE FP8 SERVICE IS ALREADY STOPPED. Stopping and starting it is the user's decision
#     (AGENTS.md); this script never touches a service, a container or systemd beyond the
#     `systemd-run --user --scope` that smoke_h3.sh wraps each run in. It only CHECKS that port
#     18124 is quiet, and refuses if it is not.
#   * Both cards free, no uncleared device coredump, >= 11 GiB MemAvailable. smoke_h3.sh's
#     preflight checks all of that before every run and refuses on any of them.
#   * The source run's tensors.safetensors exists (see LATENTS_FROM below).
#
# Usage:
#
#   ./decode-experiments-session.sh                # the whole sequence
#   SKIP_PROBE=1 ./decode-experiments-session.sh   # E1 already passed, go straight to the decodes
#   LATENTS_FROM=... OUT_ROOT=... ./decode-experiments-session.sh
#
# DISK: every decode run is wrapped by smoke_h3.sh's run_gpu, which passes --save-tensors, so each
# one writes ~750 MB of tensors.safetensors (that is what compare-h3-runs.py reads for the
# frame-level E2 numbers). Five decode runs is ~4 GB; /mnt/fast-ai had 500 GB free on 2026-09-19.
#
# Everything lands in OUT_ROOT/<step name>/ as receipt.json (+ probe.json for E1), and the summary
# at the end prints the seconds and the verdicts. Read the summary; it is the output of the
# session, and the numbers in it are the answer to "is the two-card decode worth keeping".
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMOKE="${HERE}/smoke_h3.sh"
COMPARE="${HERE}/compare-h3-runs.py"
CPU_VENV="${CPU_VENV:-/mnt/fast-ai/venvs/minimax-h3-cpu}"
PY="${CPU_VENV}/bin/python"

# The pruned 960x544 / 124-frame / 8-NFE run of 2026-09-19: 79.964 s of decode.video, and the
# control every gate below is measured against.
SOURCE_RUN="${SOURCE_RUN:-/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/pruned-960x544/smoke-20260919T224948Z}"
LATENTS_FROM="${LATENTS_FROM:-${SOURCE_RUN}/tensors.safetensors}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/minimax-h3-decode-$(date -u +%Y%m%d)}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PROBE_TILES="${PROBE_TILES:-3}"

export OUT_ROOT LATENTS_FROM

E1="e1-probe-${STAMP}"
CONTROL="control-single-off-${STAMP}"
TWOCARD="two-card-off-${STAMP}"
FP16A="fp16-a-${STAMP}"
FP16B="fp16-b-${STAMP}"
BOTH="two-card-fp16-${STAMP}"

say() { printf '\n=== %s ===================================================================\n' "$1"; }

if [ ! -f "${LATENTS_FROM}" ]; then
  echo "missing ${LATENTS_FROM} -- point LATENTS_FROM at a run made with --save-tensors" >&2
  exit 2
fi
if ss -ltn 2>/dev/null | grep -qE '127\.0\.0\.1:18124|0\.0\.0\.0:18124'; then
  echo "port 18124 is still listening: the FP8 service holds both cards." >&2
  echo "Stopping it is the user's decision; this script does not touch services. Aborting." >&2
  exit 4
fi
mkdir -p "${OUT_ROOT}"

echo "source run   ${SOURCE_RUN}"
echo "latents      ${LATENTS_FROM}"
echo "output       ${OUT_ROOT}"
echo "source hashes:"
"${PY}" - "${SOURCE_RUN}/receipt.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
for k, v in r["hashes"].items():
    print(f"  {k:24s} {v}")
t = r["timings_seconds"]
print(f"  decode.video {t['decode.video']:.2f} s   total {sum(t.values()):.1f} s")
PY

# ---------------------------------------------------------------------------------------------
# 0. CPU: the tile loop still matches the diffusers source it was written against.
# ---------------------------------------------------------------------------------------------
say "step 0  the reimplemented tile loop vs upstream (CPU, no cards)"
"${PY}" "${HERE}/test_vae_tile_loop.py"

# ---------------------------------------------------------------------------------------------
# 1. E1: does one tile decode to the same bytes on both cards, twice?
# ---------------------------------------------------------------------------------------------
if [ "${SKIP_PROBE:-0}" != "1" ]; then
  say "step 1  E1 tile identity probe (${PROBE_TILES} tiles, both cards, twice)"
  RUN_NAME="${E1}" PROBE_TILES="${PROBE_TILES}" "${SMOKE}" probe-tiles
  "${PY}" - "${OUT_ROOT}/${E1}/probe.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
g = p["gates"]
print()
print("E1 gates:")
print(f"  1 identity across cards : {'PASS' if g['identity_across_cards'] else 'FAIL'}")
print(f"  2 repeatable per card   : {'PASS' if g['repeatable_per_card'] else 'FAIL'}")
for dev, row in g["vram"].items():
    print(f"  3 memory {dev:8s}       : allocated {row['allocated_bytes']/2**30:.3f} GiB "
          f"(gate: <= 12.5 GiB with both replicas up)")
print(f"  4 host VmHWM            : {g['host_peak_rss_bytes']/2**30:.3f} GiB "
      f"(gate: <= ~13.0 GiB, i.e. no more than +0.5 over the 12.467 of a normal run)")
if not (g["identity_across_cards"] and g["repeatable_per_card"]):
    print()
    print("STOP: a tile is not the same on both cards (or not repeatable). The two-card decode")
    print("cannot be called bit-identical; do not run the decode steps as an exactness gate --")
    print("they would have to be re-framed as an arithmetic change and measured, not asserted.")
    sys.exit(1)
PY
fi

# ---------------------------------------------------------------------------------------------
# 2. The control: decode-only, single card, no autocast. MUST reproduce the source run exactly --
#    if it does not, --decode-only itself is wrong and nothing after it means anything.
# ---------------------------------------------------------------------------------------------
say "step 2  control: --decode-only --vae-decode single --vae-autocast off"
RUN_NAME="${CONTROL}" VAE_DECODE=single VAE_AUTOCAST=off "${SMOKE}" decode-only
"${PY}" - "${OUT_ROOT}/${CONTROL}/receipt.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
src = r["decode_only"]["source_hashes"]
ok = all(r["hashes"][k] == src[k] for k in src)
print()
print(f"control decode.video {r['timings_seconds']['decode.video']:.2f} s")
for k in src:
    print(f"  {'MATCH   ' if r['hashes'][k] == src[k] else 'DIFFERS '} {k}")
if not ok:
    print("STOP: --decode-only does not reproduce the source run. Fix that before reading any gate.")
    sys.exit(1)
PY

# ---------------------------------------------------------------------------------------------
# 3. Lever 2: the two-card decode. The gate is exact equality with the control, nothing weaker.
# ---------------------------------------------------------------------------------------------
say "step 3  lever 2: --vae-decode two-card (gate: identical hashes)"
RUN_NAME="${TWOCARD}" VAE_DECODE=two-card VAE_AUTOCAST=off "${SMOKE}" decode-only
TWOCARD_OK=1
# A failed gate here does not stop the session: E2 below is an independent experiment, and the
# summary at the end is more useful with both halves measured than with one half missing.
"${PY}" - "${OUT_ROOT}/${TWOCARD}/receipt.json" "${OUT_ROOT}/${CONTROL}/receipt.json" <<'PY' || TWOCARD_OK=0
import json, sys
b, a = (json.load(open(p)) for p in sys.argv[1:3])
src = b["decode_only"]["source_hashes"]
same = all(b["hashes"][k] == src[k] for k in src)
tb, ta = b["timings_seconds"]["decode.video"], a["timings_seconds"]["decode.video"]
plan = b["decode_placement"]["video_decode_plan"]
print()
print(f"two-card decode.video {tb:.2f} s vs control {ta:.2f} s  ({ta/tb:.2f}x)")
print(f"  tiles {plan['tiles_total']} split {plan['tiles_per_card']} over {plan['cards']}, "
      f"blended on {plan['blend_card']}")
for k in src:
    print(f"  {'MATCH   ' if b['hashes'][k] == src[k] else 'DIFFERS '} {k}")
print("GATE: " + ("bit-identical -- lever 2 stands" if same else
                  "NOT identical -- lever 2 does not stand as written; read E1 again"))
sys.exit(0 if same else 1)
PY

[ "${TWOCARD_OK}" = "1" ] || echo "NOTE: lever 2's exactness gate FAILED. E2 below is independent of it and still runs."

# ---------------------------------------------------------------------------------------------
# 4. E2: fp16 autocast, twice. The repeat gate first (is it even deterministic?), then the time,
#    then the difference against the control -- as numbers, not as a verdict.
# ---------------------------------------------------------------------------------------------
say "step 4  E2: fp16 autocast, run A"
RUN_NAME="${FP16A}" VAE_DECODE=single VAE_AUTOCAST=fp16 "${SMOKE}" decode-only
say "step 5  E2: fp16 autocast, run B (the repeat gate)"
RUN_NAME="${FP16B}" VAE_DECODE=single VAE_AUTOCAST=fp16 "${SMOKE}" decode-only

FP16_OK=1
"${PY}" - "${OUT_ROOT}/${FP16A}/receipt.json" "${OUT_ROOT}/${FP16B}/receipt.json" <<'PY' || FP16_OK=0
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
same = all(a["hashes"][k] == b["hashes"][k] for k in a["hashes"])
print()
print(f"fp16 A decode.video {a['timings_seconds']['decode.video']:.2f} s, "
      f"B {b['timings_seconds']['decode.video']:.2f} s")
for k in a["hashes"]:
    print(f"  {'MATCH   ' if a['hashes'][k] == b['hashes'][k] else 'DIFFERS '} {k}")
print("REPEAT GATE: " + ("the two fp16 runs are bytewise equal" if same else
                         "the two fp16 runs DIFFER -- fp16 autocast is not deterministic here, "
                         "and the lever is dead whatever its speed"))
sys.exit(0 if same else 1)
PY

say "step 5b  E2 fidelity: fp16 vs the fp32 control (numbers only)"
"${PY}" "${COMPARE}" "${OUT_ROOT}/${CONTROL}" "${OUT_ROOT}/${FP16A}" --quiet \
  --json "${OUT_ROOT}/${FP16A}/vs-control.json" || true
echo "(a nonzero exit above only means the frames differ, which is the expected outcome of an A/B."
echo " Whether that difference is acceptable is the user's call, not this script's.)"

# ---------------------------------------------------------------------------------------------
# 6. Both levers at once -- a timing measurement, not a gate: fp16 is not exact, so the composed
#    path cannot be, and the only question here is how much time the two of them take together.
# ---------------------------------------------------------------------------------------------
if [ "${FP16_OK}" = "1" ]; then
  say "step 6  both levers: --vae-decode two-card --vae-autocast fp16 (timing)"
  RUN_NAME="${BOTH}" VAE_DECODE=two-card VAE_AUTOCAST=fp16 "${SMOKE}" decode-only
else
  echo
  echo "skipping step 6: the fp16 repeat gate failed, so composing it with lever 2 measures nothing."
fi

# ---------------------------------------------------------------------------------------------
say "summary"
"${PY}" - "${OUT_ROOT}" "${SOURCE_RUN}" "${E1}" "${CONTROL}" "${TWOCARD}" "${FP16A}" "${FP16B}" "${BOTH}" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2])
names = sys.argv[3:]
src_hashes = json.loads((source / "receipt.json").read_text())["hashes"]
print(f"{'run':<34} {'decode.video':>13} {'vs source video hash':>22}")
base = json.loads((source / "receipt.json").read_text())["timings_seconds"]["decode.video"]
print(f"{'source (single card, fp32)':<34} {base:>12.2f}s {'(the control)':>22}")
for name in names:
    receipt = root / name / "receipt.json"
    if not receipt.exists():
        continue
    r = json.loads(receipt.read_text())
    t = r["timings_seconds"].get("decode.video")
    verdict = ("identical" if r["hashes"]["video_tensor_sha256"] == src_hashes["video_tensor_sha256"]
               else "differs")
    place = r["decode_placement"]
    label = f"{name[:20]} [{place['vae_decode']}/{place['vae_autocast']}]"
    seconds = f"{t:>12.2f}s" if t else f"{'-':>13}"
    print(f"{label:<34} {seconds} {verdict:>22}" + (f"   {base / t:.2f}x" if t else ""))
probe = root / names[0] / "probe.json"
if probe.exists():
    g = json.loads(probe.read_text())["gates"]
    print(f"\nE1: identity {'PASS' if g['identity_across_cards'] else 'FAIL'}, "
          f"repeat {'PASS' if g['repeatable_per_card'] else 'FAIL'}, "
          f"host VmHWM {g['host_peak_rss_bytes']/2**30:.3f} GiB")
print(f"\nreceipts under {root}")
PY
