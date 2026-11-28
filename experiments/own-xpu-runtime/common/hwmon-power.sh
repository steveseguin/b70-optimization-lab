#!/bin/bash
# hwmon-power.sh [interval_sec] [count]: read-only telemetry snapshot/logger for Intel xe GPUs.
# Prints timestamp, DRM card, PCI BDF, actual MHz, power cap (W), energy (J), and throttle flags.
# Modifies zero sysfs or power settings.
set -u
interval=${1:-0}
count=${2:-1}

sample_once() {
    local ts
    ts=$(date '+%FT%T')
    for drm in /sys/class/drm/card[0-9]*; do
        [ -d "$drm/device/driver" ] || continue
        drv=$(basename "$(readlink -f "$drm/device/driver")" 2>/dev/null || true)
        [ "$drv" = "xe" ] || continue
        cname=$(basename "$drm")
        bdf=$(basename "$(readlink -f "$drm/device")" 2>/dev/null || echo "?")
        freq=$(cat "$drm/device/tile0/gt0/freq0/act_freq" 2>/dev/null || echo "?")
        thr=""
        tdir="$drm/device/tile0/gt0/freq0/throttle"
        if [ -d "$tdir" ]; then
            for f in reason_pl1 reason_pl2 reason_pl4 reason_thermal reason_prochot; do
                [ "$(cat "$tdir/$f" 2>/dev/null || echo 0)" = "1" ] && thr="${thr}${f#reason_},"
            done
        fi
        hw=$(ls -d "$drm/device/hwmon"/hwmon* 2>/dev/null | head -1)
        ej="?"; pcap="?"
        if [ -n "$hw" ]; then
            eu=$(cat "$hw/energy1_input" 2>/dev/null || true)
            [ -n "$eu" ] && ej=$(awk -v e="$eu" 'BEGIN{printf "%.3f", e/1e6}')
            pu=$(cat "$hw/power1_cap" 2>/dev/null || true)
            [ -n "$pu" ] && pcap=$(awk -v p="$pu" 'BEGIN{printf "%.0f", p/1e6}')
        fi
        printf "%s  %-6s  %-12s  %4s MHz  cap=%3s W  energy=%10s J  throttle=%s\n" \
            "$ts" "$cname" "$bdf" "$freq" "$pcap" "$ej" "${thr:-none}"
    done
}

i=0
while :; do
    sample_once
    i=$((i + 1))
    [ "$count" -gt 0 ] && [ "$i" -ge "$count" ] && break
    [ "$interval" = "0" ] && break
    sleep "$interval"
done
