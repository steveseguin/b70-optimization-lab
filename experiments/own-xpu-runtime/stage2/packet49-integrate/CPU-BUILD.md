# Packet49 CPU build record

These are the preparation commands used for this packet. Do not rebuild or
change this sealed identity in place after device windows begin. A future
rebuild needs a separately recorded identity, fresh receipts and a new seal.
The oracle already running uses its own frozen binary and source bindings.

From this packet directory, every command below uses the same CPU wrapper:

```bash
cpu49() {
  nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$@"
}
cpu49 build.py prepare
cpu49 build.py gnu-host --jobs 1
cpu49 build.py device --jobs 1
cpu49 build.py asan --jobs 1
cpu49 p49_cpu_gate.py
cpu49 p49_plan_gate.py
cpu49 p49_snapshot_gate.py
cpu49 p49_python_gate.py
cpu49 p49_asan_gate.py
ASAN_OPTIONS=halt_on_error=1:detect_leaks=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
P49_SNAPSHOT_MODE=asan cpu49 p49_snapshot_gate.py
cpu49 p49_seal.py
cpu49 p49_seal.py --verify
```

The builds are serial. Compiling the device target does not execute it.
`prepare` only checks existing admitted input paths. It neither scans model
weights nor regenerates inherited tables. The retained packet45 metadata,
fixture inputs and exact RoPE table must exist at the recorded link targets;
missing inputs refuse. See [retention rules](ARTIFACT-RETENTION.md).

Mode receipts bind the source closure, actual compiler mirror, compile/link
flags and binary hashes. The six `p49-*-gates.json` receipts bind fresh CPU
fixtures, sparse plans, miniature state checks, Python admission and sanitizer
checks. `build-receipt.json` is the resulting scoped seal. It explicitly leaves
full-model oracle completion and device qualification pending. It does not
claim the historical packet45 compiler/test matrix was rerun in full.

The oracle's separate [build and unit record](oracle/README.md) governs the
only CPU jobs admitted to read model weights. It uses no device binary.
