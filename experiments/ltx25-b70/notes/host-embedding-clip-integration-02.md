# Guarded actual CLIP integration qualification

2026-09-14. The successor adapter passed six actual tiny CPU integration groups in a single guarded process (PID112132, exit0). Root scheduled this run; the source-preparation agent made no native or endpoint calls. This proves the tested CPU lifecycle and raw-byte preservation, not full-model XPU residency, real-video parity or speed.

The frozen standalone gather candidate and original integration proposal remain unchanged. New `host_embedding_clip_v2.py` and `host_embedding_placement_node_v2.py` are intended to be copied under their canonical names without `_v2` in a future immutable packet. The complete five-file source snapshot is [integration patch02](../patches/host-embedding-clip-integration-02.patch).

The v2 adapter observes actual embedding input IDs and final scaled output using a metadata-only module hook. It retains shape, dtype and device only; the hook returns None and leaves the output object intact. Observations are bounded to four calls per encode, scoped to the active encode, and consumed by the unchanged-conditioning placement node. A subsequent encode is refused until consumption. This hook does not independently observe the internal BF16 gather. Native qualification must require the expected int64 XPU2 IDs and F32 XPU2 scaled output, CPU BF16 table and full remaining encoder residency; no such native claim follows from these CPU checks.

The six fixture groups exercise the actual CLIP constructor with a tiny target and explicit initial CPU placement; actual CPU loader and unchanged memory-estimator forwarding to both owners; size-cache recomputation under private loader state access; clone/original-GC/shared retirement; active root/descendant save and reload refusals; restored complete raw state; bitwise encoding equality including signed zero; same-object conditioning passthrough; bounded observations and inference-created weight ownership. Physical model loads execute on CPU. The constructor also accepts the logical XPU2 target while remaining CPU and avoiding accelerator queries through the tiny-model early return.

The driver records its PID and source pins before Torch import, reuses the frozen accelerator traps and CPU availability policy, and permits exactly one source-pinned Comfy module-level query refusal. All compile and Triton-backend calls remain forbidden. All six tests passed without skips, errors or failures; accelerator trap and backend attempt lists are empty; import policy completed with one omission; final guards remained intact and XPU/CUDA initialization flags were false. No compilation occurred.

Evidence:

- [Native result](../data/host-embedding-integration-native-result.json), SHA `b06e617ccb8c307eeb0a8b29981049f30561985480007c85259cca54b7e09326`.
- [Native startup identity](../data/host-embedding-integration-native-startup-identity.json) and [six-group test log](../data/host-embedding-integration-native-tests.log), copied verbatim from `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/host-embedding-cpu-integration-native-01`.
- [Nine stdlib checks](../data/host-embedding-integration-stdlib-01.json) and [source-only gate](../data/host-embedding-integration-source-result.json) were executed separately without Torch imports.
- Root's [preflight](../data/host-embedding-integration-preflight-01.json), [postflight](../data/host-embedding-integration-postflight-01.json) and [run log](../data/host-embedding-integration-run-01.log) establish the separately managed execution context.

Driver SHA `6f0e89f549b9abd704c4648d1f06288b57607d3c31174c3a7dc1cfc22103e26d`; adapter SHA `53d45d883bcc46d1a5889d3b6f162b0e95417e834c62dde8d8836791cffe2994`; placement SHA `4ab92f1580f8f54ecc6631acd4fb74603d06bc8cf6c3760ede7638c655f5753b`; fixture SHA `2fa5d3636afdc7f17fc5957916cc525fa935ff1181efc90dad8753860e69f79e`. The native result binds the remaining helper and actual Comfy source identities.

Next is an inactive packet and bounded original/host-table/original screen with all four original raw output oracles, exact registered-state/ownership and per-request observation gates, complete mode-transition retirement, and at most three retained previews. Source and CPU qualification do not authorize a speed claim or bypass native failure gates.
