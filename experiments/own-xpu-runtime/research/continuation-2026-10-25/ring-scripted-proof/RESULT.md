# Scripted target-only depth-two ring proof: PASSED

All 32 gold output IDs match. All 2065
canonical target buffers and layouts compare exactly: True.
Every stage's native trace replays the 118 confirmed inputs in order,
with exact row lineage, global wire sequence, oldest acceptance, suffix discard
and physical/logical cursor accounting. Required rejected depths: [1, 2];
actual two-row stage0 suffix restores: 1. Every restore was byte-verified.

[Summary](summary.json), [full state comparison](comparison.json.gz),
[strict ring state manifest](candidate-state-set.json), [explicit ring result](ring-result.json).
The original result.json retains the reused lifecycle's older mode label; its exact
hash is bound by ring-result.json. No original evidence was rewritten.

Guesses were scripted from retained reference tokens. This is target rollback
qualification, not live recursive drafting or speed evidence. The [durable evidence packet](../ring-reuse-durable-archive.json) retains all new
traces, source and seals, and refers to byte-identical raw target bundles in the
already durable portable-live archive. [Restoration verification](../ring-reuse-archive-verification.json)
reconstructed all 417,299,400 raw bytes as independent files and passed the
strict native state reader. The complete raw tmpfs archive and originals remain
preserved as additional copies.
