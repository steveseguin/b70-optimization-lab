# Packet 58b lean CPU build and checks

Run from the repository root. Device compilation never executes the binary.
All commands use nice 19 and cores 8–15/24–31. Run builds serially.

```bash
P=experiments/own-xpu-runtime/stage2/packet58b-onecard
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" device
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" gnu-host
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/copy_queue_cpu_gate.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/cpu_cache_gates.py" --output "$P/evidence/cache-cpu-gates.json"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/test_engine_reset.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/python_gates.py"
```

The changed-path fixture compiles the actual old/new constructor fragments
against a CPU mock of the documented v2 import contract. It proves the old
regular handle is rejected and the immediate handle is accepted, preserving
the dedicated engine, native in-order flag, async mode, context and ownership.
It loads no SYCL or Level Zero library. Native behavior still needs K1.

The existing cache/expert fixture runs once without sanitizers. The small
request-reset and Python receipt checks remain required by the inherited seal.
No sanitizer campaign, model payload, large pin or device launch is used.
Regenerate the host-only K1 golden with `build/gnu-host/p58-cache-fixtures
--iterations 1 --output <fresh-directory>`, copy its `k1.json` and case log,
and add `binary_sha256` of that host binary to `k1-cpu.json`. CPU timings
are not performance claims. Then run `seal.py` and `seal.py --verify` with
the same nice/taskset/python prefix. Build artifacts stay under 1.5 GB.

Final checks on October 17: both builds pass (173 source hashes each),
changed-path CPU mock passes, cache/expert fixtures pass, all 24 K1 placement
checks pass with the **unchanged packet58 CPU golden SHA-256**
`8ba3faa72a04985c65ea1b27d9cba2379a0fa91e00ac912334c4d86ab399c303`,
request resets match across 40 retained files, and all 44 Python checks pass.
Retained build: 148,319,943 bytes. No device binary was executed.
