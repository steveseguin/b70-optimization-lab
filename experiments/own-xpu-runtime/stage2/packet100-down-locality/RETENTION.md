# Packet100 retention

Retain copied sources, copy-lineage and parent manifests, build commands and
object identities, CPU compressed raw byte transcripts and case logs, complete
compressed startup censuses/operation lists/native plans, linked assembly,
route inventory hashes, refusal logs, seals and queue plans. No raw model
weights or secrets are copied. No artifact here is a public deployment recipe.

`build/` is generated local scratch, ignored by Git. Native objects and binaries
are hash-bound in receipts and selections; inherited objects remain tied to
packet97's exact local build. `kernel_gate.py` regenerates the checked include
mirror from copied sources. The source copy and initial checked mirror were
preserved in b81a83bec; generated build files were subsequently removed from
Git tracking, without removing local files. That staged untracking was consumed
by the concurrent 97f9200a4 commit. It affects only this packet's regenerable
build tree, not another packet's evidence.

Fixture run directories are deleted only after their raw bytes/case logs have
been verified and retained compressed. Full-size runs retain complete censuses
and selected operations before removing each scratch directory. Offline compiler
scratch is retained locally, comfortably inside the 500 MB build cap. The
initial pre-mode-guard build receipts remain under evidence/pre-mode-guard;
Git retains the corresponding earlier source identity.

Missing packet77/86 raw route payloads were already absent. Packet100 deleted
none of them. Their hashes and origin inventory paths are retained in
`evidence/route-inputs.json`; recovery must match those bytes, not manufacture
IDs from a plausible distribution. About 151 MB of logical build files and
about 20 GB root free were observed after all gates; neither number grants
permission to start a record chain.

The copied 4 MiB `rope.bf16` is retained intentionally. It is packet97's exact
immutable rotary-position constant table, required by this engine's startup
and build identity. `copy-lineage.json` pins its original bytes; restore from
the pinned packet97 file (or the committed packet100 copy), never regenerate
with a different math implementation. This is the only >=1 MiB tracked input
outside generated build directories. Selected binaries are local hardlinks
under `selections/*/build/`, also ignored; all hashes remain in the seals.
