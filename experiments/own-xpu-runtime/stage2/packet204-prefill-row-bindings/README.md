# Two prompt-row bindings over one engine

This packet defines a CPU metadata contract for integrating known-prompt chunks
into the unchanged p198 engine. It does not allocate native memory, capture or
submit commands, execute a model, or qualify a paired device path. The selected
arithmetic fixtures remain in [p202](../packet202-prefill-chunk-prep/README.md)
and [p203](../packet203-prefill-gdn-branch/README.md).

The concrete first integration is feasible with two persistent row views over
one Engine/arena. Captured pointers, not integer positions alone, determine the
bindings. A separate native ownership proof is still required before modifying
the production execution path.

## Fixed row views and shared allocations

[row_bindings.hpp](row_bindings.hpp) defines typed allocation-ID/offset views,
exact required extents, histories and an ordered scratch lease. A row retains:

| Region | Bytes per row | Lifetime/use |
| --- | ---: | --- |
| Four BF16 residual streams | 20,480 | Live across all 48 layers |
| Token / position controls | 4 / 4 | Fixed input values for this chunk |
| Embedding / PLE lookup BF16 payloads | 5,120 / 5,120 | Staged before execution; immutable through consumers |
| Host-derived PLE IDs | 128 | Immutable staged lookup input; separate from native hash scratch |
| Captured layer routes | 5,760 | All 48 layers retained until chronological host replay |

These are logical retained extents, **not** a complete allocation increment or
admitted memory forecast. Row0 may reuse appropriate existing allocations only
after their prior readers finish. Two row banks total 73,232 bytes for these
fields, before alignment, staging, capture records and any later pair operands.
The existing canonical stream allocation still needs explicit publication.

The contract requires 122 shared persistent bindings: 36 GDN histories and
states, 12 QSA key/value/raw/pooled sets, one PLE history and token history.
They are not copied per row. Weights, RoPE, metadata and pointer-table storage
also remain shared. Global active/error controls stay shared; each row has its
own position and token, while canonical global position is a separate commit
target. All other one-row intermediates, parallel controls, QSA scores and
probabilities, FP32 conversion storage, compact routes, mixture buffers,
operator scratch and GEMV workspace can remain single allocations for the
initial **row-complete M1 schedule**.

The [source census review](binding-source-review.json) and
[authority](AUTHORITY.md) bind actual p201 allocation evidence. In particular,
PLE lookup is 5,120 bytes, IDs 128 bytes and token history 16 bytes; PLE
convolution history is 184,320 bytes. The existing
operator scratch is 256 MiB. The synthetic contract fixture's 8 MiB scratch is
an arbitrary metadata extent, not a replacement production size.

## Execution, history and publication

The first schedule is layer0 row0 then row1, layer1 row0 then row1, through
layer47. A complete row's PLE, HC, GDN/QSA, expert and residual consumers finish
in native dependency order before shared scratch is reused. This allows fixed
prepared row views with shared scratch; it does not prescribe a host drain per
row or layer. `Schedule.begin/finish` validates monotonically ordered event
ordinals, including the admitted dependency and route-copy completion. A
future adapter must supply **real owned events and dependencies**. Metadata
integers alone prove no DMA or device completion.

For QSA, row0 prepare, append/pool, select, attention and output consumption
precede row1 writes to shared KV/raw/pools. Context capacity is rounded to 32;
chunks do not cross a capacity boundary. A full `budget+3` selection buffer may
have no sentinel; any unused suffix must contain only `-1`. GDN retains its
per-row BF16 state update. PLE hash/history runs once per row at layer1.

Host lookup IDs/payloads are staged from a snapshot of history; do not call the
current `prepare_token` twice into shared buffers. The contract preserves the
native EOS-only history rule (248044, not im_end 248046) and uint64 hash wrap,
signed interpretation and nonnegative remainder. Native device history may
already advance while a chunk executes; host history is published only after
the complete chunk succeeds. A failed partial chunk is poisoned and retained;
there is no single-row retry or checkpoint of partial layer-major state.

All rows here are nonfinal prompt rows: final HC/head/sampler remain excluded,
and the final prompt row remains the original single-row path. Existing
per-step global `commit` must not run inside the chunk. At an actual clean
chunk exit drain, `Schedule.commit` returns only a **publication descriptor**:
new global position, last consumed token, host history and final stream row.
`publication_ready()` does not authorize SAVE or attest native publication.
The future adapter must copy the final row streams into canonical
`buffers["streams"]`, or coherently rebind/reprepare every decode/checkpoint
consumer. Swapping the buffer map alone leaves captured arguments stale.
Global token/position/history publication and FP32-tag invalidation also belong
to that adapter; any failure must poison instead of exposing success.

## Captured arguments and cache boundary

Current `prepare_commands` stores concrete argument bytes, allocation IDs and
FP32-source tags; state-bank parity and QSA capacity also affect bindings.
Future preparation must create each fixed row view before capture, then key
capture identity by row, state-bank parity and capacity. Mutable scheduling
metadata must never masquerade as a pointer rebinding. Converted-input caches
must be invalidated when their producer contents change even if allocation ID
is unchanged.

The contract assumes complete caller-supplied Engine allocation inventory and
that distinct native arena IDs refer to disjoint storage. It checks exact
required persistent types/extents and all supplied live region aliases; it
cannot detect omitted scratch or a caller lying about physical aliasing,
initialized values, captured pointers or event completion. No production
allocation adapter exists in this packet. Pairing p202/p203 operators requires
additional explicit live operand slots and selected-device argument census;
the serial scratch lease alone does not implement those pair kernels.

Expert maintenance uses the explicitly distinct
[frozen-chunk cache contract](CACHE-CONTRACT.md), with a matched-policy serial
control. The old overlapping path's quiesce and recency effects are not neutral.
Row-major route replay is required even though execution is layer-major.

## Reproduction and result

From the repository root, this compiles and runs only the tiny metadata probe:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet204-prefill-row-bindings/build_engine.py
```

The helper uses the existing compiler turn lock, 4 GiB address-space limit and
the helper cores. It includes the immutable p202 planner header but no runtime
backend or model weights. [Build/test evidence](evidence/binding-cpu.json)
records exact source/binary hashes and named checks. Independent planner,
integer-history and actual allocation-census tests are recorded in
[authority tests](evidence/authority-tests.json). Per-attempt sources/logs
retain the initial helper import failure, compile warning refusal and later
passing candidates. Build outputs stay ignored.

This is a usable typed boundary and causal scheduling specification, not a
throughput result. The next meaningful proof should use the actual HOST_ONLY
arena and PreparedCompute capture APIs with synthetic payloads, demonstrating
fixed row pointers, shared-state dependencies and final canonical publication.
Native device census, whole-prompt exactness, matched-policy timing and live
admission remain subsequent gates.
