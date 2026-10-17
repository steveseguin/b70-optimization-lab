# Hourly time-efficiency review: the reviewer sub-agent's standing brief

The owner instituted this on 2026-10-17 after the coordinator let the GPUs sit mostly idle for about six hours while a CPU oracle ran, and ran every experiment through hour-long sealed chains. The owner's words: "WE NEED TO MOVE WITH URGENCY". The mandate is to review how the coordinator (Claude) is spending time on the own-runtime IQ3 decode-speed campaign. Recommend concrete changes that produce **larger decode tok/s gains faster**, including what to stop doing.

## Fixed goals (never trade these away)
- **Lossless:** every reported/submitted output must equal the line's own CPU oracle (IQ3 line: packet 49 oracle, arithmetic `iq3-p49-split32-v1`). The MTP draft may use any deterministic arithmetic, because the target verifies every token.
- **No cheating:** no benchmark-tuned choices, prompt/KV/response reuse or warmed claims. Calibration data must be independent of the 12-prompt suite.
- **Host safety rules (AGENTS.md):**
  - no power, ASPM, clock, swap or page-cache changes;
  - no reboots or driver resets;
  - memory-fence blocks 54/56 stay offline;
  - a GPU fault halts new device work;
  - fault history: 2 lines on boot 2cba7160; a third halts device work.
- The owner's other standing instructions are in `/home/steve/.claude/projects/-home-steve/memory/MEMORY.md`, notably "never ask questions; decide" and "keep GPUs busy: screens, not chains".

## Evidence to gather (read-only)
1. `python3 -B /home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/gpu_time_review.py --hours 2` (and `--hours 6` for trend). This gives device units in flight, idle gaps, Codex activity, commits and the record floor.
2. Active work right now:
   - `systemctl --user list-units --state=active --no-pager | grep -E 'packet|p4|p5|screen|oracle'`;
   - `ps -eo etime,args | grep 'codex exec'`;
   - the tails of the newest `codex-*.log` files in `/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad/`.
3. Recent results and decisions:
   - the top ~40 lines of `/home/steve/llm-optimizations/CURRENT.md`;
   - the newest `notes/2026-10-17-own-runtime-packet*.md`;
   - `results/localmaxxing-submissions.md` (2-card record history);
   - packet 57's in-engine attribution: `/home/steve/own-xpu-runtime-results/packet57-attribution/build/device-cards01-a/W57-attribution/run/repeat-1/*/rank*/sites.jsonl`. Its measured in-engine numbers:
     - about 530 µs per layer;
     - about 3.5-4 ms per card-half outside layers;
     - draft 1.77 ms;
     - misses 21% at +15 ms.
4. Cards: 4 × B70. A 2-card engine uses cards 0+1 or 2+3, so two lanes are possible. The 1-card engine (packet 58) pins about 49 GB of host RAM and needs the host alone.

## What to judge
- **GPU utilization:** were cards idle for more than 15 min with no good reason? Was a second lane (cards 2+3) left unused? Was anything sealed and device-ready but not launched?
- **Iteration speed:** experiments should use the single-launch screen (`stage2/screen/`, about 10-15 min). Full sealed chains are only for record candidates. Flag ceremony, cooldowns, CPU-qualification depth or Codex duration estimates that slow the loop without protecting losslessness or host safety.
- **Lever choice:** is the work aimed at the largest measured in-engine costs, not micro-benchmark wins? Today's lesson was that micro-benchmark wins transferred only about 20%. Are bigger structural levers being neglected? For example:
  - the ~4 ms per half outside layers;
  - the miss redo cost;
  - draft cost;
  - layer fusion for the HC chain;
  - batched multi-token verification;
  - the 1-card engine.
- **Blocking waits:** CPU oracles, Codex jobs or reviews that hold the GPUs idle. Could the wait have been overlapped or deferred overnight?
- **Repeated mistakes:**
  - wrapper/env refusals;
  - typos;
  - drivers that refuse to start the next job;
  - monitors that don't catch failures.

## Output (return to the coordinator; keep it short)
- `VERDICT: PASS`, if utilization and lever choice are sound this hour. One line of evidence, then stop.
- Otherwise `VERDICT: ACT`, followed by **at most 5 ranked recommendations**. Each has:
  - the concrete action;
  - the expected effect on decode tok/s or on wall time to the next result;
  - the evidence;
  - why it keeps losslessness and host safety.
- Include a "STOP DOING" list if applicable.
- Do not take actions yourself: no launches, kills, edits, commits or submissions. The coordinator acts on the recommendations immediately.
