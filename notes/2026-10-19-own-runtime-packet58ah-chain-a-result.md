# Packet58ah chain a: WS128 30.05 tok/s, below the one-card record, not submitted; one preregistered quiet-host rerun

Chain `packet58-onecard-58ah-a` ran 00:17:47–00:41:27 UTC on 2026-10-19, boot 2cba7160, card 0, whole host. It is packet58ad plus the packet58ag ports: HC-wide, p109 other-fusion and the E1 scale cache. All seven windows passed (K1a, K1b, KD, W2m, WS, WS128x, WS128), and all 12 prompts were exact in both timing windows. The GPU fault count was 2 before and after. The waiter ended clean.

| Window | Class-balanced tok/s | Process major faults (1,536 tokens) | Minor faults |
| --- | ---: | ---: | ---: |
| WS128x (exactness window) | 31.536 | 124 | 26,016 |
| **WS128 (timing window)** | **30.050** | **3,736** | 22,404 |

WS128 is the timing result. It is **below the record 30.395631** (`cmvefq3ep009orf0186k21lba`), and `packet58_submission.py` refused it ("not above matching one-card threshold"). **Nothing was submitted.**

The bracket that qualified the composition (packet58ag, one load, 23:56–00:08) measured:
- p60fusion views: 31.631 and 31.620;
- warm production controls: 30.585 and 30.511;
- gain: +3.38% strict, with 0.24% drift, 60/60 exact.

## Why WS128 is low (coordinator finding, not a measured proof)

- Both windows are fresh processes with the same binary, selection and admission, 90 s apart.
- WS128 took **30× more major page faults**. They are concentrated in the prompts that are slow in WS128:
  - risk-register 940, technical-guide 662, bug-report-synthesis 596, performance-hypotheses 500;
  - WS128x: 0–27 per prompt.
- The one-card engine's ~29 GB PLE and embedding tables are file-mapped. Packet58q found that host page faults drive one-card variance.
- The WS128 slowdown is therefore host paging of those tables, not the engine.
- MemAvailable during decode was 66–67 GB in both windows. What evicted the pages is unknown. Kernel log: no lines.
- Codex units were frozen from WS (00:27:43) to the end. Four Codex CPU jobs (p151b, p152, p153, p58ai) were active during K1a–W2m (00:17–00:27). Their file reads there could have shifted the page cache. This is not proven.

## Preregistered rerun (written before any rerun)

- Exactly **one** rerun of the identical packet58ah chain, in a fresh chain folder `card0-58ah-b`, unit `packet58-onecard-58ah-b`. The command differs only in those two names. A fresh handoff (Codex p58ahb) keeps the chain-a evidence untouched.
- **Host rule for the rerun:**
  - every Codex unit is frozen from **before K1a** until the chain ends;
  - no other CPU work that reads the model runs;
  - lanes A and B are paused and drained, as before;
  - no cache drops, page-cache settings or pre-touch reads, so the host is left as the chain finds it.
- The rerun's WS128 is **final** for packet58ah, whichever way it lands. It is submitted only if it exceeds 30.395631. There is no third run, and no choosing between a and b.
- A submission discloses chain a (WS128 30.050, not submitted), its major-fault count and the reason for the rerun.

Evidence: `experiments/own-xpu-runtime/stage2/packet58ah-onecard-record/evidence/card0-58ah-a/` (window.json/summary.json per window; per-token faults in `WS128*/run/run/*/timings.jsonl`).
