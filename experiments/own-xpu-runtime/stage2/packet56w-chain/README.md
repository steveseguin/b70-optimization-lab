# Packet56w full-chain preparation

This separate chain uses the **exact packet56w screened device binary**,
`b6a78f44a7174ad2d4b22da804227cd4c4f9668cd230368a5ccbb2338c95c169`.
It never edits or replaces packet56, packet56w-spin, their seals, or their
retained screen evidence. No kernel, arithmetic or compilation change is made.

The screen measured 48.831 class-balanced tok/s, with 13/13 exact checks,
against packet56 controls of 46.792 and 46.796. These remain diagnostic screen
observations; this preparation provides no new measured result or submission.
The record floor is read from
[`scripts/packet49_record_threshold.json`](../../../../scripts/packet49_record_threshold.json),
currently 46.96269702286488, and checked again before posting.

The chain mirrors packet56's K0 → K1a → K1b → K2 → W0p → KD → W2m → WS →
WSs → WS128x → WS128 sequence. It retains the same packet49 oracle, 23/25
target split, draft rank 1, cards 0+1, 4096-token capacity, BF16 KV, reset
policy, exactness companions and 99/(t100−t1) class-balanced metric.
The owner-authorized 128-token scope is unchanged; the strict 512-token gate
remains false.

- [Exact coordinator command and CPU checks](WINDOW.md).
- [Preparation, dry-run and submission commands](SUBMISSION.md).
- [Decisions and checks](../../../../notes/2026-10-17-own-runtime-packet56w.md).

`build` is a view under `/home/steve/own-xpu-runtime-results/packet56w-spin/build`.
Its device engine links to packet56w-spin; unchanged fixture binaries and the
CPU-only draft reference link to packet56. The parent prefix calibration,
input bundle and packet49 oracle are read-only dependencies. No binary copy
or model load is needed. `prepare_chain.py` restores only these verified links;
it refuses replacement or changes after the chain starts.

`chain_seal.py` checks the original parent and screen hashes, their source
closures, screened CPU gates and bytes, all selected binaries, the oracle and
the local chain tools. Its separate `build-receipt.json` is admission evidence,
not a claim that the device chain has passed. The submission pins bind this
chain seal and the original screen seal. The two retained packet56 head windows
must still verify, including their distinct process owners and current boot.

The inherited PF_EXITING-aware memory sensor is also used by the chain's
rank and KD supervision. Missing anonymous-memory fields are accepted only
for vanished, dead or kernel-marked exiting tasks. A live task with malformed
memory information still fails. Native wait policy and binary bytes are unchanged.

Only the documented entry points apply. Copied historical helper entry points
are dependencies, not instructions to rebuild or run additional campaigns.
No service, GPU, external validation or submission is started by preparation.
