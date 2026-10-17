# Packet80 retention and rebuilding

Keep the ignored build directory, including GNU/device binaries, inherited
objects and parent fixture links. This is a lab packet with pinned local parent
objects, not a standalone public recipe. The maximum build size is1.5GB, each
process is limited to8GiB, and compiles are serial at nice19 on8-15,24-31.

Fresh preparation order: build_engine.py, cpu_gate.py, full_shape.py,
memory_census.py, retirement_gate.py, protocol_gate.py, mini_gate.py (with
OMP_NUM_THREADS=2), prepare_chain.py, prepare_packet.py, fast_reseal.py,
dry_run.py. All use python3 -B and stdin /dev/null. Existing sealed views are
selected with fast_reseal.py; a changed CPU helper requires prepare_packet.py
--refresh, which archives original seals and refuses any started chain.

The exact2096-case operator fixture is retained once as a content-addressed
.bin.gz under evidence. It exceeds1MiB because it includes full outputs and
scratch for2048 route and40 norm scenarios plus8 HC fixtures; it is not a
headline measurement. Per-view ignored fixture links refer to identical bytes.
Every original numerical output was byte-verified before gzip compression.

retain_build.py archives exact generated sources, the checked compiler mirror,
full-shape allocation censuses and CPU logs in evidence/build-sources.tar.gz.
The adjacent build-retention.json lists each original member's byte count and
SHA256; archive creation verifies every member and deletes nothing.
restore_links.py restores missing archived bytes, verifies existing files and
recreates only pinned parent/fixture/binary links. It never runs a model.
Larger pre-refresh seal archives retain exact previous JSON strings and carry
the decompressed SHA256 in their filenames. They were never used on a device.
The build-retention manifest is also larger than1MiB because it records every
original member separately. Keep it with its archive; restore_links.py consumes
both. The final all-view plan receipt retains every actual plan output so each
configuration and window can be reviewed. dry_run.py regenerates it; the final
readiness receipt binds its exact bytes through the CPU rehearsal receipt.

Both numerical compilers run twice for each of16 compositions. All64 placement
configurations receive a real post-load memory census on both ranks and two
native miniature target/draft comparisons. Reverse handoff and ordered queue
failures also run under GNU and Intel. These CPU proofs do not establish device
residency, real-model parity or speed; the coordinator's fresh chain must do so.
Only the documented preparation, chain and submission entries are supported;
other copied helpers preserve earlier source history.
