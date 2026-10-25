#!/usr/bin/env bash
# One controlled sc117-lan reload for an engine experiment (an application reload, never a host restart):
#   service-cycle.sh RECEIPT12 LABEL [VAR=VALUE ...]
# Points the unit at engine/receipts/RECEIPT12.json, sets the given variables in the user manager for this start
# only (unset afterwards are the caller's job: pass VAR= to clear), stops and starts the service once, waits for
# ready/failure (20 min deadline), prints the F32 oracle differences and the prefill gate, and, if
# OWNRT_DECODE_PROFILE was set, copies rank 0's device profile to profiles/LABEL-decode-device-rank0.jsonl.
set -euo pipefail
receipt=$1 label=$2; shift 2
lane=/home/steve/llm-optimizations/experiments/own-xpu-runtime
unit=$lane/gsq-rco-iq3s/serving/lan/sc117-lan.service
test -f "$lane/engine/receipts/$receipt.json"
sed -i -E "s#receipts/[0-9a-f]{12}\.json#receipts/$receipt.json#" "$unit"
cp "$unit" ~/.config/systemd/user/sc117-lan.service
systemctl --user daemon-reload
for kv in "$@"; do
  if [[ $kv == *= ]]; then systemctl --user unset-environment "${kv%=}"; else systemctl --user set-environment "$kv"; fi
done
systemctl --user stop sc117-lan
# Disk floors: the service refuses to start near them. Prune this campaign's superseded run directories (USB evidence:
# keep the newest; root control: keep the newest three; summaries live in the repo).
usb=/mnt/usb-models/own-xpu-runtime-results/sc117-lan; ctl=$HOME/own-xpu-runtime-results/sc117-lan
for d in $(ls -td "$usb"/run-* 2>/dev/null | tail -n +2); do rm -rf -- "$d"; done
for d in $(ls -td /dev/shm/sc117-lan-evidence/run-* 2>/dev/null | tail -n +2); do rm -rf -- "$d"; done
for d in $(ls -td "$ctl"/run-2026102[5-9]T* 2>/dev/null | tail -n +4); do rm -rf -- "$d"; done
start=$(date +%H:%M:%S)
systemctl --user start sc117-lan
end=$((SECONDS+1200))
# No pipe into grep -q here: under pipefail its early exit SIGPIPEs journalctl and the test never succeeds.
log=$(mktemp)
until journalctl --user -u sc117-lan --since "$start" --no-pager > "$log"; grep -q '"ready": true\|"passed": false' "$log" || [ $SECONDS -ge $end ]; do sleep 10; done
grep -v 'sudo\|pam_unix' "$log" | grep -o '"ready": true\|"passed": false.\{0,300\}\|decode_tok_s": [0-9.]*' | tail -3 || true
rm -f "$log"
binary=$(python3 -c "import json;print(json.load(open('$lane/engine/receipts/$receipt.json'))['binary_sha256'][:16])")
ev=$lane/gsq-rco-iq3s/serving/lan/evidence
python3 - "$ev" "$binary" <<'EOF'
import glob, json, sys
ev, b = sys.argv[1:]
f = glob.glob(f"{ev}/f32-state-{b}.json") + glob.glob(f"{ev}/f32-state-{b}-split*.json")
print('oracle differences:', json.load(open(f[0]))['differences'] if f else 'missing')
for g in sorted(glob.glob(f'{ev}/prefill-{b}-*.json')):
    d = json.load(open(g)); print('prefill gate', g.rsplit('/', 1)[1], 'passed', d['passed'], len(d['cases']))
EOF
run=$(ls -td /dev/shm/sc117-lan-evidence/run-* /mnt/usb-models/own-xpu-runtime-results/sc117-lan/run-* 2>/dev/null | head -1)
cat "$run"/rank*/failure.txt 2>/dev/null | head -c 400 || true
if systemctl --user show-environment | grep -q '^OWNRT_DECODE_PROFILE=2'; then
  for r in 0 1; do
    test -f "$run/rank$r/decode-device-profile.jsonl" || continue
    cp "$run/rank$r/decode-device-profile.jsonl" "$lane/gsq-rco-iq3s/service-speed/b-prefill/profiles/$label-decode-device-rank$r.jsonl"
    echo "profile: profiles/$label-decode-device-rank$r.jsonl"
  done
fi
