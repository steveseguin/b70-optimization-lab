# 2026-10-22: packet184, saving and restoring a two-card session (CPU preparation only)

## What this is

The own runtime can already save a running conversation on one card and pick it up later in a new
process, bit for bit (packets 179–181, qualified on device today). Packet184 does the same for the
**two-card** engine, the line that holds the two-card record (packet136 bundle 8, 58.80 tok/s). It is
item 1 of the follow-up list in `experiments/own-xpu-runtime/SESSION-SWAP-DESIGN.md` §10.

**Nothing has run on a GPU.** Everything below was built and tested on the CPU. The checkpoint is
labelled `experimental-two-card` until two lane-B rows pass on device. Packet:
[`experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/`](../experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/README.md).

## What a two-card checkpoint holds

Each card runs half the model in its own process. A checkpoint is one folder with one blob folder per
card and a single `manifest.json` that names both cards' files with their hashes. The manifest is
written last, so a save is either complete for both cards or invisible. A restore checks both cards'
files before either card loads anything back.

At the size used by the device rows (a 343-token session) a checkpoint is 128.8 MB: 93.7 MB for card 0
and 35.1 MB for card 1. Card 0 keeps three copies of its recurrent (GDN) state, because the record
line's speculation uses three banks; two of those copies are not needed after a pause, but they are
saved anyway (59 MB). At the full 4096-token context a checkpoint is 244 MB.

## The draft (MTP) state is saved, not rebuilt

The record line guesses the next token with a small "draft" model block that has its own memory of
the conversation. That memory is built from the main model's internal state at every past position,
which the main model does not keep. So the draft memory cannot be rebuilt from the rest of the
checkpoint without re-reading the whole conversation. Packet184 saves it (0.8 MB at 343 tokens) plus
the one main-model value the draft needs for its next step. A CPU test shows the difference: with the
draft memory zeroed, the main model still produces the right words (it checks every guess), but the
draft memory stays empty; with it saved, everything matches the uninterrupted run.

## How it was checked on the CPU

* The packet copies packet153 (bundle 8 plus the one-load harness) and changes only the entry source
  file. Before the change, the copy rebuilt packet153's device binary byte for byte; after it, all 78
  inherited kernel objects are relinked unchanged. Device binary `ebbc9b15…c7c5`.
* 56 real two-process sessions on the CPU (small synthetic model): save, restart in new processes,
  restore and continue. Every saved buffer on both cards came out byte-identical to an uninterrupted
  run at the same point, for resume, for appending a new turn, and for saving again after a restore.
  21 kinds of damaged or mismatched checkpoints were all refused before anything was loaded.
* The engine's own list of its state was compared with what the checkpoint saves or skips: they match
  exactly on both cards, at small and at full model size.
* At full model size (no real weights, fake device addresses), both cards start up, save, restore in a
  new process and take one real step; their prepared GPU commands after a restore are identical to a
  fresh engine at the same point, and a fresh start is identical to the parent binary.
* The device worker and its report were rehearsed with real CPU sessions; the queue planner passed
  both rows; the pin guard found 0 cross-packet pins.

## What runs next (proposal only, not queued)

`experiments/own-xpu-runtime/ops/lane-queue/proposed-p184-two-card-B.txt`, lane B (cards 2+3):

1. **smoke** (~4–8 min, two model loads): an uninterrupted 384-token run, then a run of 256 tokens
   that is saved; a new process restores it and writes 128 more. The 256 + 128 tokens must equal the
   384, and the draft guesses must match too.
2. **lifecycle** (~6–13 min, three loads; needs the smoke): append a new 126-token turn to the restored
   session, save again, resume that, and repeat the append in an already-running process; the saved
   state after the append must be byte-identical to a fresh run of the same text.

Admission: endpoints on the lane stopped, MemAvailable ≥ 105,411,248,128 B + 1 GiB, PAUSE-A held,
≥ 25 GB disk plus 1.0 / 1.5 GB planned writes.

## Limits

No device result. The device binary was never executed. The small CPU model always outputs the same
token, so the CPU proof rests on byte equality of the saved state, not on the words. Only the record
card layout is supported, only same-binary restores, no ctxkeeper adapter yet.

## Device result (2026-10-22, lane B window, unit lanequeue-B33, rows 14:23-14:35 UTC): both rows passed

**Smoke** (`v5/evidence/device-smoke-B-p184/summary.json`, 11/11 gates): uninterrupted 384-token reference
(oracle-128 exact); save at K=256 (position 342): 128.8 MB in 1.85 s (rank 0 93.7 MB / 141 blobs, rank 1
35.1 MB / 75 blobs, commit 0.40 s); a fresh process pair restored it in 2.32 s (precheck 0.25, verify
0.36 + 0.18, apply 0.015 + 0.009) and produced the first token 92 ms later (2.41 s restore-plus-first-token
against a 59.3 s cold prefix); merged K+M == the uninterrupted reference, draft guesses equal. Decode after
the resume 56.4 tok/s vs 59.6 in the reference process (cold expert cache of a fresh process, as on one card).

**Lifecycle** (`v5/evidence/device-lifecycle-B-p184/summary.json`, 23/23 gates): append of the 126-token
turn to the restored S1 (1.77 s, 14.0 ms per appended token, vs 6.16 s for the cold new prompt), append ==
one-shot new reference [0:M]; save S2 after the append (136.6 MB, 1.90 s); resume S2 in a third process pair
== the one-shot reference; warm-process repeat append == append; draft guesses equal in both windows;
**S2 state == one-shot SREF state on both ranks (216 blobs, none differing, token state equal)** and the
repeat save S2b == S2 byte for byte; lineage, delete and the TP1/TP2 saved-history agreement
(`9548ca50…`, pending token 37574) all passed. Label stays `experimental-two-card`, contract `v1.2+p184`;
the qualified label is a new packet (as packet181 did for one card). No faults in the window; endpoints
restored afterwards as `*-20261022-restore9`.
Window receipts (shared with packet185): `experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/lineage/window-20261022/`.
