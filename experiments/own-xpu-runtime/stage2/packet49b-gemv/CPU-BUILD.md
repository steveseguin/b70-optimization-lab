# Packet49b CPU build and seal

These are the completed preparation commands. Do not rebuild or alter the
sealed runtime identity in place; use a new packet for later changes.
Run from this packet directory when reconstructing that preparation. No command executes a device binary or reads
model weights. Builds are serial alongside the existing low-priority oracle.

```bash
cpu49b() {
  nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$@"
}
cpu49b storage_precheck.py
cpu49b build.py prepare
cpu49b build.py gnu-host --jobs 1
cpu49b build.py device --jobs 1
cpu49b build.py asan --jobs 1
cpu49b p49_cpu_gate.py
cpu49b p49_plan_gate.py
cpu49b p49_snapshot_gate.py
cpu49b p49_python_gate.py
cpu49b p49_asan_gate.py
cpu49b p49b_expert_gate.py
ASAN_OPTIONS=halt_on_error=1:detect_leaks=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
P49_SNAPSHOT_MODE=asan cpu49b p49_snapshot_gate.py
cpu49b p49_seal.py
cpu49b p49_seal.py --verify
```

Only these newly generated receipts establish CPU preparation. Inherited
historical helper tests/campaign scripts are not a claim that their whole
matrix was rerun. The oracle already has a frozen build and running unit:
use `shared_oracle.py --require-complete` only, never its run/build actions.
After sealing and starting device windows, do not edit this packet in place.
