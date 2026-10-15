# SPEED7 CPU evidence retention

These files were produced on CPU only. The device mode was compiled and linked,
never executed. The baseline receipt and compressed baseline header bind SPEED6.
No model weight bytes were read by the plan/copy probes.

`plan-sweep.json` and `../../speed7-plan-gates.json` exceed 1 MiB because they
retain all 144 production-geometry rows, writer bounds, spare-bank proofs,
selected small-FFN groups and sparse owner-check results. The first is the
row-only export; the second is the seal-consumed receipt with source hashes.
`mini-cases.json` retains every miniature target/draft state signature and
raw timing metadata. Its referenced `../scratch-*.jsonl.gz` archives retain
exact logs and file hashes before the temporary case directories were removed.
These are qualification evidence, not caches. Their row-level detail lets the
seal reject omitted or altered cases without rerunning model arithmetic.

Recreate the production proof with `python3 -B speed7_plan_gate.py` and
`speed7_copy_gate.py` from the packet directory, under the owner's CPU resource
limits. `after.cpp.gz` and `copy-probe.cpp.gz` retain the exact extracted source;
`after.gz` retains the small host-only plan probe matching its binary hash.
The copy probe binary is reproducible from its archived source and recorded
compiler command; only its hash is retained. Temporary probes are deleted.

`copy-attempt1.log` and `copy-attempt2.log` are harness development failures:
wrong scratch lifetime and duplicate labels. The owner rejected both before
copy execution. The final successful proof uses unique transaction-lifetime
scratch allocations, as production requires. Neither failure changed a runtime
safety guard or led to a device run.

Real-model exactness is pending coordinator W2m/WS/WSs/WS128x on the new sealed
artifacts; these CPU receipts cannot substitute for that device evidence.

Compiler logs retain their original diagnostic spacing, including trailing
spaces. Whitespace checks apply to source and documentation; raw logs are
retained byte-for-byte.
