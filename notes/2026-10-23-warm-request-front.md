# Next own-runtime step: a warm one-card request interface

The owner's October 23 direction was to consult the north star, choose the
next work and continue. The [objective](../docs/own-xpu-runtime-objective.md)
requires our own Intel Xe runtime with exact outputs, then serving, prefill,
an OpenAI-compatible interface and packaging. The
[checkpoint integration review](../tools/ctxkeeper/CHECKPOINT-INTEGRATION.md)
identifies the immediate gap: the checkpoint engine accepts a fixed suite,
while ctxkeeper needs a request interface that keeps that engine loaded.

This is the next substantive lever after qualifying the already measured
one-card diet improvement. Packet179 measured 0.46 seconds to restore state
against 36.75 seconds for the cold prefix. Packet181's fresh lifecycle
processes paid about 209–215 seconds each for loading. Those are component
measurements, not a forecast of serving speed. They justify connecting the
existing mechanisms before starting another small speculative kernel sweep.

The first implementation uses packet181's unchanged kernels and arithmetic,
a bounded sequential token-ID channel, per-request checkpoint options and one
loaded owner. It keeps full 16-bit KV and refuses new requests after faults.
It deliberately does not merge the newer diet/cache-capacity engine into
this first serving change: that engine does not carry the checkpoint API.
New checkpoints remain experimental until the new owner passes device gates;
the exact binary check prevents silently adopting old engine checkpoints.

The existing parking policy's fake engine uses a different token hash and
pending-token convention from real checkpoint files. The new CPU bridge
checks actual native inspect/manifests and the small token/control payloads,
then exposes a distinct policy view. No native manifest is rewritten.
The [request transport](../experiments/own-xpu-runtime/integration/request_front/README.md)
has CPU subprocess tests; neither that mock nor the metadata bridge proves
an end-to-end device serving result.

The planned device sequence is one load: fresh A and save, unrelated fresh B,
restore A with appended input and save, repeat append, then final drain.
Every output and relevant saved state must equal the matching reference.
Report load, restore, append, first-token latency and request overhead
separately. Session reuse must never enter the cold record scoreboard.
