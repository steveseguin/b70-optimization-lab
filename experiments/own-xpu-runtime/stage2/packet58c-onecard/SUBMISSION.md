# Packet58 one-GPU submission preparation

This is a separate 1-GPU, own-runtime, plain-decode lineage for the Unsloth
quantized compressed UD-IQ3_XXS version. The pinned submission ledger contains
no matching submitted 1-GPU record. No 2-GPU threshold is inherited, and the
llama.cpp local 15.9–21.6 tok/s reference is not a submitted-record floor.
`record-threshold.json` binds that review to the ledger bytes; a changed ledger
requires a fresh matching-model/card-count review before preparation.

After all coordinator windows pass:

```bash
P=experiments/own-xpu-runtime/stage2/packet58-onecard
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/packet58_submission.py" \
  --chain "$P/evidence/chain-a" --output "$P/submission/prepared-a"
```

This reads original native outputs, reconstructs the 99-interval metric,
checks all 12 outputs against packet49, compares early layer bytes in WS,
and checks WS128x/WS128 fresh-process repeats. Every window must bind the
same binary, sources, one physical card, miss-path decision and BF16 4K
configuration. It checks both K1 receipts, journal tails, source-bound CPU
gates and teardown. No supplied summary `passed` field can replace these checks.

It writes a result, hash-bound quality evidence and promotion attestation,
a short result packet, and **payload-draft.json** with `gpuCount=1`, custom
engine, plain decode, and immutable weight cache flags. It does not load a
model, access credentials, contact LocalMaxxing or post anything. The raw
files referenced by the evidence manifest remain part of the result; retain
and publish them when promoting the measurement.

The requested 128-token comparison uses the same metric as the two-card line,
but its strict 512-token gate remains false. A two-card external scope
exception is not silently granted to this new lineage. The coordinator must
review the new 1-GPU 128-token submission scope before producing a postable
queue. Standard 512-token prefill and full natural completion remain “not
measured”; no values are borrowed. There is no MTP result in this packet.
