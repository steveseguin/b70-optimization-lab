# Packet119 retention and reproduction

Keep the native source copy, source-copy provenance, p119 delta, micro and v5
scripts, captured route bytes and input hashes, CPU output gzip, ISA gzip,
startup/reset/protocol receipts and both proposal files in Git. No newly
tracked individual artifact is at least 1 MiB.

`build/` and `v5/build/` are generated and ignored. The build receipts bind
all exact local binaries, generated include mirrors, compiler flags and
inherited parent objects. Rebuild the CPU fixture with `build_cpu119.py`, the
AOT micro with `build_microbench.py`, and its retained ISA proof with
`inspect_warm_isa.py`. Regenerate seals and queue plans after rebuilding;
never hand-edit a binary hash to make an old qualification appear current.
The v5 README lists its separate CPU sequence. Original packet118 binaries
and their inherited object/source closure remain frozen local dependencies.
The copied `rope.bf16` and `mtp-manifest.tsv` are repository-relative symlinks
into that frozen packet. This is a local diagnostic, not a public package or
clean-machine reproduction claim.

Retained host byte evidence contains synthetic operator output only. The route
payload is the predeclared packet100b capture, not weights or prompt contents.
The ISA archive binds the exact compiled micro image and preserves the address
proof and cache-policy inspection. Actual device cache probes, micro timings,
quality outcomes and the conditional bracket will be retained under their
fresh numbered evidence directories by the coordinator. No existing artifact
was removed or consolidated by this work; unused newly copied orchestration
scripts were omitted from the new packet and listed in its provenance.
