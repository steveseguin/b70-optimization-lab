# SC117 parent-capture: working lab recipe and source scope

The four-B70 parent-capture observation is **44.9679 tok/s**, versus matched
41.3990 tok/s (+8.62%), under the same controller observer. All 5,965 output IDs
and final 2,065 target buffers match; the preceding two-request gate also matches
all 73 draft allocations. The 47.9706 tok/s two-card service has a different
observer. Six independent CPU-reference disagreements remain unresolved.

Use the [exact measured configuration](../experiments/own-xpu-runtime/research/continuation-2026-10-25/parent-capture-suite-config.json),
[plan](../experiments/own-xpu-runtime/research/continuation-2026-10-25/parent-capture-suite-proof/plan.json) and
[result](../experiments/own-xpu-runtime/research/continuation-2026-10-25/parent-capture-suite-proof/RESULT.md) for the lab run.
The successful settings are cuts `0,8,21,34,48`, `provider_stage=0` (the default),
`capture_ready_overlap=true`, full F32 target/cache/recurrent state, existing draft
weights, and flat-copy mode disabled. The measured policy omits per-operation
byte diagnostics; resets, restoration, provenance and error guards remain.

The [latest archive](../downloads/own-engine/ownrt-source-e6f89fbce.tar.gz)
contains the complete source/import closure at commit `e6f89fbce49b`, including
`src/pipeline/recursive_provider/seed_peer.hpp` and
`planning/rolling_provider/remote.py`. All 230 native source hashes match build
`be61a3b986c2`; that build was tested with remote provider placement. The archive
itself has not been rebuilt or GPU-qualified, so its source match does not
transfer the capture timing result to a new deployment. Model weights, tokenizer,
Intel dependencies and local model/loader/admission authority remain external.

On an already authenticated matching lab setup, adapt the existing configuration
to a new output path, current binary/build receipt and approved BDF mapping, then
create a fresh plan with the existing tool:

```bash
python3 -B experiments/own-xpu-runtime/engine/tools/persistent_rolling_driver.py \
  --config /absolute/path/to/local-capture-config.json \
  --plan /absolute/path/to/new-capture-plan.json
```

This plans only. Follow the existing [passive admission and guarded run procedure](../experiments/own-xpu-runtime/engine/tools/pipeline-driver.md)
and qualify the new build before interpreting timing. Do not reuse the example's
lab inode/path identities on another host. For source builds with separately
authenticated generated model configuration, follow [deployment preparation](../experiments/own-xpu-runtime/engine/deployment/README.md)
and [build instructions](../experiments/own-xpu-runtime/engine/README.md).
No portable persistent adapter, HTTP service or clean-host certification is claimed.

Optional `provider_stage` selects a nonfinal owner; default0 preserves the original
path. `--pipeline-provider-stage N` is emitted on all owners only for N>0, and
`--pipeline-ring-parent-capture-ack` belongs only to the selected provider. Native
metadata binds the role separately from target-first ownership. Model descriptions,
per-tensor quantization, placement and tuning remain separate. The tested remote
placements lost (42.6283/43.2659 tok/s), so the optional feature stays off by default.
The 45.1979 tok/s flat-copy screen also stays off by default without promotion.
