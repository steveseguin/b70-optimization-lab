# CPU-only build and qualification

Run these serially with nice19, affinity4–15,20–31 and Python-B:

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet53b-virtual
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind intel-host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/inspect_registers.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/python_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cleanup.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/seal.py"
```

Device and register steps compile only; no GPU process is run. The latter
uses icpx -fsycl device bitcode and offline ocloc BMG-G31. It records GRF and
spill metadata, not a runtime occupancy measurement. Original packet45 support
objects are hash checked and baseline relinked before reuse. Intel compiles
all new code; historical GNU support reuse is explicit in build receipts.

One fresh proof per host compiler, one full-shape host run for all four
classes, one standalone ASan/UBSan proof and mocked wrapper tests keep CPU
work bounded. OMP_THREAD_LIMIT=1 remains set. M2 exactness is checked in the
small proof and in full device windows; the CPU full-shape pass is M1 only.
