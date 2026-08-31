# Qwen3.8 projection-repair strict D54 result

D54 passed the first non-instrumented strict qualification.

- All 12 unique prompts across six classes completed once; cached tokens were
  zero in every row and the workload gate passed.
- The median of prompt-class medians was **24.804756 tok/s** target-only TP1.
  Class medians ranged from 24.624696 to 24.956678 tok/s.
- Arithmetic, exact-copy, JSON-schema, and eight-repeat greedy determinism
  canaries all passed; the repeat test had one output class.
- Shutdown was clean and the bounded kernel journal had no matching GPU, OOM,
  filesystem, or I/O fault.

This is valid candidate evidence, not yet a promoted headline. D55 repeats the
complete suite in a new process/cache and requires all twelve complete token-ID
sequences to equal D54. The synchronized repair is a correctness baseline; its
barriers and padded-prefill cost still require optimization before restoring
the TP2/MTP performance lane.
