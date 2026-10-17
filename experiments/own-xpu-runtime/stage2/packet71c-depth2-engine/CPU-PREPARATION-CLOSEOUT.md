# Packet71c router configuration repair — CPU closeout

<!-- campaign-closeout -->

## Question and identity

Can the packet71 depth-two candidate pass real native startup with production
shapes while preserving `iq3-p49-split32-v1` per-row arithmetic? October 17,
2026, steve-b70s; CPU only. Frozen parent: packet71b, identified by
[copy manifest](packet71-copy.json). No model payload reads or device execution.

## Outcome

Disable only `small.ffn` in the new candidate. Both native builds pass. GNU and
Intel each pass 2,728 M2 operator checks and 80 grouped-versus-standalone checks,
with cross-compiler byte agreement. Five full-shape views pass both ranks,
including native parsing, allocation admission and paired command capture.
The old dispatch reproduces the precise router refusal as a negative control.
The copied control selection and existing production files are unchanged.

## What worked

Full geometry is necessary: the synthetic mini path skips M=2 admission.
Calling the real `Rows::capture_pairs` detects this issue before device contact.
Every plan now runs the hash-bound mock executable and checks its real memory
census, in addition to importing the deferred worker modules.

## What failed or remains uncertain

Packet71b's plan imported workers but never exercised native M=2 setup. Its
claim that shared-up epilogues prevented the small tuple was wrong for the
actual production plan. The sealed dispatch was incompatible. This repair
makes no device quality, determinism or speed claim. Standalone projections
add command overhead; only the coordinator's matched screens can judge it.
The inherited private wrapper is copied with this packet; it is not a change
to shared v4 or any live wrapper.

## Evidence and patches

[Dispatch](dispatch-speed6.json), [full-shape gate](evidence/fullshape.json),
[unfused byte gate](evidence/unfused.json), [M2 bytes](fixture/m2-receipt.json),
[worker import evidence](evidence/worker-import-check.json),
[queue plans](evidence/lanequeue-plan.jsonl), [retention](RETENTION.md).
The original device failure remains under frozen packet71b's
`screen/evidence/smoke-B/run/ranks/` on this host.

## When to revisit

The coordinator runs smoke-B, then control-B/candidate-B/control-repeat-B.
A new config or kernel change requires the same full-shape and byte gates.
A fused M=2 FFN implementation is a separate lever only if measured command
cost justifies it. No device work is authorized by this CPU closeout.
