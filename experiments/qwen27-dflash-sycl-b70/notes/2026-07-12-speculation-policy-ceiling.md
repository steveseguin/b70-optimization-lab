# 2026-07-12 speculation policy ceiling

## Conclusion

No MTP width, confidence threshold, n-gram combination, or DFlash routing
policy can take the current single-B70 executor above 68 tok/s on the fixed
mixed realistic suite without making target verification faster.  The hard
limit is the verifier cycle, not a missing routing choice.

## Exact MTP3 ceiling

The strict 538-cycle trace measured 56.848 ms per cycle and 2.7881 emitted
tokens per cycle (962/1613 draft candidates accepted, 59.64%).  At the same
cycle cost:

- 68 tok/s requires 3.8657 emitted tokens/cycle.  With MTP3, whose maximum is
  four emitted tokens, this requires about 95.5% draft acceptance;
- current acceptance produces about 49.0 tok/s from the reconciled cycle
  timings (the associated strict headline was 51.694 tok/s);
- even perfect MTP3 acceptance produces only 70.36 tok/s, leaving almost no
  practical margin above 68;
- deleting the entire 9.7 ms draft phase while keeping measured acceptance
  produces only about 59.1 tok/s.

The best prompt in the trace emitted 3.125 tokens/cycle, which is only about
55.0 tok/s at the measured cycle cost.  Prompt-genre routing therefore cannot
turn the current mixed suite into a 68 tok/s result.

## Focused early-stop validation

Two four-card strict experiments tested only the confidence boundaries needed
to decide whether adaptive early stopping could exchange fewer emitted tokens
for a materially cheaper verifier.  All rows passed the realistic gate and
reported cached tokens zero.

| policy | headline tok/s | verifier width histogram | emitted/cycle in instrumented speculative cycles |
| --- | ---: | --- | ---: |
| MTP3, p_min 0.025 | 49.840 | M2=1, M3=1, M4=542 | 2.757 |
| MTP3, p_min 0.05 | 48.772 | M2=2, M3=2, M4=542 | 2.745 |
| MTP3, p_min 0.10 | 50.895 | M2=3, M3=3, M4=539 | 2.752 |
| MTP3, p_min 0.20 | 48.810 | M2=4, M3=8, M4=530 | 2.758 |
| MTP3, p_min 0.40 | 49.543 | M2=78, M3=87, M4=359 | 2.763 |
| MTP3, p_min 0.60 | 45.694 | M2=171, M3=126, M4=189 | 2.706 |
| MTP3, p_min 0.80 | 41.274 | M2=215, M3=120, M4=102 | 2.648 |
| MTP2, p_min 0 | 47.407 | M2=1, M3=644 | 2.333 |

Thresholds through 0.20 almost never shorten the verifier.  Higher thresholds
do shorten it, but force enough ordinary/no-draft target cycles that headline
throughput falls.  MTP2 also loses.  A hindsight oracle allowed to select the
best of all eight policies separately for each of the twelve prompts reaches
only 52.245 median tok/s (50.360 mean), so a workload classifier cannot recover
68 from these policies.

Artifacts are the `qwen27-mtp3-policy-clean-*` and
`qwen27-policy-clean-*` run directories under
`/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/`, with result
summaries in `data/qwen36-27b-mtp-gguf-q4-b70-baselines/`.

## DFlash and n-gram routing

DFlash remains useful only as a diagnostic genre-specific ceiling.  Its
existing fixed mixed-suite result is 11.505 tok/s, and its larger blocks make
the target verifier cycle larger.  That violates the condition of finding a
policy win without enlarging verification.  N-gram/history acceleration is
disallowed by the strict cold headline policy; it also cannot be combined
with a promoted mixed-suite result as a hidden cache/history route.

Keep production policy at MTP3 with a low confidence floor (0 to 0.10 is the
noise-equivalent band).  Do not spend further runs on p_min or MTP2.  Revisit
DFlash routing only after the multi-row target verifier is substantially
faster.  At current acceptance, 68 tok/s requires a cycle at or below 41.0 ms;
at current non-target cost that means target M=4 verification below about
29.8 ms.
