# CPU-only build and gates

One compile at a time; all work stays nice 19 on cores 4–15,20–31. The helpers
refuse other affinity/priority, a 500 MB build budget violation, or writes that
would leave less than 18 GB free. The existing packet45 checked objects are
read-only and revalidated against their source closure and relink provenance.
Their relevant control bodies are checked against packet49c. New headers and
the benchmark use one mirrored type tree. No protected packet is rebuilt.

```bash
P=experiments/own-xpu-runtime/stage2/packet54-compute
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind intel-host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/check_controls.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/python_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cleanup.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/seal.py"
```

The device build compiles only; it never enumerates or opens a GPU. GNU and
Intel each run one bounded identity proof, comparing raw bytes and complete
finite output digest. Exceptional payloads remain exact against the control
within each compiler and are recorded separately. One GNU full-shape fixture pass checks every class/control/
eligible candidate through actual production submissions, plus one exceptional
mix comparison. Both norm proposals and FFN vectorization are closed by their retained actual-production
NaN mismatches; their isolated helper tests remain diagnostic only. Small proofs cover M2,
controls and exceptional cases. No sanitizer/full-model job or compiler
matrix is added in this lean round. Device E1/E2 still cover complete M1/M2.
The mocked Python suite validates refusal behavior, seals, fresh owners,
complete capture/event census, the PF_EXITING sensor and both decision bars.

Cleanup removes only this packet's regenerable object files after gates.
Keep final binaries, source mirrors, logs and receipts. Rebuilding after the
seal invalidates it; after device qualification begins, use a new packet.
