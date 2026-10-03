#!/usr/bin/env bash
# MiniMax-H3 gate session, 2026-10-03: the two open items from the 2026-09-21 ledger, in one GPU window.
#
#   gate A  persistent two-process decode server + audio overlap, EXACT (fp32 decode, base model, 50 NFE,
#           960x544, 2 clips). Pass = clip-00's four hashes MATCH the standalone baseline
#           repeat-20260920T023257Z-a bytewise. Expected decode.video ~40 s/clip (was 55.7 without the server).
#   gate B  the new clip-mode default (fp16 picture decode) on the same stack with the turbo LoRA, run twice.
#           Pass = both runs give the same four hashes per clip (repeatable), and latents + audio hashes MATCH
#           the fp32 turbo reference duet-20260920T074116Z (only the picture tensor may differ).
#
# It stops at the first failure or the first new GPU fault line and never retries on the same boot: the
# 2026-09-21 freeze came ten minutes into a rerun launched 90 s after a watchdog kill had left a copy-engine
# CAT error on card 03:00.0. Launch inside a user unit:
#   systemd-run --user --unit h3-gates-20261003 --collect --working-directory=$PWD bash scripts/gate-session-20261003.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/minimax-h3}"
SESSION="${SESSION:-/mnt/fast-ai/bench-results/minimax-h3-gates-20261003}"
PROMPTS="${PROMPTS:-${HERE}/../notes/h3-gate-prompts.txt}"
REF_EXACT="${REF_EXACT:-repeat-20260920T023257Z-a}"
REF_TURBO="${REF_TURBO:-duet-20260920T074116Z}"
CPU_PY="${CPU_PY:-/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python}"
mkdir -p "${SESSION}"; LOG="${SESSION}/session.log"
ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "${LOG}"; }
die() { say "STOP: $*"; exit 1; }
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup|hard LOCKUP'
fault_count() { journalctl -k -b --no-pager 2>/dev/null | grep -ciE "${FAULT_RE}"; }
F0="$(fault_count)"
[ "${F0}" -eq 0 ] || [ "${ALLOW_PRIOR_FAULTS:-0}" = "1" ] || die "this boot already has ${F0} GPU fault line(s); not starting MiniMax work on it"
pgrep -af 'run_h3_t2v|h3_duet|h3_vae_duet|h3_audio_proc' | grep -v "$$" && die "a previous MiniMax process is still alive"
[ -d "${OUT_ROOT}/${REF_EXACT}" ] && [ -d "${OUT_ROOT}/${REF_TURBO}/clip-00" ] || die "reference receipts missing under ${OUT_ROOT}"
[ -f "${PROMPTS}" ] || die "prompts file ${PROMPTS} missing"

run_duet() {   # run_duet <label> <env...>   -> sets RUN_NAME
  local label="$1"; shift
  say "---- ${label}: env $* ./smoke_h3.sh duet"
  env HEIGHT=544 WIDTH=960 VAE_DECODE=two-proc PROMPTS_FILE="${PROMPTS}" OUT_ROOT="${OUT_ROOT}" "$@" \
      bash "${HERE}/smoke_h3.sh" duet > "${SESSION}/${label}.out" 2>&1
  local rc=$?
  RUN_NAME="$(ls -dt "${OUT_ROOT}"/duet-2*/ 2>/dev/null | head -1 | xargs -r basename)"
  say "${label}: rc=${rc} run=${RUN_NAME}"
  grep -E 'MATCH|DIFFERS|REPEAT GATE|preflight: VAE_AUTOCAST|PREFLIGHT FAIL|WATCHDOG' "${SESSION}/${label}.out" | tee -a "${LOG}"
  local f; f="$(fault_count)"
  [ "${f}" -eq "${F0}" ] || { journalctl -k -b --no-pager -o short-iso | grep -iE "${FAULT_RE}" | tail -20 > "${SESSION}/FAULT-HALT.txt"; die "new GPU fault line(s) during ${label} (${F0} -> ${f}); halting, nothing reset"; }
  return "${rc}"
}
timings() {   # timings <run>
  "${CPU_PY}" - "${OUT_ROOT}/$1" <<'PY' | tee -a "${LOG}"
import json, sys, glob, os
run = sys.argv[1]
for r in sorted(glob.glob(run + "/clip-*/receipt.json")):
    d = json.load(open(r)); t = d["timings_seconds"]
    keep = {k: round(v, 1) for k, v in t.items() if k.startswith(("decode.video", "decode.audio", "sample"))}
    print(f"  {os.path.basename(os.path.dirname(r))}: steps={d.get('num_inference_steps')} "
          f"total={sum(t.values()):.1f}s {keep} decode_placement={json.dumps(d.get('decode_placement'))[:300]}")
log = run + ".log"
if os.path.exists(log):
    import re
    wall = [l for l in open(log, errors="replace") if re.search(r"wall|s/clip|total", l)]
    for l in wall[-4:]: print("  log:", l.strip()[:200])
PY
}

say "gate session start; kernel $(uname -r); MemAvailable $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB; fault lines this boot ${F0}"

# GATE_A=base (default): 50 NFE against the base-model baseline, ~25 min. GATE_A=turbo: the same exact fp32
# decode path with the turbo LoRA against the fp32 turbo reference, ~5 min. The first session ran `base`:
# clip-00 matched 4/4 (duet-20261003T224727Z) and then a worker crashed on a shared-file cleanup race, so
# the rerun after the fix used `turbo` to exercise the multi-job path without another 25 minutes.
if [ "${GATE_A:-base}" = "skip" ]; then
  say "gate A skipped (GATE_A=skip): it passed earlier in this session family; see the run-2 log"
  RUN_A="(skipped)"; REF_A="-"
elif [ "${GATE_A:-base}" = "turbo" ]; then
  run_duet gateA EXACT=1 BATCH_REF_0="${REF_TURBO}/clip-00" || die "gate A failed (see ${SESSION}/gateA.out)"
  REF_A="${REF_TURBO}/clip-00"
else
  run_duet gateA LORA= EXACT=1 BATCH_REF_0="${REF_EXACT}" || die "gate A failed (see ${SESSION}/gateA.out)"
  REF_A="${REF_EXACT}"
fi
[ "${GATE_A:-base}" = "skip" ] || { RUN_A="${RUN_NAME}"; timings "${RUN_A}"; }
[ "${GATE_A:-base}" = "skip" ] || say "GATE A PASS: persistent decode server + audio overlap is bytewise-exact vs ${REF_A} (run ${RUN_A})"

run_duet gateB1 || die "gate B run 1 failed (see ${SESSION}/gateB1.out)"
RUN_B1="${RUN_NAME}"; timings "${RUN_B1}"
run_duet gateB2 || die "gate B run 2 failed (see ${SESSION}/gateB2.out)"
RUN_B2="${RUN_NAME}"; timings "${RUN_B2}"

"${CPU_PY}" - "${OUT_ROOT}" "${RUN_B1}" "${RUN_B2}" "${REF_TURBO}" "${SESSION}/gateB.json" <<'PY' | tee -a "${LOG}"
import json, sys, os
root, b1, b2, ref, out = sys.argv[1:6]
keys = ["video_tensor_sha256", "audio_tensor_sha256", "video_latents_sha256", "audio_latents_sha256"]
H = lambda run, clip: json.load(open(os.path.join(root, run, clip, "receipt.json")))["hashes"]
res = {"repeat": {}, "vs_fp32_turbo_reference": {}}
ok = True
for clip in ("clip-00", "clip-01"):
    a, b = H(b1, clip), H(b2, clip)
    res["repeat"][clip] = {k: a[k] == b[k] for k in keys}
    ok &= all(res["repeat"][clip].values())
r, a = H(ref, "clip-00"), H(b1, "clip-00")
res["vs_fp32_turbo_reference"] = {k: a[k] == r[k] for k in keys}
untouched = all(res["vs_fp32_turbo_reference"][k] for k in keys[1:])
# The picture tensor MUST differ from fp32: on the first run it matched, which exposed that the
# two-proc tile workers ignored --autocast and the "fp16" run was an fp32 decode.
res["fp16_in_effect"] = not res["vs_fp32_turbo_reference"][keys[0]]
res["pass"] = bool(ok and untouched and res["fp16_in_effect"])
json.dump(res, open(out, "w"), indent=2)
print(json.dumps(res, indent=2))
print("GATE B", "PASS: fp16 default is repeatable; latents and audio are untouched (only the picture tensor differs from fp32)" if res["pass"] else "FAIL")
sys.exit(0 if res["pass"] else 1)
PY
[ "${PIPESTATUS[0]}" -eq 0 ] || die "gate B failed"
say "ALL GATES PASS. runs: A=${RUN_A} B1=${RUN_B1} B2=${RUN_B2}; session ${SESSION}"
