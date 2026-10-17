# Packet 59c: selectable draft kernels

Built from packet 59. One host binary and one device binary contain packet 56
and packet 59 choices for **30 draft swaps and all ten fusions**. The sealed
`selection.json` defaults every draft entry to `production` (packet 56).
Target choices, target arithmetic, weights, the 91,392-row draft head and BF16
KV remain unchanged. This is a diagnostic screen packet, not a new speed result.

[Coordinator commands and four-screen plan](WINDOW.md) ·
[source diagnosis](SOURCE-DIAGNOSIS.md) · [CPU preparation](CPU-BUILD.md) ·
[task note](../../../../notes/2026-10-17-own-runtime-packet59c.md)

## Selection contract

`p59c_select.hpp` is the complete registry. `selection.json` keeps the frozen
packet56 target `choices` and its existing decision hash; `draft` has one entry
per swap or fusion. Every value is `production` or `packet59`. Both the Python
sealer and native init reject missing, duplicate, unknown or invalid entries.
Native init checks the exact selection bytes against `--selection-sha256`.
It also rejects changing any target choice.

- Each QSA projection, attention, expert gate/up and down, attention output,
  router, shared-expert projection and shared router has its own entry.
- Attention, FFN and final HC low/gate sites are independently selectable;
  attention and FFN inject sites are independent too.
- Embedding, hidden, attention-HC, FFN-HC and final norm trees are independent.
  Embedding and hidden projections each have their own entry.
- The three low activations, three gate/mixes, expert and shared activations,
  attention combine and hidden merge each have a fusion entry. A fusion needs
  its corresponding `packet59` producer. Turning it off keeps the producer's
  new schedule and restores the original separate consumer. Invalid producer /
  fusion combinations are refused before model initialization.

Selection is resolved while preparing commands. Captured device replay adds
no file read or selector lookup. Original launch slots, including empty fused
slots, remain intact for context recapture. The per-rank
`draft-kernel-choices.json` records the selection hash, all switches and every
original site, including the hidden/embedding prelude.

## Fast resealing without another build

`p59c_seal.py --fast-reseal --selection FILE --output NEW_LINEAGE` makes a new
immutable directory below `selected/`. It hardlinks the existing binaries,
copies the selected JSON, and binds the same source/build evidence to a new
screen seal. It never overwrites the default seal or an earlier selection.
The screen consumes that directory via its existing `--lineage` option; no
shared screen code is changed. Hardlinks are ignored build artifacts, not
copies committed to Git. Never rebuild or alter a binary after sealing.

The four screen profiles and single-switch profiles are already CPU-gated.
A new valid combination gets two fresh small CPU runs before its fast seal;
no compiler or device is launched. The selected output carries a reseal timing
receipt. Restore the same locally compiled products before resealing elsewhere;
this packet is not a public deployment package.

## CPU evidence and its limits

`cpu-gates.json` binds 46 choice sets: the production default, all packet59,
four screen groups and 40 individual switches (fusion tests also enable the
required producer). Each has two fresh CPU rank-pair runs, 96 target layer
fixtures and 24 generated target tokens, plus at least 24 draft proposals.
Default proposals also equal packet56; all-on proposals equal packet59.
Every choice set retains target fixture equality to packet56.

The mini engine uses small BF16 tensors. `operator-gates.json` adds separate
production-width INT8/BF16 fused and unfused synthetic arithmetic, 135 route
checks and 88 split32 checks per fresh run. This covers the production-only
route/split32 entry points bypassed by the mini engine. None of these fixtures
loads real model weights or establishes device determinism, target-oracle
parity, acceptance or speed. The coordinator's screens retain all 13 exact
checks; any winning combination still needs the full qualified chain.

## Retention

Keep both `cpu-evidence/operators/qsa-{a,b}/output.bin` files (1,622,016 bytes
each). They are the actual ordered output bytes from two fresh host runs over
88 split32 cases, including context boundaries and inactive/error cases.
`operator-gates.json` and the sealer consume their SHA256 values. Their size
and duplicate content are not grounds for dropping either run's evidence.
They can be regenerated on a fresh preparation with the host
`p49-qsa-fixtures --output NEW_DIRECTORY` executable; verify the retained
`bfba50bfd43acebef6ba26cdaa5102c5674e71811bcb16cfc0d51211b0f209dd` hash.
No real model weights are present. The local build is about 125.5 MB; selected
lineages share its binary inodes and add only small JSON files on disk.

[Preparation closeout](CPU-PREPARATION-CLOSEOUT.md) ·
[fast reseal checks](reseal-checks.json) ·
[target source review](target-parity-review.json)
