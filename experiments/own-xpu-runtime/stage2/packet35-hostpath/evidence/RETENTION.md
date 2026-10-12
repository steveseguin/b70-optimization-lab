# Packet 35 evidence retention

Inherited and new evidence have separate identities. A copied archive does not
become a fresh packet 35 gate or device measurement.

| Artifact | Identity and purpose |
| --- | --- |
| `preparation-logs.json.gz` | Inherited packet 27 preparation/provenance record. Preserve its original member bytes and historical identity. |
| `preparation-logs-p29.json.gz` | Inherited packet 29 archive of 2,465 CPU preparation text artifacts: compiler, argument-validation, integration/sanitizer, fixture, model timing/ownership and failed-diagnostic logs. Its historical hashes and cleanup record remain parent evidence, not new packet 35 passes. |
| `fixture-gates-full.json.gz` | Inherited fixture detail. Its old qualification applies only to its recorded source and binaries. |
| `expert-down-nonfinite-initial/` | Inherited initial exceptional-value failure executables/logs; local manifest binds hashes and sizes. These retain a negative result, not a newly qualified path. |
| `prepared-equivalence-arguments.json.gz` | New packet 35 argument-equivalence audit evidence. Its consumer is the matching prepared-equivalence receipt; retain exact argument blocks and source/binary identities. |
| `preparation-logs-p35.json.gz` | New packet 35 preparation archive produced at final cleanup/sealing. It holds this packet's commands, compiler/gate output and per-case receipts; members are byte-verified before disposable scratch removal. Never describe the parent archives as its contents or evidence. |

The preparation archives are retained even when larger than 1 MiB because the
recorded commands, failure diagnostics and per-case receipts are needed for
independent review. They contain no downloaded checkpoint and no native benchmark
result produced by this CPU-only packet. Size or overlapping content is not
permission to discard historical evidence.

For a preparation archive, decompress with gzip and parse its JSON array. Locate
a member by `path`, decode its `base64` payload, and verify its `sha256` and `bytes`
before restoring it beneath this packet's ignored `build/` directory. The cleanup
receipt must bind compressed and uncompressed archive hashes and verify every
member before its original disposable scratch can be removed. The new packet 35
archive needs its own receipt; the old packet 29 cleanup record cannot certify it.
The argument-equivalence archive uses the representation recorded by its consumer;
read that receipt and preserve the payload rather than assuming the preparation
archive's member schema.

Preserve these artifacts while this packet remains an evidence or reproduction
dependency. No timed deletion is authorized. Regenerating a new CPU log requires
rerunning its exact source/model/toolchain identities; a fresh log does not replace
historical bytes. Refer to `../inherited-files.json`, `../source-packet29.json` and
`../inherited/` for the parent snapshot boundary. Final packet 35 gate and build
receipts identify which new files bind the sealed binaries.
