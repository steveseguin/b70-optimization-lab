# Packet183 negative-result index (S1 dense-scales, two-card one-load bracket)

No device result exists yet; this preparation closes nothing. After the window, append the row
from the bracket summary's `s1_decision` (and the waiter's `v5/evidence/waiter-decision.json`).

Checked before work (all stage2 `DO-NOT-REPEAT.md`, notes, IDEAS, packet177's sweep):

* **No row closes S1.** Packet177 (2026-10-19) left S1 open as its recommended build.
* **packet175b D1** (same-bit scale-word multicast in the dense lane): dense B/A 1.0665, closed.
  Different mechanism (no byte cut, adds cross-lane selects); its revisit condition does not
  apply, but its lesson does: per-step lane work is not free in this lane (priced as a risk).
* **packet74** packed Q6_K/Q8 dense + head: -0.8/-2.4/-2.9%, the per-weight 6-bit unpack cost
  more than the bytes. S1 keeps the int8 codes; no unpack.
* **packet175 D2** warm-ahead: closed (warm kernels' own time). Not reused.
* **packet25/packet10-kopt5**: cached FP32 scales were introduced for all formats; no packet
  measured metadata scales against them on the int8 Q6 layout. Packet25's "scale hoisting is not
  new" row concerns IQ expert metadata.
* **packet140 N1 / packet58ao**: scale multicast ranked below the bar; not S1.

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-22 | S1 metadata scales, two-card one-load bracket (expanded/metadata x5, lane B, unit lanequeue-B32, 12:03-12:11 UTC) | **Closed: loss -6.2%.** Controls 58.617/58.587/58.630, S1 54.987/54.985 tok/s; every view 13/13 exact, identical draft proposals, drift 0.072% (`v5/evidence/device-metadata-v5-B-p183/bracket-summary.json`, `s1_decision`). Priced +4.42% floor; measured the same-size loss as packet175b D1 (6.7%) for the opposite byte change: the dense GEMV lanes pay for per-group inner-loop work (one half->float convert and one multiply per 256 weights, three lane copies), not for scale bytes. **S2 (planar 6-bit codes + FP32 scales, packet177 option c) is closed with it**: packet177's rule kept S2 only if B/A <= 0.90 showed near-full byte transfer; measured B/A = 0.938. | A dense GEMV lane whose measured time tracks bytes read (a byte-cut micro that gains, not loses); or a scale path with zero per-group arithmetic in the inner loop |
