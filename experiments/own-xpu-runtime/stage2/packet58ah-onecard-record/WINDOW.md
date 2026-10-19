# Packet58ah coordinator contract

Preparation only. This is the single quiet-host rerun preregistered in
notes/2026-10-19-own-runtime-packet58ah-chain-a-result.md. Chain b is final
whichever way it lands: no third run and no selection between a and b.
The original same-hold instruction applied to chain a; this authorized rerun
requires one new uninterrupted whole-host hold across all seven windows.
Rerun seal.py --verify and verify_ready.py --output ready.json before launch.
A preparation marker is not a smoke/bracket pass. Missing or failed evidence
refuses the chain. Do not launch unless ready.json says ready=true.

Use exactly the environment-embedded chain_command in ready.json.
Unit: packet58-onecard-58ah-b.
Fresh output: evidence/card0-58ah-b (must not exist).
Capture fresh evidence/fault-review-58ah-b.json using this packet's
fault_review.py immediately before the chain. The command names this same path.
The unchanged review admits exactly two known boot fault lines and preserves
the two-second boundary overlap. New faults stop launches.

Pause and drain both lanes; retain the whole host throughout
K1a → K1b → KD → W2m → WS → WS128x → WS128 and the 90-second gaps.
Freeze EVERY Codex unit and block compiles from BEFORE K1a through WS128
completion. The coordinator records the freeze before launch. No other CPU
work reading model/GGUF or full-shape data is admitted during the hold.
No cache drops, page-cache settings or pre-touch reads. The generic waiter
only freezes at WS: its --check mode validates the handoff, but its normal
mode alone does not satisfy this preregistered before-K1a freeze requirement.

K1a/K1b/KD: nice19, cores 8–15/24–31.
W2m/WS/WS128x/WS128: nice0, cores 0–3/16–19.
One B70, target-only greedy, --hc p60fusion, --hc-geometry hc-wide,
--experts wide64+halfcache, --other-fusion fused,
--retirement ordered-foreground, tile16, overlapped maintenance,
zero-copy misses and host-pinned experts. Both K1 windows must qualify
zero-copy; no streamed fallback. Cache allocation AND usage: 21,552,729,600
bytes. Full BF16 KV, context4096, packet49 iq3-p49-split32-v1.

The native engine and tile16 selection are bound to final packet58ag outputs
by hash. The full composition uses the explicit runtime flags above; do not change
selection JSON to invent a dispatch choice. No rebuild or parent edit.

Model-window MemAvailable floor: 98,990,252,032 bytes, with the unchanged
8 GiB reserve and 4 GiB shadow stop. No host memory settings change.
Root must retain 25 GB after planned writes. Preparation adds at most 100 MB; five reused binaries total 73,442,424 bytes.

Start each stage once, stop gracefully and retain evidence. No retry loop,
hard kill, resident server, reboot or host-setting change. Only fresh WS128
supplies the new timing. WS128x is exactness only; strict512 and a fresh
second timing repeat remain false.
