# Packet118: record bundle 7

Frozen packet111 copy after packet111r. Exactly two sealed compositions:

- Bundle 6: packet103 + packet109 other-fusion + packet105b target-head split;
  draft prefix 91,392 rows.
- Bundle 7: the same bundle with packet114's fixed 80,128-row draft prefix.

Only draft prefix selection is added. The row reduction, argmax tie rule,
complete target head, target verifier and BF16 KV stay unchanged. No second
head allocation or upload is introduced. KD recomputes the draft host reference
for the selected N and retains the original target captures.

[Prefix preregistration](prefix-calibration/preregistration.json) and
[selection](prefix-calibration/selection.json) are copied from packet114.
They used non-benchmark text; N must never be retuned from benchmark data.
The inherited `calibration/` and coverage metadata retain their original bytes;
they are historical metadata, not the new prefix selection authority.

First proposal: [`proposed-p118-smoke-B.txt`](../../ops/lane-queue/proposed-p118-smoke-B.txt),
all twelve cold prompts × 64 tokens, every token exact to `iq3-p49-split32-v1`,
including the known suffix-token regression. Only the coordinator may execute.
CPU gates are not device quality or performance evidence.

Run CPU preparation with `nice -n 19 taskset -c 8-15,24-31 python3 -B
cpu_prepare.py build_engine.py cpu_gate.py full_shape.py prepare_chain.py
startup103.py prepare_packet.py propose_smoke.py </dev/null` from this folder.
One compiler at a time uses packet94's turn. CPU entry processes alone impose
resource caps. Root free-space floor is 25 GB; preparation build cap is 250 MB.

The [orchestration](../../ops/packet118-orchestration/README.md) compares the
packet103 bundle5 record line against bundle7. Both lanes must clear +1.0%
over both controls, with exact prompts and a passed smoke, before the fresh
record chain can become ready. Use its finalized submission entry.

[Work note](../../../../notes/2026-10-18-own-runtime-packet118.md) ·
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md) · [retention](RETENTION.md).
