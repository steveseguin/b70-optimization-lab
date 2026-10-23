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

The planned device sequence is one load and eight requests: fresh A and save,
unrelated fresh B, resume A and save, append to A and save, repeat the append
and save, run that appended prompt fresh and save, uninterrupted A, and B
again. Every output and relevant saved state must equal the matching
reference. Report load, restore, append, first-token latency and request
overhead separately. Session reuse must never enter the cold record scoreboard.

All three native targets now compile: the standalone protocol probe, the
host-only engine and the device engine. Compiler dependency checks cover the
full repository input closure; the device link reuses 41 unchanged parent
objects. The actual host-only engine passed the eight-request lifecycle in
one process, including resumed output, unrelated-request isolation, and
byte-identical saved state for appended, repeated and fresh input. This uses
tiny synthetic CPU geometry and does not establish device correctness or
model performance. The single real-model device window subsequently passed
all eight requests and 1,408 output tokens, exact saved state, one load and
clean shutdown. The [result](../experiments/own-xpu-runtime/stage2/packet197-warm-request-front/RESULT.md)
and independent audit preserve the component timings and scope. The next
implementation is a separate protocol version with explicit postreply
SAVE/RELEASE, while packet197 stays frozen.

The token-ID pilot is one part of the serving interface. Its RUN command
chooses a checkpoint ID before generation, whereas ctxkeeper's parking
policy computes its full-history ID after the reply and then calls save.
Connecting that policy therefore still needs an explicit postreply SAVE
operation or a separately specified mapping to pre-saved native IDs.
Inspect and delete are native CPU commands, not request-front operations.
The metadata bridge currently accepts qualified packet181 checkpoints only;
packet197 requires its own evidence and explicit adapter support. No
ctxkeeper or OpenAI-compatible endpoint is wired by this pilot.
