# Captured prompt-row views on the existing host backend

This packet executes the unchanged runtime `Device`, `Arena`, `PreparedCompute`
and `CopyEngine` code with synthetic inputs. It reuses the exact p198 GNU host
objects and extracts its `Host` class unchanged. That class derives from the
existing `LifetimeMock` / `MockDevice`: CPU operations and byte copies really
execute, while queue, event and context completion are **simulated backend
markers**. This is an ownership/capture proof, not native device event
authority, model execution, arithmetic qualification or throughput evidence.

## What runs

[capture_probe.cpp](capture_probe.cpp) allocates two tiny row maps with separate
token, position, input, streams and PLE-ID buffers, sharing token history,
convolution history, convolution output and scratch. It captures these existing
adapter operations for each row:

1. `CopyEngine` stages eight bytes of that row's payload into shared scratch.
2. The actual host adapter checks the row position (`Special::begin`).
3. Its PLE hash consumes token/history/metadata and updates shared token history.
4. Its convolution consumes the staged shared payload and shared BF16 history.
5. Its HC combine updates that row's four BF16 streams.
6. Its row-local commit increments that row's position.

The synthetic width is four, context sixteen, with two known rows. Actual
`packet18::submit_parallel` creates the captured `HostOperation` instances;
there is no replacement mock of the owner, arena, capture, copy or arithmetic
interfaces. The fixture uses the host adapter's implementation-zero path.
It does not reproduce the full model's selected SYCL dispatch tuple. The
external adapter scratch argument may be unused by host operators that allocate
their own CPU work arrays; the explicit staged payload and convolution consumer
make **shared buffer reuse** observable separately.

The required RoPE ABI extent is four MiB even for the convolution adapter. The
fixture supplies zeroed synthetic storage of that extent; its operations do not
read RoPE values. No model weights, tokenizer or production checkpoint is read.

## Captured identity and mutable contents

The row map actually supplies allocations during capture. After capture, every
map entry is replaced by a valid decoy allocation. Caller-local binding vectors
and `Spec` objects are also mutated and destroyed. Replay must still match the
eager adapter byte-for-byte and leave all decoy bytes untouched. Row position
argument blocks are distinct; shared history and shared payload consumer IDs
remain the same across rows.

Captured pointers do not freeze their contents. Changing a row's input in place
before replay must change its downstream stream bytes. Zeroing recurrent
history before row1 and substituting row0's payload for row1 must each change
row1 streams, not merely a bookkeeping field or the modified state itself.
Both complete-state and row-output SHA-256 values are retained.

`PreparedCompute` retains operation objects and argument storage but is not an
allocation lease or a dependency graph. The fixture issues commands serially;
the exact host backend executes operations synchronously and emits simulated
markers. It checks owned completion markers before canonical publication.
This does not prove asynchronous GPU ordering or a replay graph.

## Publication and failure boundaries

Canonical streams, token, position and host history remain unchanged through
both row computations. Only after all row operations complete successfully does
the fixture use four real `CopyEngine` copies to publish them. It checks exact
canonical bytes and the final position/token/history.

Those copies are **not atomic**. A test allows the stream copy to finish and
then deliberately supplies an invalid extent for the second copy. The actual
copy API refuses with its original error; publication becomes sticky-failed,
retry is refused, and already-copied canonical streams remain changed. No
rollback or valid checkpoint is claimed. An incomplete marker prevents every
copy; a partial-row refusal is nonmutating.

A `before_compute` guard refusal after row0 automatically poisons the fixture,
preserves the original error and blocks row1 retry/publication. The healthy
owner can still close normally. A separately captured throwing `HostOperation`
exercises the actual owner fault path: further submission refuses and shutdown
reports `failed-drained`, exit code 1, with safe exit only after its existing
cleanup succeeds. This is not a successful runtime request. Normal, guard,
publication-refusal and backend-failure shutdown receipts retain status,
sequence, in-flight count, live bytes and safe-exit fields.

## Allocation lifetime and integration implications

The real arena tests establish that adding an unrelated allocation does not
change the generation, but releasing one invalidates prepared captures—even
captures referencing other still-live allocations. Explicit invalidation also
refuses stale captures. Release/invalidation/publication refuse while simulated
work markers remain pending; the fixture completes them explicitly for cleanup.

A future Engine integration must account for **both ordinary decode and chunk
captures** when allocations are released or generations change. Prefer finalizing
all row allocations before capture; any necessary release/rebinding requires
coherent re-preparation of every affected consumer. Updating a name-to-ID map
does not update captured pointer bytes. This packet demonstrates the seam and
canonical-copy ordering with tiny views; it does not instantiate the full
[p204 contract](../packet204-prefill-row-bindings/README.md), its 122 persistent
regions, cache policy, QSA capacity variants or actual model geometry.

## Evidence and reproduction

[Production bindings](production-binding.json) pin the exact extracted host
fragment, headers, p198 build receipt and 23 reused GNU host objects. The model
program entry and unrelated fixture/loader objects are excluded. The
[source authority](SOURCE-AUTHORITY.md) links owner/adapter source-to-object
lineage. Existing checked headers retain their original absolute includes;
this recipe is tied to the recorded workspace and retained host objects.

From the repository root:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet205-host-row-capture/build_engine.py --run
```

The helper uses the existing compile lock, helper cores and a four-GiB address
space bound. [Build receipt](evidence/build.json) and
[host result](evidence/host-capture.json) retain source/object/binary hashes.
Per-attempt directories retain exact tested sources, compile logs and raw
output, including the initial C-array initialization compile refusal and the
RoPE-extent admission refusal. Later strengthened passing candidates also
remain available. Build outputs are ignored; no sealed source was edited.

The next implementation gate is a real Engine allocation/capture adapter using
the established row binding and cache contracts, with complete buffer-liveness
coverage and selected device argument census. This fixture alone authorizes no
device execution or serving change.
