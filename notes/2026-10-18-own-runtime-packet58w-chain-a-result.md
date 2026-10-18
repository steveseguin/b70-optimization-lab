# Packet58w chain a: 25.77 tok/s, below the one-card record, not submitted; one preregistered quiet-host rerun

Chain `packet58-onecard-58w-a` (packet58w = packet58v overlapped cache maintenance on the tile16 one-card line; card 0, whole host), 18:12–18:37 UTC October 18, boot 2cba7160, GPU fault count 2 before and after. All seven windows passed (K1a, K1b, KD, W2m, WS, WS128x, WS128) and all 12 prompts were exact against packet49 in every model window. Evidence: `stage2/packet58w-onecard-record/evidence/card0-58w-a/`.

| Window | Class-balanced tok/s | Per-prompt range |
| --- | ---: | --- |
| WS128x (exactness window) | 28.078 | 26.66–29.83 |
| **WS128 (timing window)** | **25.773** | 22.62–28.55 |

WS128 is the only timing result, and it is **below the record 26.228599** (`cmvdukc200064rf01lqsql9x8`). **Nothing was submitted.**

## Why WS128 is low (coordinator finding, not a measured proof)

- The two windows ran back to back as fresh processes with the same binary and selection, so they should match.
- WS128 is slower on almost every prompt, and the late prompts are worst (23.87, 23.49, 22.62).
- During the chain, three Codex CPU jobs were active (p141, p58xb, p58y). Compiles were correctly blocked by `compile_turn` (p141 logged "Waiting for compiler turn: hold-lane-B").
- p58y was running its full-shape CPU gates, which read the model GGUF. The one-card engine's 29 GB PLE and 0.5 GB embedding lookup tables are file-mapped, and packet58q found that host page faults drive one-card variance. The coordinator's rule "no whole-host windows while Codex runs heavy CPU workers" was not enforced for this chain; that was a coordinator mistake.
- The bracket that qualified packet58w (packet58v, 17:50–18:04) measured overlap at 28.116 / 28.153 vs warm serial 26.053 / 26.079.

## Preregistered rerun (written before any rerun)

- Exactly **one** rerun of the identical packet58w chain, in a fresh chain folder `card0-58w-b`.
- Host rule for the rerun: every Codex unit is frozen (`systemctl --user freeze`) from before K1a until the chain ends, and no other CPU work that reads the model runs. Lane B is paused and drained, as before.
- The rerun's WS128 is **final** for packet58w, whichever way it lands. It is submitted only if it exceeds 26.228599. No third run, and no choosing between a and b.
- A submission discloses chain a (25.773, not submitted) and the reason for the rerun.

Rule from now on: during every one-card timing window (WS, WS128x, WS128) and every one-card bracket, all Codex units are frozen, not just compile turns.
