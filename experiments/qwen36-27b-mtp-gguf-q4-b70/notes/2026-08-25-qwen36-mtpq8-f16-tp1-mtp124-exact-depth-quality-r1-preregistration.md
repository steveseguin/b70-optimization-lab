# Embedded-Q8 F16 TP1 MTP1/2/4 exact-depth quality R1

This combined expansion follows the successful exact-8K route screen. It keeps
the sealed MTP3 R3 runtime/model/fixture identity and runs one fresh MTP0
control followed by fresh isolated MTP1, MTP2, and MTP4 lifetimes. Every arm
covers display depths 0/2K/4K/8K/16K/24K/32K with 128 output tokens. Display
x=0 retains the disclosed R3 transport: zero prior active context plus one
ordinary token ID 90, so API usage reports one physical prompt token.

Each candidate cell must match both the fresh same-run MTP0 output and the
sealed MTP3 R3 target hash, report cache zero, and have one positive conserved
draft row. After its seven cells, each candidate runs its own full lane battery:
four exact canaries, two identical repeats, and the approximately 27.2K-actual
needle generated from the 29,400-token suite target, with all seven requests
reporting `cached_tokens=0`.

Candidate failures are preserved and route-local so later candidates still run.
A control failure invalidates all candidates; unclean shutdown invalidates the
shared frame. There is no speed floor and no graph, site, record, featured, or
protected-value authority. Passing arms are quality-complete inputs for a
separate tracked family-ingestion review.

Inert check:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py --check
```

Future create-only launch:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py \
  --execute \
  --ack 'RUN qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-20260825-r1'
```

Output root:
`/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-20260825-r1`.
