# Packet93 artifact retention and rebuild

This is a local research screen bundle, not a public deployment recipe.
Copied packet84 sources are bound by `parent-source-manifest.json`; its actual
object lineage is bound by `build-device-receipt.json` and
`evidence/object-identity.json`. Existing source packets were not edited.

Retain `rope.bf16` (4,194,304 bytes): required source-relative runtime constant,
restorable from frozen packet84 with SHA256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
Retain both `evidence/cpu-bytes/*.bin.gz` archives (about 2.5 MB each): they
preserve every raw decoded FP32 value, ordered chain/tree, BF16 logit and
argmax comparison. The extra candidate-operation check makes the production
stream length differ from the candidate streams. Each compiler/repeat verifies
both compressed and raw hashes in `cpu-byte-identity.json`. Size and duplicate
structure are not grounds to discard this evidence. Recreate only by running
`cpu_gate.py` with the pinned compiler/source identity, then verify recorded
hashes; do not silently replace old evidence if a compiler changes bytes.

Full-size plans/censuses and offline assembly are retained compressed with
hashes and commands. Build logs and compiler flags are recorded locally and in
receipts. `build/` and per-view hardlinked builds are ignored generated local
artifacts. They contain the checked source mirror, inherited objects, compiler
outputs and full-shape executable required for local seal verification. CPU
fixture run scratch and startup run directories are removed after their
verified evidence is saved. Only packet93 scratch is removed. The build is
below 1 GB; no other packet or live record evidence is cleaned.

A clean reconstruction requires the pinned packet84 build/object inputs and
GNU/Intel compilers; it is not an independent public rebuild. Preserve old
receipts before rebuilding in a new authorized packet identity. CPU stage order:
`build_engine.py`, `cpu_gate.py`, `inspect_decode.py`, `full_shape.py`,
`memory_plans.py`, `build_microbench.py`, `python_gate.py`, `seal.py`,
`final_check.py`, `queue_plan.py`. Use `nice -n19 taskset -c8-15,24-31 python3 -B`
and stdin `/dev/null`. Compilers share `/tmp/own-xpu-runtime-cpu-compile.lock`,
wait for other compiler processes and run one at a time; process address space
is capped at 8 GiB. Keep root free ≥12 GiB and build <1 GB. These stages never
run a device executable. A rebuilt binary may need a new seal identity; never
rewrite a historical measurement's hashes to match new code.
