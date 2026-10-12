# Arithmetic-v2 128-token CPU oracle suite — closeout

<!-- campaign-closeout -->

## Question and identity

Extend all twelve fixed realistic-suite CPU oracles from 64 to 128 generated tokens
for quantized Unsloth UD-IQ3_XXS Qwen3.8 Flash-Next, arithmetic
`iq3-p17-detmath-v2`. Run on 2026-10-12, CPU only, context 256, with unchanged
numerical sources and compiler flags. The wrapper/build identity is recorded in
[build-receipt.json](build-receipt.json); no device code or discovery was run.

## Outcome

Complete: twelve prompts, each 128 generated tokens with no early end. Retained
9,216 raw BF16 fixtures: 48 layers at generation steps 1–8 and 97–104 for each
prompt. All twelve 64-token prefixes, early fixtures and ledgers match the existing
suite exactly. The incident capacity gate additionally matches the sealed oracle.
The complete checker passed, as did all 14 runner/checker tests, including corrupted
copies. This is CPU exactness coverage, not a serving speed result or the 512-token
realistic final performance gate.

Actual campaign span was 21,922.563252 seconds (6.089601 hours). Summed numerical
process wall time was 43,649.869087 seconds; measured CPU time was 20.199154407 hours.
Per-position and per-generated-token wall times remain in each prompt directory.
Every finished prompt was committed and pushed separately.

## What worked

[Capacity analysis](capacity-analysis.md) established that context capacity changes
cache allocation and bounds, not valid-position arithmetic. Before releasing token
65, the context-256 incident reproduced the sealed context-192 run's 64 token IDs,
all logit/top-five records, 384 raw fixtures and eight ledgers byte for byte. All
other prefixes then passed the same comparison against their 64-token suite runs.
The cap-independent existing runtime bundles are referenced by five-file SHA256
bindings rather than copied. Temporary output directories, verification before
rename, status updates, and per-prompt pushes kept finished work restartable.

## What failed or remains uncertain

The first coordinator matched the old suite path as a substring of the new suite128
path, keeping concurrency at one unnecessarily. After two completed prompts were
pushed, the supervisor was stopped cooperatively, the path comparison was fixed,
and the run resumed with up to three two-thread workers. One customer-email partial
had zero completed positions when stopped; no completed prompt was recomputed.
An administrative refresh refused a shell's broader affinity; subsequent commands
explicitly used the original 4-15,20-31 mask. Oracle units retained that mask throughout.
These events are recorded in [coordination-fix.json](coordination-fix.json).
There were no output differences. No GPU runtime execution or performance
qualification is claimed by this CPU campaign.

## Evidence and patches

- [Per-prompt results and timing table](README.md)
- [Final verification and totals](final-verification.json)
- [Tests, including corrupted copies](checker-tests.json)
- [Complete wrapper delta](oracle128.patch) and [CPU rebuild script](build_cpu.py)
- [Sealed incident equality](incident-retrospective/equality-proof.json)
- [Pre-token-65 capacity gate](incident-retrospective/capacity-prefix-proof.json)
- Each prompt's `receipt.json`, `suite64-equality-proof.json`, `validation.json`,
  `result.json`, `positions.jsonl`, `tokens.jsonl`, layer fixtures and ledgers.

Receipts bind the executed runner snapshot and CPU binary/build. Compressed logs
retain the original SHA256 and byte length in receipts; decompress them to restore
those original bytes. Final verification rechecked their restored hashes. Model
weights and the rebuilt executable are external inputs and are not committed.

## When to revisit

Use these references when a runtime window is ready to compare 128-token output
and both fixture ranges. A changed arithmetic identity, tokenizer, weights or
numerical source requires its own oracle qualification. Any device run remains
outside this CPU-only task. The broader optimization lane remains open.
