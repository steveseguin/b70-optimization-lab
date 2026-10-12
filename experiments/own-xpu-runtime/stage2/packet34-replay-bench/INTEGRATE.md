# Attaching replay to a pipeline rank

This is a design boundary, not an implemented packet32 change. Only packet32's
README was consulted; packet34 does not compile or depend on packet32 code.

Packet32 assigns layers 0–23 to rank 0 and layers 24–47 to rank 1. Each process
owns one single-device context, one in-order queue and its own allocations.
Shared transport holds stream bytes in two slots, never SYCL or Level Zero
handles. Replay must remain inside one rank process and its existing owner.

Create one immutable recording per rank per ping-pong parity, after that
rank's direct path passes its own bytes/state gate. Each parity recording may
bind fixed local staging buffers corresponding to the transport slot. Keep
IPC receipt, host staging, device upload, accepted-token publication, checkpoint
management and rollback outside the graph. Queue order must put incoming
bytes and controls before the recorded half.

The per-token device control region holds position, active/error and any
dynamic input selector. Router results, selected expert route descriptors,
attention selected IDs and recurrent/KV state stay in the rank's existing
device allocations. The kernels read their contents at execution. Fixed
capacity/budget, format, dimensions and addresses belong in the recording.
Current packet29 kernels have fixed buffer pointers; choosing the appropriate
qualified parity recording is what changes the fixed staging address.
Packet34's measured half instead uses a device-selected boundary copy into
one fixed streams buffer, outside its timed graph.

Rank 0 token and PLE lookup work precedes its recorded half. Packet34 covers
layers 24–47 and therefore does not qualify recording the unique layer 1 PLE
path. Rank 1's fused final normalization is already included in the last
combine; head and argmax need separate capture qualification or stay direct.
A full pipeline integration must inventory these boundaries explicitly.

A recording is invalidated by any allocation/address replacement; context or
device change; rank ownership change; changed kernel binary, dispatch, precision
flags or optimization overlay; weight identity; tensor format/dimensions;
context capacity/budget; or launch/dependency topology. Destroy it before
freeing any captured allocation. Updating the contents of stable control,
state or input allocations does not invalidate it. A changed parity selects
the other already qualified recording.

Rank 0 speculation and rollback are state operations, not graph mutation.
Drain an attempted half, preserve sticky errors, restore the registered
state bytes, upload the corrected token/control, then replay the same parity
recording. No graph may bypass the target's exact-output gate, publish an
unconfirmed half, overlap a writer to its input slot, or keep a pointer to
a transaction allocation after the owner releases it.

Drain queue work and retain failure evidence first. Destroy replay completion
events, executable graphs, modifiable graphs and any backend borrowers before
releasing their allocations, then destroy queue/context wrappers before the
native context owner. A timeout or uncertain submit retains the whole owner
for the coordinator. There is no automatic retry, reset or hard kill.

The coordinator still needs to establish real device graph support,
byte identity over changing routes/attention counts, bounded graph memory,
per-parity freshness, cancellation behavior and the wall-time benefit. A
packet34 pass would justify a narrow pipeline experiment; it would not
qualify the entire two-rank pipeline.
