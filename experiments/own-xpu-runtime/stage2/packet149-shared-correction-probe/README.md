# Packet149: in-engine correction exchange probe

CPU preparation for lane B. No device run is claimed. The two-card record remains
58.798108759182306 tok/s. The coordinator gets a 12 × 64 `probe=xchg` smoke and
one load with five 12 × 128 views: **off / xchg / off / xchg / off**. Each view
also has the inherited separately reset incident64 check. Nothing is queued.

The runtime is packet136's banked bundle8 arithmetic, with the packet145 v5
harness vendored locally and its class-layout experiment removed. Packet136 and
all other existing packets are frozen. All 182 original symlink objects are
preserved in `lineage-inputs/packet136-symlinks`; the active root oracle link
retains its original target and `oracle-binding.json` / `shared_oracle.py` checks.
The checked native source and active Python dependencies are inside this tree.
Parent ELF objects are immutable hash-bound build inputs. See
[lineage](lineage-inputs/vendor-origin.json) and [work note](../../../../notes/2026-10-18-own-runtime-packet149.md).

## Concrete exchange schedule

This probes a particular proposed **output-row split of the large projections**,
not a shared implementation of every operation. Four exchanges occur in each of
rank 0's 24 corrected layers:

1. The common attention input goes to rank 1. Half the QKV and z rows return for
   GDN; half the qgate/k/v/iq/ik rows return for QSA. Same-input projections are
   packed into one reply.
2. The attention output projection input goes out; half its 2,560 rows return.
3. The selected expert gate/up input and ten 32-bit expert IDs go out; half the
   gate rows and half the up rows return.
4. The ten expert activation rows and IDs go out; half their down rows return.

Activations and returned rows use the model's BF16 boundaries. Every reply also
carries a 4-byte sticky-error flag. BF16-to-FP32 expansion for existing kernels
can remain exact. HC, small scalar projections, routing, shared experts, PLE,
attention and recurrent state stay local in this proposed split. No partial-dot
sum is exchanged, and no FP32 reduction is reordered.

[The payload census](payload-sizes.json) lists every site, shape and layer.
There are **96 round trips per miss**, carrying **849,792 bytes rank 0 → 1** and
**1,362,048 bytes rank 1 → 0**. Each GDN layer sends 35,408 and receives 57,360
bytes; each QSA layer sends 35,408 and receives 54,928 bytes. The first half has
18 GDN and six QSA layers. PLE on layer 1 adds no exchange to this scope.

The probe uses each engine's existing compute-queue `CopyEngine`, allocation
hazard events and explicit waits, plus release/acquire shared-memory publication.
This is the host-staged route used by the accepted compute-queue head exchange.
Each rank owns 64 KiB of device scratch and 64 KiB of pinned staging. The IPC
mapping grows by 65,600 bytes. No extra weight or model-state allocation is made.
The conservative inherited memory admission remains above these extra bytes.

Only the confirmed redo path enables the callback. Rank 1 receives an explicit
miss-only service command; ordinary hits perform no probe polling or transfers.
The draft sequence is saved independently of that command's sequence, preserving
native draft publication checks. Every corrected xchg half must perform exactly
96 exchanges. Source/received payloads never replace model outputs. The receiver
uploads and downloads private scratch and the sender discards the reply. The
snapshot guard separately excludes these strictly labeled, non-aliasing buffers;
request reset still clears them. Both ranks retain bounded cancellation and peer
abort checks. A failed exchange aborts the experiment, with no retry.

This is a **serialized communication surrogate**: the original rank-0 kernels
still run in full before the associated exchange. Rank-1 copies contend with
its real outstanding draft work. There is no surrogate peer matrix multiply.
It measures this schedule's added cost, not an unavoidable lower bound, a proven
upper bound for a future implementation, or an achieved optimization. Coalescing,
overlap, duplicate-weight placement and peer compute need their own evidence.

## Report and gates

The report reads each v5 view's retained native rank trace instead of demanding
`p105-transfers.jsonl` in every request directory. It binds each corrected half
to a distinct false `guess_rows.hit` position, rejects missing/duplicate half
records, and reports unavailable data as unknown. New probe receipts also carry
the engine completion clock, exchange count and byte totals. Reporting remains
outside the measured completion clock. Per-view output includes corrected-half
time, miss count, cold class-balanced 1–100 tok/s, and the candidate-minus-control
correction cost. Smoke uses its declared 63-interval full-decode rate.

The regression invokes the real report step on packet145's retained lane-A
router bracket. Only report writes are redirected to temporary scratch; all
original JSON/JSONL hashes are checked unchanged. Those five old view timings
are regression evidence, never packet149 measurements.

CPU gates cover both compiler builds; four fresh controller mock runs across
hit/miss/mixed/native-draft cases; four transport mock runs of the actual probe
methods; payload extents, event waits, abort/odd-row refusal and unchanged model
buffers; full report replay; oracle binding; drain races; native getrlimit;
real entry and wrong-unit/environment refusal; all worker requests and failure
teardown; temporary queue plans; `ops/rehearse_entry.py --report`; and pin guard.
CPU mocks do not establish full-model output equality or a speed result.

Run preparation commands with `nice -n 19 taskset -c 8-15,24-31 python3 -B`
and stdin from `/dev/null`. Native compilation uses `ops/compile_turn.py`.
The finite 4-GiB cap applies inside CPU test/build entrypoints; intercepted
native-launch tests check that the real unlimited inherited exec limits remain
unchanged. No model payload or full-shape startup test is needed by these gates.

The external proposals are `proposed-p149-smoke-B.txt` and
`proposed-p149-v5-B.txt` under `ops/lane-queue/`; byte-identical copies are in
`proposals/`. The bracket requires its exact same-lane smoke. The final
`READY-FOR-DEVICE.json` is written last, binding the source commit, CPU seal,
gates and proposal hashes. Only the coordinator can admit device execution.
