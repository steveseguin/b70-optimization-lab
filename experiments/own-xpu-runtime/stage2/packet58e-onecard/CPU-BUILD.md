# Packet58e CPU preparation

Run serially from the repository root. Device code is compiled, never executed.
Full-shape setup uses only the host mock and 2,457,406 backing bytes.

```bash
P=experiments/own-xpu-runtime/stage2/packet58e-onecard
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" gnu-host < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" device < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/postload_allocation_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/test_engine_reset.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/admission_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/python_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
```

The full post-load gate executes Engine::initialize_cache with all 144 expert
banks and 48 routes, including both invalid-lifetime regression checks.
Admission tests use census extents without materializing payloads. Real file
locks and crash markers are exercised only under temporary directories.
Memory-floor crossing uses the real inherited supervisor with a mock child.

Cache/operator and copy-queue CPU receipts and the production K1 fixture are
also refreshed. Build gates pin source identities. See WINDOW.md for the actual
`--plan` invocation; it must pass the seal and creates no queue output.
