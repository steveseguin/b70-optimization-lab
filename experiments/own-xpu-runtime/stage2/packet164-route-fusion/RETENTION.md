# Retained evidence

`evidence/input-pins.json` records the original path, byte size and SHA256,
plus compressed SHA256, for eleven existing inputs. Each `.gz` is deterministic
gzip (`mtime=0`) of the complete original file, not a summary or selected
prompt subset. `analyze.py` checks both hashes before decoding. Restore to a
new destination with `gzip -dc <file>.gz`; never overwrite frozen parents.
The full 4.6 MB packet141 event stream is compressed below 1 MiB. No original
evidence was removed. The retained full record results contain their actual
prompt rows and exactness scope, not new performance results.

`prior-audit.json` and `prior-matches.txt` retain the searched path/hash census
and matching lines. Packet147 has a PLAN rather than a DO-NOT-REPEAT file.
`source-pins.json` freezes the specific source/note boundaries cited in the
decision; `input-pins.json` freezes numeric evidence. Build receipts enumerate
the actual local header closures and compiler commands. These are lab CPU
fixtures depending on existing in-repository sources, not a public package.

`build/` is ignored. It holds two small host binaries, four bounded byte dumps,
objects and a private exact copy of p141's p109 header. Recreate with
`cpu_gate.py`; compiler/version, source and binary hashes are retained. The
four byte-dump SHA256 values must agree; no dump is a model weight file.
Compiler logs and JSON summaries are tracked. No generated cache is committed.

No artifact of 1 MiB or larger is added. The packet's total retained evidence
is useful for independent CPU review without relying on ignored live run paths.
