#!/usr/bin/env bash
set -euo pipefail

# Quiet baseline for the Supermicro M12SWA-TF in this 4x B70 system.
# Observed mapping:
#   - FANC is the only BMC-controlled fan that responded clearly to PWM.
#   - Optimal mode clamps zone 1 to 20%, where FANC sits around 840 RPM.
#   - zone 0 is left at the original 28% baseline to avoid reducing CPU-side
#     safety margin for fans that do not appear controllable by PWM.

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "set-supermicro-fan-quiet.sh must run as root" >&2
  exit 1
fi

IPMITOOL="${IPMITOOL:-/usr/bin/ipmitool}"
if [ ! -x "$IPMITOOL" ]; then
  echo "ipmitool not found at $IPMITOOL" >&2
  exit 1
fi

set_fan_mode() {
  local mode="$1"
  "$IPMITOOL" raw 0x30 0x45 0x01 "$mode" >/dev/null
}

set_zone_duty() {
  local zone="$1"
  local duty="$2"
  "$IPMITOOL" raw 0x30 0x70 0x66 0x01 "$zone" "$duty" >/dev/null
}

# Supermicro fan mode 0x02 is Optimal.
set_fan_mode 0x02

# BMC fan zones. Duties are hexadecimal percentages.
set_zone_duty 0 0x1c  # 28%, original CPU/system-side baseline
set_zone_duty 1 0x14  # 20%, lowest observed FANC setting in Optimal mode
set_zone_duty 2 0x14  # 20%, original baseline
set_zone_duty 3 0x14  # 20%, original baseline

echo "Applied Supermicro quiet fan baseline: mode=Optimal zone0=28% zone1=20% zone2=20% zone3=20%"
