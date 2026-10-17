# Packet81 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packed activation loads reduce routed-expert issue overhead without
changing any output? Packet75 source bundle, packet70 wide64 control,
Unsloth UD-IQ3_XXS compressed Flash-Next version, IQ2_S gate/up and IQ4_NL down,
`iq3-p49-split32-v1`, intended two B70 cards. CPU-only on steve-b70s,
2026-10-17; model weights, target oracle and full BF16 KV unchanged.

## Outcome

Three choices prepared for screening: gate-only, down-only and combined.
No GPU timing or model output was measured here. The shared v4 coordinator
screen remains the next step; no candidate is promoted or selected live.

GNU and Intel each pass two fresh executions of all four views, including
production. Each execution has 18 expert/route cases, 110,592 raw FP32 chain
checks and 3,456 tree checks. Full startup passes eight view/rank combinations,
with selected-operation capture, actual production extents, post-load capture,
draft initialization and teardown. One short-allocation and five malformed
selection tests reject as intended. 80 shared wrapper and five packet tests
pass, including closed worker imports and real lane admission. Four seals,
five A plans, nine possible B plans and both temporary queue plans pass.

## What worked

Explicit uint32 vectors coalesce eight unchanged BF16 activation values into
one load message. Fresh offline BMG-G31 assembly reduces gate/up loads 51→27
and instructions 1993→1897; down loads 79→31 and instructions 2955→2755.
No spills and no extra device storage; 128 configured GRFs in both kernels.
This establishes the compiler mechanism, not device throughput.

## What failed or remains uncertain

Raw unremapped production includes initially refused duplicate owner ABI;
the production checked mirror fixes the build, with the diagnostic retained.
An initial incomplete local source copy lacked prototype headers and the
RoPE build include; both were copied from the frozen parent before gates.
No software or device job was killed, and no GPU fault occurred in this work.
Physical occupancy, cache hit rate, exact dynamic instruction mix and speed
remain unknown. Past raw-weight load-count improvements sometimes lost speed.
The first local seals were superseded solely to correct inherited plan-count
progress text; prior seals and that text remain under evidence/first-seals.
A final whitespace-only correction reran both compiler byte gates and resealed;
its prior source bytes and receipts remain under evidence/pre-whitespace-seals.

## Evidence and patches

[Analysis](ANALYSIS.md), [source origin](parent-source-manifest.json),
[candidate header](p65_expert.hpp), [CPU bytes](evidence/cpu-byte-identity.json),
[retained cases/output](evidence/retained-cpu.json),
[device compilation](build-device-receipt.json),
[offline candidate](register-report-candidate.json),
[full-shape startup](evidence/full-shape.json),
[shared-wrapper checks](evidence/python-tests.json),
[final seals/plans](evidence/final-check.json),
[temporary queue plans](evidence/queue-plans.json), [retention](RETENTION.md).
Final build is about 169 MB logical, under 1 GB; compiler child peak RSS is
726,712 KiB. The identical 4 MiB RoPE constant is a read-only relative link
to the frozen parent, with unchanged content hash.

## When to revisit

Coordinator runs A once, then only its exact improving winner on B between
fresh production controls. Retain all outcomes; a loss closes this load
spelling, not the expert lane. A both-lane win needs a fresh composed record
chain and unchanged oracle/determinism/final-suite gates. Pending evidence
is not an authorization to launch from this CPU task.
