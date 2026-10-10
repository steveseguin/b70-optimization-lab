#!/usr/bin/env bash
# Switch the Gemma 4 26B Q8 LAN service on the two-B70 host between recipes.
#   scripts/gemma4-26b-two-b70-recipe.sh throughput   # 8 x 4K per card, no draft: 16 concurrent, max total tokens/s (<=4K ctx)
#   scripts/gemma4-26b-two-b70-recipe.sh throughput-card1   # throughput shape on card 1 only (card 0 free for experiments)
#   scripts/gemma4-26b-two-b70-recipe.sh balanced     # 4 x 16K per card, draft 1: 8 concurrent, up to 16K context (default)
#   scripts/gemma4-26b-two-b70-recipe.sh single       # 1 x 16K per card, draft 3: fastest single session, 2 concurrent
#   scripts/gemma4-26b-two-b70-recipe.sh status
# Recipes live in deploy/systemd/two-b70-host/<name>-backends.conf and <name>-frontdoor.conf and are installed as the
# systemd drop-in two-b70-host.conf of gemma4-26b-q8-quad-backends.service / -frontdoor.service. Needs sudo.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
recipes_dir="$repo_dir/deploy/systemd/two-b70-host"
backend_unit=gemma4-26b-q8-quad-backends.service
frontdoor_unit=gemma4-26b-q8-quad-frontdoor.service
cmd=${1:-status}
# non-interactive use: export SUDO_ASKPASS=/path/to/helper (sudo -A); interactive sudo otherwise
sudo_cmd=(sudo); [[ -n ${SUDO_ASKPASS:-} ]] && sudo_cmd=(sudo -A)

status() {
  systemctl is-active "$backend_unit" "$frontdoor_unit" | paste -sd' ' | sed 's/^/units: /'
  grep -h '^# recipe:' "/etc/systemd/system/$backend_unit.d/two-b70-host.conf" 2>/dev/null || echo "recipe: (none installed)"
  for p in 19350 19351; do
    curl -fsS -m 2 "http://127.0.0.1:$p/props" 2>/dev/null |
      python3 -c 'import json,sys; d=json.load(sys.stdin); print("backend '"$p"': slots", d["total_slots"], "x", d["default_generation_settings"]["n_ctx"], "tokens")' ||
      echo "backend $p: not ready"
  done
  curl -fsS -m 2 http://127.0.0.1:8000/v1/frontdoor/status 2>/dev/null |
    python3 -c 'import json,sys; d=json.load(sys.stdin); f=d["frontdoor"]; print("frontdoor:", d["client_hints"]["runtime"].get("profile"), "active", f["active_generations"], "queued", f["queued_generations"])' ||
    echo "frontdoor: not ready"
}

case "$cmd" in
  status) status; exit 0 ;;
  throughput|throughput-card1|balanced|single) ;;
  *) echo "usage: $0 {throughput|throughput-card1|balanced|single|status}" >&2; exit 2 ;;
esac

b="$recipes_dir/$cmd-backends.conf"; f="$recipes_dir/$cmd-frontdoor.conf"
[[ -f "$b" && -f "$f" ]] || { echo "missing recipe files $b / $f" >&2; exit 2; }
"${sudo_cmd[@]}" install -D -m 0644 "$b" "/etc/systemd/system/$backend_unit.d/two-b70-host.conf"
"${sudo_cmd[@]}" install -D -m 0644 "$f" "/etc/systemd/system/$frontdoor_unit.d/two-b70-host.conf"
"${sudo_cmd[@]}" systemctl daemon-reload
"${sudo_cmd[@]}" systemctl enable "$backend_unit" "$frontdoor_unit" >/dev/null 2>&1 || true
"${sudo_cmd[@]}" systemctl restart "$frontdoor_unit"
"${sudo_cmd[@]}" systemctl restart "$backend_unit"
echo "[recipe] $cmd installed; waiting for both backends (model load ~30 s per card, staggered) ..."
ports=$(grep -o 'GPU_INDICES=[0-9 ]*' "$b" | grep -o '[0-9]' | sed 's/^/1935/' | paste -sd' ')
for i in $(seq 1 90); do
  ok=1
  for p in $ports; do
    h=$(curl -fsS -m 2 "http://127.0.0.1:$p/health" 2>/dev/null || true)
    [[ "$h" == *ok* ]] || ok=0
  done
  if [[ $ok == 1 ]]; then echo "[recipe] ready after ~$((i*5)) s"; status; exit 0; fi
  systemctl is-active --quiet "$backend_unit" || { echo "[recipe] backends unit died:"; journalctl -u "$backend_unit" -n 20 --no-pager -o cat | cut -c1-200; exit 1; }
  sleep 5
done
echo "[recipe] timed out waiting for health" >&2; status; exit 1
