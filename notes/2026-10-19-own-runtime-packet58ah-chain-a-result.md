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

## Packet58ahb — final quiet-host chain-b handoff

CPU-only preparation on October 19. The frozen-path tool passed (58,240 paths);
an ownership check of all 36 other active/ready packets found no pins into
packet58ah. The handoff is therefore resealed in place. Chain a's original
seal, submission pins, coordinator readiness snapshot and marker bytes are
retained under `lineage/58ah-chain-a-*`. Its evidence, fault review and original
marker bytes remain unchanged; the active orchestration marker becomes the
chain-b handoff only as the final content write.

The unit is `packet58-onecard-58ah-b`, output `evidence/card0-58ah-b`, and fresh
review `evidence/fault-review-58ah-b.json`. The exact command changes only the
unit and output names plus that required fresh fault-review path. Selection,
all five native binaries, oracle, seven windows, 90-second gaps, admission,
pinned 30.395630964654867 record and readiness policy are unchanged. Binary
bytes were hashed only. Outputs must still match `iq3-p49-split32-v1` exactly.

The submission tool admits only chain b and refuses chain a before reading
its evidence. Notes, result and ledger entries always disclose chain a's
**30.050 tok/s**, **not submitted**, **3,736 major faults versus 124 in WS128x**,
and the suspected host-paging disturbance as the reason for the preregistered
quiet-host rerun. That cause remains unproven. Chain b's WS128 is final
whichever way it lands; no third run and no choosing between attempts.

All **134 passive/mocked tests**, **seven actual queue-to-native entry probes**
and **28 wrong-unit/environment refusals** passed. Entry probes used the real
chain-b environment and unit gate, with native execution intercepted. The
specific old chain-a unit and submission-path refusals passed. The submission
rehearsal passed from the final location with no repository-root override or
network; notes are 1,711 characters. Its inherited packet58ad timing remains
labeled rehearsal evidence, never a chain-b measurement.

The minimal 287-source seal verifies. The passive seven-window plan passes,
and `verify_ready.py` now returns true on the completed packet58ag smoke and
five-view receipts under the unchanged policy. Peak observed test/probe/
rehearsal memory was 158,302,208 bytes, below the 2 GB budget. The inherited
optional literal helper exposed a pre-existing missing `template_symlinks`
manifest key; it wrote no receipt. A focused passive check verified the new
live chain identities and the absence of symlinks instead. No native parser,
full-shape proof, model/GGUF read, compilation, GPU job, service, sudo, setting
change, live queue edit or submission was performed.

[Light checks](../experiments/own-xpu-runtime/ops/packet58ah-orchestration/58ahb-light-gates.json)
include the unchanged identity hashes and command comparison;
[readiness replay](../experiments/own-xpu-runtime/ops/packet58ah-orchestration/58ahb-readiness.log)
retains the parent gate. Command SHA-256 (UTF-8, no trailing newline):
`d36bd16bd9335bebcb8d01d9bc177285a908b53ac0d38f87fcb3e9e096c2268f`.

The coordinator must pause/drain both lanes, capture the fresh review and
freeze **every Codex unit before K1a through completion**, excluding other
model-reading CPU work and compiles throughout. No cache drops, settings or
pre-touch reads. The generic `onecard-chain.sh --check` can validate this
handoff; its normal watcher freezes only at WS, so the coordinator must
arrange the earlier freeze separately. This preparation starts nothing.

Pull refused the unrelated dirty tree; fetch confirmed HEAD == origin/main.
Preparation uses explicit-path `git commit --only` and an immediate push.
Then [READY-FOR-DEVICE.json](../experiments/own-xpu-runtime/ops/packet58ah-orchestration/READY-FOR-DEVICE.json)
is the last content write, binding that pushed preparation commit. The
requested waiter `--check` runs read-only after it, and the marker is committed
and pushed separately. No chain-b evidence directory has been created.

## Chain b result (final) — submitted

The quiet-host chain `packet58-onecard-58ah-b` ran 00:52:18–01:16:19 UTC. Every Codex unit was frozen from before K1a, both lanes were paused, and the waiter ended clean. All seven windows passed and were exact.

| Window | Class-balanced tok/s | Major faults | Minor faults |
| --- | ---: | ---: | ---: |
| WS128x | 31.027 | 2,079 | — |
| **WS128 (final)** | **31.663** | **24** | 26,114 |

- WS128 is 31.662719 tok/s, +4.17% over 30.395631.
- **Submitted** 01:20 UTC: HTTP 201, `cmvekebvh00a0rf01q3v2c3cz`, APPROVED.
- The submission discloses chain a.
- Receipt: `data/localmaxxing-responses/2026-10-19-packet58ah-chain-b-onecard-ws128.txt`.

Even with everything frozen, WS128x took a paging hit (2,079 major faults). So the freeze does not control which fresh window pays for host paging. This confirms review 35's point: the fix belongs in the engine (packet58aj, resident lookup copies), not in reruns. There will be no further quiet-host reruns.
