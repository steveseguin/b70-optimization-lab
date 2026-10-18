# Packet91 retention and restoration

The native sources are a frozen-source copy of packet84. `rope.bf16` is the
same 4 MiB input blob already tracked by packet84, retained to preserve the
copied source/fixture paths. Original patch files retain their exact bytes,
including patch context whitespace. `parent-source-manifest.json` records the
copy inputs; no original is deleted or modified.

`build-provenance.json` binds the original packet84 and packet82b GNU/Intel
binaries, build receipts and source closures. All selection binaries are local
hard links to these parent binaries so the shared v4 safe-path check accepts
them without creating another binary's worth of disk data. The selected chain
uses packet-owned symlinks; changing a selection replaces only those symlinks.
Build artifacts and selection hard links are ignored by Git.

To restore aliases on the originating host, preserve/restore the hash-pinned
parent builds first, then run `python3 -B restore_links.py` with nice19, helper
CPU affinity, stdin `/dev/null`, and the 8 GiB process bound. It verifies the
parents and recreates only packet91's aliases. `prepare_chain.py` restores the
inherited fixture inputs by hash. No public clean-build claim is made.

Each fresh CPU recurrence invocation retains compact compressed expected and
candidate transcripts, case descriptions and native counts, then removes its
own scratch. Full-size startup retains compressed census, selected-operation
and draft-prefix receipts, then removes its own scratch. Pytest scratch is
removed after the log is retained. Earlier packet91 seals are retained as
hash-named compressed records; they are superseded, never source-screen evidence.

The final space receipt is `evidence/final-verification.json`. Even counting
shared hard links repeatedly, the new packet trees stay below 1.5 GB. Root free
is checked at CPU gates and must stay above 12 GB. The chain storage precheck
reserves its full future writes separately; its margin must be checked again
by the coordinator after packet84 finishes.
