# FP8/MTP recovery and bounded metadata validation

User authorized this follow-up after the failed communication experiment:
restore reliable FP8/MTP service, then validate the smaller metadata change.
This is a new campaign; the earlier fault latch, source and evidence stay frozen.

## Admission and order

1. Preserve passive host/journal/ownership evidence and review the incident.
   The host has been quiet for over 40 minutes, with no device owners or model
   listeners and no later GPU fault signature. No reboot or driver reset is
   proposed. The faulted custom communicator remains quarantined.
2. Run one bounded health probe in the last qualified immutable runtime:
   two-card discovery, per-card copy/compute and standard XCCL all-reduce.
   Hold the exclusive host lock, monitor the new journal window, stop on the
   first fault/timeout, preserve exact container identity and confirmed exit.
   No active health retry and no custom IPC implementation.
3. If health passes, restore the qualified FP8/MTP1 package on port18124 in
   `recovered-service`, with its exact model, arithmetic, FP16-family KV,
   settings and immutable image. Validate known outputs against frozen evidence.
4. Resolve current upstream again before metadata development. The prepared
   campaign needs its separate refreshed image and worker extension; it cannot
   attach to the qualified service. After successful restoration, one deliberate
   replacement uses localhost18129 for the prepared experiment. Preserve source
   identity, model identity and all accepted overlays. If upstream has changed,
   re-review rather than silently use a stale image as latest.
5. Run the prepared full metadata campaign: independently qualify the new base,
   36 native cases on both ranks, then control/candidate/control/candidate with
   full 12-prompt varied natural completions and 512/2K/16K continuation profiles.
   Exact complete numeric outputs, cache zero, native metadata fields/aliases,
   determinism, class-balanced decode, server prefill and HTTP TTFT remain
   separate mandatory checks. No DFlash, quantization change or quality waiver.
6. A quality failure halts that client. Device faults halt the campaign. Neither
   triggers automatic retries or application cycling. The root reviews each
   transition; no unattended chain starts a successor server.
7. If the experiment completes with healthy devices, stop its owned server once
   and restore the original qualified service in `final-service`. A within-process
   gain remains a screen until independent-process confirmation is possible
   under the stability policy. Leave the original public defaults intact unless
   all promotion gates are actually satisfied.
8. Preserve all outcomes, publish the result and relevant website/package links,
   verify CI/live files, and report the endpoint and any concrete remaining gates.

Raw root: `/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914`.
Prior incident: [postmortem](../probes/mtp-exact-tp2-20260914/native04-postmortem.md).
Prepared gates: [metadata campaign](../probes/mtp-metadata-20260914/README.md).

No power/clock/ASPM, swap, page-cache, driver or host changes. All GPU operations
are root-owned; delegated work is CPU/source only. If health cannot be restored
within this admitted probe, preserve the evidence and report the blocker.
