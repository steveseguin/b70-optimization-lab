# Qwen3.8 27B Q8 TP2 peer-collective cache hints

Date: 2026-08-16

Status: active on the two-ASRock-B70 reference host; do not duplicate unchanged
until this note is closed.

## Hypothesis

The accepted TP2 stack performs 128 already-fused collective boundaries per
generated token.  Its root vec4 reduction kernel reads the second B70's
peer-mapped partial and writes the completed sum back to that peer mapping.
Those one-use transactions should not displace reusable local data from cache.
Intel's compile-time SYCL `annotated_ptr` cache controls can express streaming
or uncached policy on only those peer operations without changing arithmetic,
ownership, launch count, or synchronization.

This is distinct from the closed reordered-Q8 weight cache-policy arm in the
Qwen3.6 pass-2 notebook.  That arm changed high-volume local weight reads;
this arm changes only the cross-device `p1` vec4 read/write in the accepted
root reduction.

## Contract

- accepted Qwen3.8 27B Q8_0 TP2 target-only stack and model identity;
- selector `level_zero:1,0`, `SYCL0/SYCL1`, equal tensor split;
- F16 KV, flash attention, batch 1024 / ubatch 256;
- same binary exposes incumbent, streaming, and uncached peer policies;
- first require a quality-exact smoke and evidence that the treatment door is
  live, then use a position-balanced control/treatment decode bracket;
- promote only a repeatable gain followed by the complete cache-zero fixed
  suite, exact-output hashes, semantic canaries, and long-context needle gate.

The experiment must be stopped and recorded as unsafe if the current boot
shows a Xe reset, hang, timeout, or device-lost event.  This arm does not use or
revive quarantined collective mode 3.
