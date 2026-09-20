# Packet 84: the 23/25 split is exact and buys 1.9%; the sampler still paces (2026-09-20)

Packet 84 moves the transformer split from 21/27 to 23/25 (per the time-balanced
rebalance in `split-rebalance-design.md`) and adds cross-stage input fingerprints
to the pipeline receipts. Server 84 ran on boot `58ae370e` (the first boot with
C6 / cpuidle state2 disabled at runtime).

| Arm | Prompts | Distinct clips | Exact |
| --- | --- | --- | --- |
| f84-warm | 3 | 0 (fills) | 3/3 |
| f84-tsh | 30 | 27 | **30/30, `all_exact: true`** |
| f84-endure | 120 | 117 | **in progress at this writing** (see §4) |

Every f84-tsh fixture matched its reference byte for byte, including `bird`.
This is the first split change since the graph-capture lineage began: five
inherited packet13 files were replaced with packet13 originals preserved under
`provenance/graph-capture/parent/`, and the launcher gate names them in
`replaced` (manifest `01f521e5f601f4bf816fa7e2ce56e8ec4227aba8f15293b47de5d84e3ee23753`).
The launch-day stop the design note predicted did fire once: the capture gate
pins `ltx_layer_shard.py` by sha256 and rejected the rebuilt shard until the
pin was re-audited and updated (the change is the `DECLARED_SPLIT_INDEX`
constant only; `_dest` routing arithmetic is byte-identical).

## 1. Result: ~1.9% faster, matching the ~2.4% prediction

| | Packet 83 (21/27) | Packet 84 (23/25) |
| --- | --- | --- |
| Steady mean per emitted clip | 1.6625 s (f83c-tsh) / 1.6620 s (f83e-endure) | **1.6311 s** (f84-tsh) |
| Steady p95 | 2.234 s | 2.415 s |
| Effective fps | 14.8 / 15.06 | **15.33** |

The 31 ms gain is within the design note's predicted 30-38 ms. Against the
packet-74 control the whole two-clip pipeline now stands at 1.66 -> 1.63 s/clip;
the design note's estimate of 76-85 ms was too optimistic because the measured
imbalance was 168 ms, not 220-260.

## 2. The sampler paces the pipeline; ~0.6 s/pair sits between sampler nodes

f84-tsh receipts:

- `queued_ahead` is 28/28 and `speculation_miss` is 0/28: the sampler never
  waits for conditioning. Encode is fully hidden.
- The sampler node itself measures 2.65 s/pair (`stage_seconds`), but the wall
  period between emitted clips is 3.26 s/pair. The ~0.6 s/pair difference is
  spent between sampler nodes: run_behind handoff, conditioning consumption,
  receipt writing and Python scheduling.
- Encode `stage_seconds` fell from 5.36 s (f83c) to 3.40 s (f84) per pair of
  encodes, apparently from reduced device contention after moving two blocks
  off xpu:1 — but it never paced anything, so the gain is invisible in steady
  state.

Two consequences:

1. **Three-clip overlap (design doc §3.1)** now has a measured ceiling:
   sampler-busy is 2.65 s/pair = 1.33 s/clip, so perfect overlap of the
   inter-node gap would reach ~1.33 s/clip (~18 fps), not better.
2. Getting under 1.0 s/clip additionally requires the sampler stage itself to
   shrink ~25% (the 6-step phase schedule / deeper fusion work), or the
   inter-node gap to shrink alongside overlap.

## 3. Cross-stage fingerprints are live

The encode stage fingerprints the handed-off conditioning (`conditioning_fingerprint`
in pipeline receipts); the sample worker fingerprints the conditioning, noise
seeds and both input latents at execution time (`emitted_conditioning_fingerprint`,
`emitted_sample_inputs` in sampler receipts). Warm-arm and tsh receipts carry
both. A future wrong clip can now be attributed: if the emitted conditioning
fingerprint differs from the encode-side one, the conditioning mutated in
flight; if they match and the noise seeds are the expected ones, the sampler
left the expected path.

## 4. Endurance: 120/120 exact; the wrong bird clip did not reproduce

f84-endure: 120 prompts, 117 distinct clips, **`all_exact: true`**, steady mean
1.6505 s/clip (15.15 fps effective; the 30-prompt arm read 1.6311). Every bird
clip in the sequence matched its reference byte for byte, including prompt 05's
clip at the fill boundary — the slot that produced the finite-but-wrong clip on
servers 82b and 83e.

The bug is therefore still unexplained and now cleanly bounded: same packet,
same boot, same fixture sequence — 83c clean, 83e wrong, 84 clean. What varies
between those servers is allocation history at load. The fingerprint
instrumentation shipped in this packet is the standing trap: on the next
occurrence, `emitted_conditioning_fingerprint` vs `conditioning_fingerprint`
and `emitted_sample_inputs` will attribute the divergence to the encode
handoff, the noise/latent inputs, or the sampler path itself.

## 5. What the user needs to decide (updated)

1. **C6 is now disabled at runtime** (this boot). It does not persist across
   reboots. The systemd unit or the BIOS "Package C State Limit: C0/C1" /
   "Typical Current Idle" settings are still the durable fix; re-check
   `/sys/devices/system/cpu/cpu0/cpuidle/state2/disable` after every boot.
2. **BIOS: Power Supply Idle Control**, as before.
3. `drm_kms_helper.fbdev_emulation=0`, as before.
4. memtest86+: the host was powered off for ~1.5 h before this boot; whether a
   memory test ran in that window is unknown to the lane. The f84 numbers above
   are promoted as *provisional*: they match the design prediction, but the
   host's two earlier byte-corruption events mean a single clean boot is not
   proof of memory health. A full memtest86+ pass remains the gate for
   treating any sub-5% delta as real.
