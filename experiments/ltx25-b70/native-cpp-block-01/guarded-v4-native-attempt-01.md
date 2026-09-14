# Guarded CPU v4: Comfy import probe refused

2026-09-14. The single root-controlled diagnostic, PID105412 (parent105411),
tool session5978, exited1. It made **zero model or compiler calls**. XPU and
CUDA both remained uninitialized. No new clip or speed result exists.

Root reviewed the full metadata policy and harness delta; an independent
source review found no blocker for this bounded diagnostic. All39 stdlib
tests and the source-only gate passed first. The earlier unchanged v4 source
qualification remains valid, but native compiled-block qualification did not run.

The actual refusal was `torch.xpu.device_count` at
`comfy/model_management.py:127`, imported by `comfy.ops`. Comfy executes this
probe even with `--cpu`, before assigning its CPU state from that option.
Its bare exception handler swallowed the guard's first exception. The sticky
guard retained the attempt and rejected the later metadata-policy binding,
so no eager/compiled block call followed. This is a different import path
from guarded-v2's Kitchen availability query. The v4 metadata omission hook
was installed but never reached a cache-save call.

Evidence:

- [Source check](guarded-v4-source-check-01.json)
- [Result with captured import stack](guarded-v4-result-01.json)
- [Startup receipt saved before Torch](guarded-v4-startup-01.json)
- [Run output](guarded-v4-run-01.log)
- [17:19:46 UTC postflight](guarded-v4-postflight-01.json)
- [17:14:53 UTC full admission](../data/cpu-candidate-preflight-20260914-01.json)

Postflight confirmed the probe absent, identical full LTX endpoint identity,
an empty queue, only the unchanged LTX PID84255 on all four render nodes,
no FAULT latch and no matching new kernel faults. No application restart,
computer action or settings change followed. External evidence remains at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/native-cpp-block-cpu-guarded-v4-01`.

The prepared embedding CPU driver reaches the same import and was therefore
not run. The next separately reviewed successor will refuse this one known
CPU-mode import probe with an ordinary recorded exception handled by Comfy,
without calling the original hardware query. Every other device access keeps
the sticky guard. No unchanged retry is authorized by this note.
