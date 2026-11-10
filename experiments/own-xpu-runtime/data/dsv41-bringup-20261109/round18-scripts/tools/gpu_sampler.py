#!/usr/bin/env python3
# Read-only sampler of the six B70s' clock, throttle reasons, energy and package temperature (xe sysfs/hwmon).
# usage: gpu_sampler.py OUT [period_s]; stops on SIGTERM. One line per sample:
#   t_mono tile act_freq_MHz reasons energy_uJ temp_mC
import glob, os, signal, sys, time
out, per = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
order = ["0000:03:00.0", "0000:23:00.0", "0000:43:00.0", "0000:83:00.0", "0000:a3:00.0", "0000:e3:00.0"]  # tiles 0-5
cards = {}
for d in glob.glob("/sys/class/drm/card*/device"):
    pci = os.path.basename(os.path.realpath(d))
    if pci in order and os.path.isdir(d + "/tile0/gt0/freq0"):
        hw = sorted(glob.glob(d + "/hwmon/hwmon*"))[0]
        cards[order.index(pci)] = (d + "/tile0/gt0/freq0/act_freq", d + "/tile0/gt0/freq0/throttle/reasons",
                                   hw + "/energy1_input", hw + "/temp2_input")
stop = False
def h(*_):
    global stop
    stop = True
signal.signal(signal.SIGTERM, h)
def rd(p):
    try:
        with open(p) as f: return f.read().strip()
    except OSError: return "?"
with open(out, "w", buffering=1 << 16) as f:
    while not stop:
        t = time.monotonic()
        for tile in sorted(cards):
            a, r, e, tp = cards[tile]
            f.write(f"{t:.4f} {tile} {rd(a)} {rd(r).replace(' ', ',')} {rd(e)} {rd(tp)}\n")
        time.sleep(max(0.0, per - (time.monotonic() - t)))
