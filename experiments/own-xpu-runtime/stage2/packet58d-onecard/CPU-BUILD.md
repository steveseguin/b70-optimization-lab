# Packet58d CPU preparation

Run serially from the repository root. Builds compile device code but never
execute it. All executed native binaries are under `build/gnu-host` and use
CPU mocks only. No model payload is opened by the new allocation test.

```bash
P=experiments/own-xpu-runtime/stage2/packet58d-onecard
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" gnu-host < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" device < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/postload_allocation_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/test_engine_reset.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/python_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
```

Cache/operator and copy-queue gates are retained in `evidence/`; their receipts
pin the exact tested source. The production K1 CPU fixture is rerun against
the rebuilt host binary and must preserve the parent exact-output hash.
`postload_allocation_gate.py` also retains its allocation census and teardown.
Large expert/cache payloads are represented by opaque aligned addresses;
actual backing remains below 4 MiB. This is not a memory-fit benchmark.

The plan command and fresh card-0 output are in WINDOW.md. Missing or stale
allocation evidence now rejects planning before any command can be queued.
