# CPU preparation

Use nice 19, helper cores and null stdin for every command. The copied,
unchanged packet94 `compile_turn.py` serializes all compilers with the other
workers. It also waits out a whole-host hold. Compiler address space is bounded
to 8 GiB; the sparse full-size gate reserves virtual arena ranges without
populating model pages and separately checks RSS below 8 GiB. The build cap is
300 MB. No command below executes a device binary.

```bash
P=experiments/own-xpu-runtime/stage2/packet58j-onecard-port
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" gnu-host < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" device < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/byte_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/fullshape_submit_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/postload_allocation_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/k1_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/test_engine_reset.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/budget_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/cpu_cache_gates.py" --output "$P/evidence/cache-cpu-gates.json" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/copy_queue_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/python_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/admission_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/mask_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
```

The seal is over source, immutable selections, binaries, frozen oracle inputs
and finished CPU gate receipts. Live `ops`, queue state and other packets'
changing composition decisions are excluded. Proposed launch commands are in
[WINDOW.md](WINDOW.md). `build/input`, `build/fusion-fixtures` and generated
rope headers use the same frozen packet56 inputs as 58g. Rebuilding therefore
requires those existing local fixtures; this is a lab port, not a public recipe.
