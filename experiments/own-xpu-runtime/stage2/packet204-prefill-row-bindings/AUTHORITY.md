# Causal row-binding authority

This packet specifies a CPU metadata contract for a future Engine integration.
It does not bind real allocations, submit native work, prove device pointer
lifetimes, or qualify a faster model. [Input pins](authority-inputs.json) bind
unchanged source and retained device metadata; the cache policy is separate in
[CACHE-CONTRACT.md](CACHE-CONTRACT.md).

## Row-local input and PLE history

The p198 Engine `prepare_token` (main.cpp:1256) mutates one shared lookup map,
lookup output allocations, staging slab, and host token history. Calling it
twice before either consumer completes is unsafe. Stage immutable token,
embedding, sixteen PLE IDs, lookup payload, and history-before/history-after
for each row. Keep each row's four BF16 streams (20,480 bytes) alive across
all layers. Per-row token/position are four bytes each; embedding and PLE
lookup are each 5,120 bytes; sixteen signed 64-bit IDs occupy 128 bytes.

PLE hash is executed once per row at layer 1. Preserve unsigned 64-bit
multiply/XOR wrap, bit-cast to signed 64 bits, and nonnegative modulo for each
of the sixteen positive vocabulary sizes. If history[1] equals geometry EOS
248044, hash history[0] as EOS; that conditional does not rewrite the retained
history. History after consuming token t is [old history[1], t]. Token248046
is a native stopping token but is not this PLE history sentinel. The host and
device histories must agree at the eventual publication boundary. Shared PLE
convolution history is BF16[4*2560,9] (184,320 bytes), updated row0 then row1.

The retained append fixture starts at processed position342, history
[43164,22843], pending token37574. The recorded 370-token append input has
positions342..344 equal to [37574,248046,198]. The pending token must be
consumed first, followed by248046: histories become [22843,37574], then
[37574,248046]. A subsequent row must not apply the EOS reset to248046.
These are existing recorded inputs, not newly inferred model outputs.

## QSA visible prefix and selected IDs

For logical position p, only keys/values/raw rows0..p are visible. Completed
four-token pools number floor((p+1)/4); no partial group is eligible as a
completed pool. Selected complete groups expand to four token IDs each;
remaining tokens from the current partial group are appended separately.
Selection preserves existing score arithmetic and tie order (lower pool ID
wins equal scores), and unused IDs remain -1. Every admitted selected token
must satisfy 0 <= id <= p and id < context. Pool-group capacity, selected-ID
budget, full allocation capacity, and launch extent are distinct bounds.

Conservative integration may reuse the unchanged selected M=1 QSA operators
for each row: prepare, append/pool, select, attention, output projection, then
release the workspace. Complete row0's consumers before row1 modifies the
shared raw/pool/history storage. This avoids any future row influencing row0's
selection. The selected attention path is p49 split-softmax implementation12;
the historical `p49::current` M=1 p30 helper is not authority to switch kernels.

Engine `admit_position` (main.cpp:1618) uses
min(context, ((p+32)/32)*32), draining and recapturing select/attention sites
when that extent changes. Initial chunk2 admission must not cross a32-position
boundary. At p31 extent32 is valid; p32 requires extent64. A one-row tail and
the final prompt token retain their existing execution path. Do not truncate
full KV allocation capacity to the launch extent.

## Actual Engine binding and publication obligations

The proposed two row views override streams, token, position and lookup inputs.
They share the exact same persistent GDN/PLE/QSA allocations, metadata,
weights, active/error controls and expert-cache storage. Shared M=1 scratch
has one owner until its real dependency completes and row/layer route data
has been retained. Allocation identity plus byte ranges must detect partial
overlap, not just equal base pointers. Reusing scratch is legal only when all
consumers have finished; distinct logical views do not establish that fact.

A future integration must rebuild captured argument blocks, Allocation
pointers, issue sites, current state-bank parity and FP32 input/source tags.
The existing Engine stores these concrete pointers; changing a logical buffer
map alone is insufficient. Row-local kernel positions cannot advance the
canonical publication position via the old per-token commit operation.

Execute layer0(row0,row1), then layer1(row0,row1), through layer47. Record each
row/layer's routes before shared route storage is reused. Layer-major mutation
is not a complete token prefix midway through the chunk. Only after all96
row/layer completions, actual drain and clear sticky error may the canonical
position/history/processed-prefix descriptor publish two newly processed
tokens. No SAVE, inspectable successful checkpoint, intake or single-row retry
may expose partially advanced state. Failure is fatal for this chunk and
retains actual resources until an outer owner proves quiescence.

Existing checkpoint classification (checkpoint.hpp:215) saves shared recurrent
histories/state and controls whole, but saves QSA keys/values/raw only through
processed prefix N and pooled rows through floor(N/4). IDs and other scratch
are recomputed. For the production geometry keys/values each consume1024 bytes
per saved token; raw and pooled each consume256 bytes per saved row. This
serialization boundary is evidence of required state completeness, not a
ready-made chunk transaction or rollback mechanism.

The retained p201 allocation census separately confirms the122 persistent
regions and row input extents. Its operator scratch is268,435,456 bytes; the
tiny contract fixture uses an8 MiB representative scratch region and does not
claim to be a complete real allocation or memory budget.

## CPU gates and remaining proof

The contract fixtures should refuse out-of-order layers/rows, overlapping row
storage, short regions, mismatched shared state, future selected IDs, early
workspace reuse, lost route capture, boundary-crossing pairs, early commit and
commit after sticky error. Use the recorded pending-token case plus synthetic
signed-overflow PLE metadata, EOS/non-EOS histories, pooling boundaries3/4 and
31/32, and incomplete96-operation schedules. A valid schedule must leave the
canonical prefix unchanged until final publication. Completion facts in these
fixtures are simulated; native event provenance and actual captured pointer
rebinding remain required integration/device gates.
