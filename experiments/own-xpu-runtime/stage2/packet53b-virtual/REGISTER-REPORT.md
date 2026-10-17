# Final offline register and spill result

[Machine receipt](register-report.json) binds the final device build, exact
kernel source mirror, compiler/translator/ocloc identities, commands, logs and
compressed native assembly. This is CPU-only BMG-G31 compilation, not an
installed-driver JIT capture or measured occupancy result. No GPU is opened.

All15 inspected kernels report128 configured GRFs. Counts below are the
native assembly's `.spill` metadata; absence means zero reported spills.
The receipt's text search for scratch-message mnemonics is supplementary and
does not override explicit spill metadata.

| Class | Candidate | FP32 chains per physical lane | Spill metadata |
| --- | --- | ---: | --- |
| Expert gate/up | paired V4 global, remeasured reference | 8 | 896 bytes; estimated60 GRF references; predicate stores/loads2/4 |
| Expert gate/up | V8 split-stream | 8 | none |
| Expert gate/up | V16 split-stream | 16 | none |
| Expert down | V4 / V8 / V16 global | 4 / 8 / 16 | none |
| HC low, both sides | V2 / V4 / V8 | 2 / 4 / 8 per split | 64 bytes each, same as the accepted packet51 control |
| HC gate, both sides | V2 / V4 / V8 | 2 / 4 / 8 | none |
| Small FFN tuple | V2 / V4 | 2 / 4 per split/member | none |

The requested paired V16 with32 simultaneous sums is excluded. Initial paired
V8/V16, bounded-chain and scalar-unpack attempts spilled. Their source, logs
and assembly remain under evidence-cpu; no speed result exists for these
rejected CPU arms. The unsupported256-GRF property is also excluded.

The V8/V16 replacement gives gate and up separate subgroups, retaining the
exact logical chains, reduction tree, compact production bytes, status/error
semantics and BF16 outputs. It costs an extra input load per stream and may
change occupancy; only the sealed device timing windows can decide its value.
V4 is deliberately retained with its original paired scheduling and reported
spills as the control-of-record candidate requested in the brief.
