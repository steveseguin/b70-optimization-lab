# Current-f01e AutoRound TP2/MTP4 eager F16 16K/24K expansion R1

State: **preregistered; not launched**.

This packet measures exactly two cells: TP2 native-MTP4 eager/F16 at 16K and
24K active context. It exists because the same-profile exact-4K sentinel passed
all exact/cache-zero, 90/148 isolated acceptance, TP2/MTP0 token-parity,
quality/baseline, topology, rank-cache, and cleanup gates. The passed sentinel
is hash-pinned but did not itself authorize automatic expansion; this packet is
the separate human authorization for only 16K and 24K.

Every included candidate must match the pinned same-image, same-topology
TP2/MTP0 target at all 128 output IDs. The clean TP2/MTP3 16K and 24K receipts
and their positive conserved acceptance evidence are pinned as the mechanism
parent. They do not replace the target oracle.

The scope exclusions are hard gates. x0 has no literal fixture; 2K is not
authorized; 4K is already closed; 8K remains the existing speedless token-99
TP2/MTP4 quarantine; and 32K is excluded because MTP4 has already produced a
runtime-fatal speculative-shape failure at that depth on TP1 and is a higher
risk endpoint on TP4. A successful 16K/24K result cannot clear or infer any of
those cells and cannot launch another depth automatically.

One eager server handles the two requests. Each request gets isolated before
and after draft-counter snapshots. Exact depth, cache zero, positive finite
conserved acceptance, and exact target parity are per-depth gates. Full
objective/baseline quality, both TP2 workers, model verification, rank-isolated
cache evidence, and strict cleanup are global gates. Execution additionally
requires clean local `main` equal to cached and live `origin/main`.

There is no speed floor, automatic site publication, protected or historical
replacement, or descendant execution authority.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1.sh --check
```

Execution command (not run during preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-20260826-r1'
```
