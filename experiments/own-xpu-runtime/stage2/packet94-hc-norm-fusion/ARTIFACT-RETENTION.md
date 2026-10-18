# Packet94 retention and rebuild

The 4,194,304-byte rope.bf16 is an immutable source-relative runtime constant,
restorable from packet84 with SHA-256
92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390.
Parent source hashes identify every copied source and adapted harness.

The two approximately2.2 MB gzip byte archives are required exact-output
receipts, not generated caches. They retain every output, scratch and control
byte from96 full-shape HC cases. GNU and Intel production differ only in NaN
payload selection, explicitly enumerated in cpu-byte-identity.json. Each
candidate matches its same-compiler production exactly, including those bits.
Every archive has compressed and original SHA-256, and decompresses to the
recorded expected/candidate streams. All twelve case ledgers are retained.
The first gate attempt's cross-compiler assertion is retained in
`evidence/cpu-first-attempt.log`; it was too strong for the existing production
compiler difference. No candidate comparison was weakened or normalized.

Builds and fixture scratch live only in ignored build/. Receipts bind the
copied source closure, checked mirrors, inherited object bytes and both
executables. This is a local lab screen packet, not a portable public recipe.
Only entry-main, selection dispatch and HC dispatch/kernel units are rebuilt;
other objects are reused from packet84 by hash. One compiler at a time uses
/tmp/own-xpu-runtime-cpu-compile.lock, with the coordinator's whole-host hold
check retained. Every stage enforces priority19, CPUs8-15,24-31,8 GiB address
space, build below1 GB, and root free space at least12 GB.

CPU reconstruction stages (all with `nice -n 19 taskset -c 8-15,24-31
python3 -B`, stdin /dev/null): build_engine.py, cpu_gate.py, full_shape.py,
memory_plans.py, python_gate.py, seal.py, final_check.py, queue_plan.py.
Keep prior receipts when rebuilding; a different binary requires a new seal.
The source-local build script deliberately refuses overwriting a completed
build receipt. Generated startup test source remains to verify its bound seal;
per-run fixture scratch is removed only after compressed receipts are checked.
No frozen packet or other process's scratch is removed.
