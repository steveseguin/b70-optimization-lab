# Packet58z coordinator contract

Preparation only. No queue or service was started. Use exactly the environment-
embedded chain_command in ready.json, after rerunning verify_ready.py.
The fresh unit is packet58-onecard-58z-a; the output must not exist before
launch: evidence/card0-58z-a. The marker binds preparation commit and command.

Pause and drain lane B; hold the whole host through K1a → K1b → KD → W2m →
WS → WS128x → WS128, including unchanged 90-second gaps. Every window also
takes whole-host admission. Capture fresh evidence/fault-review-58z.json with
this packet's fault_review.py: exactly two known boot fault lines, unchanged
two-second boundary overlap. New faults stop launches. No capture was made here.

Review 29: **freeze Codex units and block compiles from WS through completion
of WS128**. During K1a through W2m, helper-core CPU work may stay within its
budget, without model/GGUF or full-shape reads. The coordinator owns and
records the freeze; the chain never freezes or restarts other units. Exclude
other model-reading work for the entire whole-host hold.

K1a/K1b/KD: nice19, cores 8–15/24–31. W2m/WS/WS128x/WS128: nice0,
cores 0–3/16–19, as in 58w chain b. One B70, target-only greedy, tile16,
overlapped cache maintenance, zero-copy misses, host-pinned experts.
Max cache allocation AND usage: **21,552,729,600 bytes (21.55 GB)**.
Full BF16 KV, context4096, packet49 iq3-p49-split32-v1. Both K1 windows must
qualify zero-copy; no streamed fallback.

Model-window MemAvailable floor: 98,989,727,744 bytes, from admitted 58x,
with unchanged 8 GiB reserve and 4 GiB shadow stop. No host memory settings
change. Root must retain 25 GB including planned writes. Build: 72,949,256 bytes.

Start each stage once; stop gracefully and retain evidence. No retry loop,
hard kill, resident server, reboot or host-setting change. Only fresh WS128
supplies the new timing value. WS128x is exactness only; strict512 and a fresh
second timing repeat remain false.
