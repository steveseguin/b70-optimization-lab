# Embedded-Q8 MTP3/F16 TP1 exact-depth R2 retry

R2 is a fresh create-only retry of the preserved R1 pre-GPU failure. It pins
the committed R1 manifest, runner, and validator plus the immutable R1 failure
receipt. No R1 row is reused; R1 launched no server or GPU and remains a
zero-cell negative result.

The sole execution change permits leading whitespace before a SONAME in GNU
`ldd` output. Canonical path equality, SHA-256/size gates, and the exact
eight-DSO closed-set requirement remain unchanged. The embedded-Q8 model,
`15586e2d` VDR2 binary and manifest, server arguments, graph-off environment,
MTP0/MTP3 arms, seven contexts, exact-output parity, draft-counter gates,
quality battery, cleanup contract, and authority are inherited without change.

Static check is inert:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py --check
```

The fresh output root is
`/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r2`
and execution requires the exact acknowledgement printed by `--check`. A pass
still needs separate result and quality review before any family/site change.
