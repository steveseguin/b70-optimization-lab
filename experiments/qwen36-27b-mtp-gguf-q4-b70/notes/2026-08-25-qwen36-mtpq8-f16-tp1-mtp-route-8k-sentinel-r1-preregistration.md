# Embedded-Q8 F16 TP1 MTP route 8K sentinel R1

This is a bounded route screen, not a context curve or a speed promotion. It
uses the successful embedded-Q8 MTP3/F16 graph-off R3 tuple unchanged and runs
five fresh, isolated server lifetimes at exact 8K in this fixed order:
MTP0 target control, MTP1, MTP2, MTP3 positive control, and MTP4.

Every arm must produce the same deterministic 128-token target output as the
fresh MTP0 control and the sealed R3 8K hash. Each speculative arm must report
one positive, conserved draft-acceptance row. Cleanup is independently required
after every lifetime. Candidate boot or request failures are preserved and do
not stop later candidate arms; however, MTP0 or the proven MTP3 positive control
failing invalidates the entire screen.

The only positive authority is to name MTP1, MTP2, and/or MTP4 routes that may
receive a separately preregistered 0/2/4/8/16/24/32K curve. There is no speed
floor. This packet cannot publish site rows, submit a record, replace a featured
or protected value, or alter the successful MTP3 R3 evidence.

The default command is inert and performs identity checks only:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py --check
```

The explicit future launch command is:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py \
  --execute \
  --ack 'RUN qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1'
```

It is create-only at
`/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r1`
and still requires clean pushed `main`, the sealed runtime/DSO/model/fixture
identity, an idle GPU0, the normal exclusive locks, and the exact acknowledgement.
