# Packet58y CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare a fresh one-card split of packet58v's overlap engine on October 18.
Unsloth IQ3 compressed model, packet49 split32 arithmetic, tile16, full BF16 KV,
18 GB cache, twelve fixed prompts at a 128-token cap. Device work belongs only
to the coordinator's existing packet58x whole-host batch.

## Outcome

The new diagnostic compiles with GNU and Intel; CPU exactness and startup gates
pass. No device run or speed result exists. The next lever is not selected from
old pre-overlap numbers. The +3% kill gate was committed before device data.

## What worked

The native miniature retains exact tokens and all 32 layer fixture files across
an untraced control and two traced repeats. Its attribution buckets close to
the measured host span and profiling is rejected. Full-size startup, two K1
source-byte checks, delayed-fill ownership tests and the real proposal's three
intercepted native boundaries pass. Published pointers supply miss counts.

## What failed or remains uncertain

The first ordered temporary batch caught 58x files changing after their seal;
its failed plan is retained. Nothing in the frozen packet was repaired here.
Device exactness, instrumentation overhead and actual per-token measurements
remain unrun. Zero-copy kernel time cannot be isolated from the compute tail;
all unavailable device durations remain null. Host spans are not causal savings.

## Evidence and patches

[Work note](../../../../notes/2026-10-18-own-runtime-packet58y.md),
[copy manifest](copy-manifest.json), [build and gate seal](build-receipt.json),
[native delta](attribution_source.py), [miniature equality](evidence/attribution-cpu.json),
[first batch refusal](evidence/queue-plan-batch.log), [batch contract](batch-contract.json).
Build artifacts stay ignored; build_engine.py rebuilds them from pinned frozen
objects under the shared compiler turn, without running a GPU executable.

## When to revisit

After the coordinator runs the ordered batch in one continuous whole-host hold,
read its receipts, validate every packet49 token and rank supported levers under
the registered +3% gate. A missing/changed predecessor seal or changed pause
must be resolved by the coordinator before any diagnostic device launch.
