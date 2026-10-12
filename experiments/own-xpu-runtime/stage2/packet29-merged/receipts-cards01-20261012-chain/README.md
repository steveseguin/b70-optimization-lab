# Packet 29, sealed chain on cards 0+1 (2026-10-12 00:28 – 01:28 UTC): 22.49 tok/s, exact

K0, K1a, K1b (two fresh owners), K2 (per-class timing with rotated full-size buffers for
the heavy classes, selection), W0 (two-card canary), W2m (two-card decode with K2's
selection) and W2c (the same with per-class GPU timing) passed through the packet's own
wrapper. Clean kernel log throughout (no `xe` line).

| Run (UTC) | Dispatch | tok/s | ms/token | host enqueue loop | waiting | token preparation | launches | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| [W2m](w2m-r29/window.json) 00:58 | K2 measured | 21.74 | 45.9 | 18.1 | 26.5 | 0.56 | 2,307 | 64/64 tokens, 384/384 layers |
| [W2m, repeat](w2m-r29b/window.json) 01:26 | K2 measured | **22.49** | 44.3 | 12.4 | 30.7 | 0.59 | 2,307 | 64/64, 384/384 |
| [W2x](w2x1-r29/window.json) 01:12 | measured + 3 small fusions | 19.58 | 50.5 | 22.6 | 22.0 | 4.93 | 1,935 | 64/64, 384/384 |
| [W2x, repeat](w2x1-r29b/window.json) 01:19 | measured + 3 small fusions | 18.89 | 52.9 | 16.3 | 26.9 | 9.01 | 1,935 | 64/64, 384/384 |

Every run is bit-exact against the v2 oracle. The spread is host noise, not kernels:

- **The repeats ran pinned to four reserved cores** (`taskset -c 0-3,16-19`), with the
  CPU-only helper jobs moved to the other cores. The first two ran unpinned while up to
  22 cores of CPU gates were running (load average 12–25).
- **Token preparation** (embedding and PLE row lookups from the memory-mapped model
  file) took 0.5 ms per token at 00:58 and 01:26 and 3.7–9.0 ms in the three runs
  between 01:04 and 01:21, with either dispatch ([W2c](w2c-r29/timings.jsonl) had 3.7 ms
  with the measured dispatch). In that interval another CPU job was reading the model
  file; the lookups were page-faulting. It is a property of the host at that time, not
  of the dispatch.
- **Host issuing** cost 5.4 µs per launch in the quietest run (01:26) and 7.8–11.7 µs in
  the others. The GPU waits for the host between small kernels, so this shows up in the
  token time.

Without the preparation faults the two dispatches are equal within this noise (43.1 and
43.2 ms of enqueue+wait in the two pinned runs). They cannot be ranked from these runs.

**GPU time per token: 41.2 ms** over 2,307 launches ([W2c](w2c-r29/class-times.json);
packet 27: 47.7 ms over 1,898). Largest classes: expert down 6.25 ms (48 × 130 µs),
expert gate/up 4.02 (was 8.62), route 3.27, QSA attention 3.18, gdn.qkv 2.81 (was 3.31),
attention projection 2.56 (was 3.23), gdn.z 1.73, logits 1.68, gdn.recurrence 1.23,
qsa.qgate 1.10, hc gates 2.13 (was 2.89).

**What K2 selected** ([table](k2-table.txt), [selection](k2-r29/dispatch-measured.json)):
`p28.paired.wg32` for expert gate/up (175 → 82–84 µs with rotated buffers), `p28.dense`
variants for every dense GEMV class (gdn.qkv 98 → 75, gdn.z 62 → 48, logits 2,590 →
1,880, hc gates 27.6 → 20.6 …). **Expert down has no winner**: the two new kernels
measured 123 µs against 127; every other candidate was slower (150–183 µs).

**A flaw in K2's selection rule.** The three small merged-GEMV fusions won their own
comparisons (HC low+inject 32.3 → 15.6 µs, GDN a+b 14.3 → 4.6, router + shared expert
gate/up + scalar gate 43–45 → 20.5/14.7) but were disabled because their member GEMVs
also won individually, although the fusion is cheaper than the sum of the selected
members (20.1, 7.2 and 32.5 µs). The measured dispatch therefore issues 409 more
launches than necessary. [dispatch-x1-fusions-restored.json](dispatch-x1-fusions-restored.json)
is the assembled alternative used by the two W2x runs. Packet 35 fixes the rule.

Progression of the exact two-card decode: 3.15 → 12.08 → 17.85 → 19.63 → 22.49 tok/s.
Reference 28.49.
