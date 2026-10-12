# Rank-0 rollback coverage

`audit_rollback.py` derives the inventory from `launch-plan-rank0.json` and
checks the actual code. `rollback-inventory.json` lists every allocation and
writer. The independent reviewer received the launch dump and code before this
list. The real split is 24 layers per rank; the four-layer miniature puts both
GDN and QSA plus layer-1 PLE on rank 0.

| Persistent data | Count / bytes | Handling |
| --- | ---: | --- |
| GDN recurrent state | 18 × 1,572,864 | Existing kernels read committed bank and write alternate bank. |
| GDN convolution history | 18 × 61,440 | Separate old/new pointer arguments, unchanged kernel. |
| PLE convolution history | 1 × 184,320 | Separate old/new pointer arguments, unchanged kernel. |
| QSA keys / values / raw index rows / pools | 6 layers × 4 arrays | Append at current position; redo overwrites the same rows. Prior rows unchanged. |
| Device PLE token history | 16 | Hash writes through its input; checkpoint on host, restore on miss. |
| Host PLE histories | 16 | Restore the saved two int64 values on miss. |
| Position / commit counter | 4 | Half executes one unchanged commit. Undo restores the pre-half position. |
| Sticky error | 4 | Never cleared or rolled back; any nonzero value aborts. |
| Streams / hyper-connections | full 20,480-byte stream | Broadcast overwrites at each rank-0 half; no cross-position carry. |
| QSA selection IDs and other intermediates | listed individually in inventory | Written before their first read each position; redo overwrites. |
| FP32 prepared input cache | 696,320-byte workspace | Cache source/extent invalidated at bank transition; no stale cache can be consumed. Contents with invalid cache are scratch. |
| Prepared bindings | two maps of host descriptors | Swap with banks; the GEMV matrices never bind temporal state. |
| Host lookup IDs / selected experts / loaded layer | bounded host metadata | Lookup IDs regenerated; routes selected again; streaming layer released. |
| Fixture snapshots | initialized 983,040-byte workspace | Candidate bytes held privately; publish only after acceptance. Redo replaces candidate. |

The extra state bank is **29,601,792 bytes**, covering 37 allocations. The GDN
and convolution hot path copies **zero state bytes**. All banks are initialized
once, including unused output bytes read by the host reference adapter.

There are 1,015 rank-0 plan buffers and 890 plan sites: 37 banked, 24 QSA append
arrays, three temporal controls, four externally initialized, and 947 overwrite-only
buffers. Immutable weights, RoPE and PLE metadata are never speculative writes.
The inventory includes first-writer/first-reader evidence and explicitly handles
QSA partial writes instead of assuming that an output name means a whole-array
write. The owner allocation inventory also accounts for non-plan scratch,
slabs, routes, mixture buffers, snapshots and FP32 input storage.

QSA appends 1,024 bytes of keys, 1,024 bytes of values and 256 bytes of raw index
state per layer/position. A completed four-token block writes its 256-byte pooled
row. A miss followed by redo rewrites exactly those locations. Rows beyond the
committed extent after an abandoned terminal guess are not exposed as retained
state. They must be overwritten before any future reuse.

## Hot-path copy ledger

For each rank-0 half: position check 4-byte D2H; PLE-history checkpoint 16-byte
D2H; token 4-byte H2D; token embedding and PLE lookup 5,120-byte H2D each;
sticky-error check 4-byte D2H; confirmed/candidate boundary stream 20,480-byte
D2H. The same stream is copied into the producer shared slot, across to the
consumer slot by the coordinator, and then uploaded 20,480 bytes H2D on rank 1.
Each rank-1 half also checks position/error (4-byte D2H each), uploads the token
(4-byte H2D), and generation reads the target token (4-byte D2H).

The bounded pinned slab entails an ordinary host memcpy of the same byte count
for each H2D/D2H transfer. Python's shared-slot slice makes a bounded host temporary.
Commands are 32 bytes and replies 64 bytes. Model scalars travel in these frames;
no pointers/events do. Lookups read only their quantized file rows on CPU and
produce the BF16 upload bytes. Resident model weights and static constants have
no per-token uploads. The CPU gate's layer-streaming weight uploads are separate
from the native resident path.

The rollback-specific overhead is the 16-byte D2H checkpoint on every rank-0
half, plus **20 bytes H2D per miss** (16 history + 4 position), and 16 bytes of
host scalar restoration. Large state bank selection costs no copy. Speculative
halves and redos incur the ordinary half ledger again.

For each of the eight retained fixture positions, each rank makes 24 × 20,480
bytes of local-device snapshot copies, then reads its initialized 983,040-byte
snapshot allocation. Fixture bytes are copied into private host candidate
vectors, checked against the oracle, and written only on acceptance. These
intentional gate costs are included in model-window wall timing.

Full state gates compare every plan buffer's bytes, both active and inactive
banks, host histories and FP32 cache validity after a miss plus redo, against
never speculating. Invalid FP32 scratch bytes are not persistent model state and
are not claimed to match. Rank 1 only consumes confirmed streams; all its
history remains the sequential history and needs no rollback.
