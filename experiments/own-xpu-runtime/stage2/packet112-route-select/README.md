# Packet112: exact top-10 routing

Standalone route micro, CPU prepared. No device measurement or runtime
integration is claimed. [Full work note and proof](../../../../notes/2026-10-18-own-runtime-packet112.md).

Control is the current **route-fast** kernel, not legacy all-pairs routing.
The candidate preserves its arithmetic and merges exact subgroup top-16 lists
instead of fully sorting 512 probabilities. See [source audit](evidence/source-audit.json)
and [candidate](p112_route.hpp).

Two fresh lane-B processes must each pass 2,048 byte cases and reduce median
event time to <=50% of control, overall and within each order/layer stratum.
Otherwise this arm closes without integration. The proposal is
[proposed-p112-micro-B.txt](../../ops/lane-queue/proposed-p112-micro-B.txt).
Expected duration: 60 seconds per owner; watchdog: 1,200 seconds each.
Only the coordinator runs devices. No live queue was edited.

The sixteen original inputs are from packet107's unchanged CPU layer harness,
using synthetic weights. Packet100b's saved selected IDs are not router logits.
NaN/Inf rows are rejected; every output is checked unchanged. Production's
partially written rejected-row maxima are unspecified, as explained in the note.

CPU reproduction from the repository root, each command prefixed with
`nice -n 19 taskset -c 8-15,24-31`, stdin `/dev/null`:

```sh
P=experiments/own-xpu-runtime/stage2/packet112-route-select
python3 -B "$P/capture_inputs.py"
python3 -B "$P/build_micro.py" --mode device
python3 -B "$P/build_micro.py" --mode gnu
python3 -B "$P/build_micro.py" --mode intel
python3 -B "$P/cpu_gate.py"
python3 -B -m unittest discover -s "$P" -p test_gate.py
python3 -B "$P/seal.py"
python3 -B "$P/run_micro.py" --lane B --owner 1 --plan
python3 -B "$P/run_micro.py" --lane B --owner 2 --plan
```

Capture and CPU logs require fresh destinations; preserve existing receipts.
Builds take packet94's compiler turn, one compiler at a time, under 8 GiB.
`build/` is ignored and stays below 200 MB. The retained build is about 10 MB.
The capture executable uses pinned, host-local packet97 objects; its generated
copy uses packet107 checked headers. This is a lab experiment, not a portable
published recipe. The standalone micro recompiles its actual header closure.

After both clean device receipts, `python3 -B "$P/qualification.py"` recomputes
the hash-bound gate. Integration is conditional on that result and p103x's fix.
