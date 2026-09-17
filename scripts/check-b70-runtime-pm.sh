#!/bin/bash
# Refuse GPU work while any Intel Arc Pro B70 endpoint can runtime-suspend.
# Exit 0 only when every 8086:e223 endpoint reports power/control=on.
# See experiments/ltx25-b70/notes/2026-09-17-freeze-cause-runtime-pm-race.md.
rc=0
for dev in /sys/bus/pci/devices/0000:*; do
  [ "$(cat "$dev/vendor" 2>/dev/null)" = "0x8086" ] && [ "$(cat "$dev/device" 2>/dev/null)" = "0xe223" ] || continue
  c=$(cat "$dev/power/control"); s=$(cat "$dev/power/runtime_status")
  printf '%s control=%s status=%s\n' "$(basename "$dev")" "$c" "$s"
  [ "$c" = "on" ] || rc=1
done
[ $rc -eq 0 ] && echo "B70 runtime PM: all endpoints pinned on" || echo "B70 runtime PM: NOT SAFE - an endpoint can runtime-suspend; fix before launching (sudo sh -c 'for d in /sys/bus/pci/devices/0000:*; do [ \"\$(cat \$d/device)\" = 0xe223 ] && echo on > \$d/power/control; done')"
exit $rc
