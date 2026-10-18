# Packet97: record bundle 4

A CPU-prepared descendant copied from packet91. Existing packet trees, the
shared screen wrapper and live queues are frozen. The recorded frontier remains
55.68696298163401 tok/s (packet84, `cmvd78ela0007uj01k1ojlm8g`).
No packet97 device speed or model-output result is claimed.

One newly compiled binary selects 128 combinations at startup:

| Dimension | Choices |
| --- | --- |
| head | production, head-transpose (packet93) |
| host | ordered, ordered+reply-first (packet92) |
| hc_norm | production, normfuse (packet94) |
| experts | wide64, wide64+grid-prefetch, wide64+halfcache, wide64+grid-prefetch+halfcache |
| route | production, fast (packet91/78) |
| recurrence | rec-parallel, rec-both-plus (packet91/82b) |

The new combined expert implementation reads E1's exactly decoded FP32 half
scale while retaining E3's two grid-word pipeline. Codes, input bits, scale
multiplication, logical sums and adjacent reductions retain their source order.
The closed HC weight cache and head-plane are not selectable. E1 remains a
composition option, never a new standalone claim.

`copy-lineage.json` records copied packet91 inputs. `build-device-receipt.json`
binds newly compiled units and unchanged inherited object hashes. The original
packet91 bundle continues to use its own binaries and screens.

Both compilers execute each changed operator twice, including raw FP32 chains,
state/output bytes and reply-first failure handling. The complete 128-view
proof is factorized from those actual operator transcripts; it is not a CPU
model run. Full-shape startup executes all 128 selections on both ranks using
real allocation, capture, draft setup and memory admission, mocking only weight
payloads and the backend. Packed target head storage requires a separate
308,904,960-byte unchanged draft prefix, leaving only 8,944,640 bytes net saving
on rank1. Both limits remain unchanged: 30 GiB arena and 1.5 GB VRAM reserve.

The [orchestrator](../../ops/packet97-orchestration/README.md) reads both screen
directions using each source's own compare logic. It emits a decision-bound
control/candidate/control proposal for each lane. Control is packet91's exact
winning selection, or packet84's baseline after packet91 has no winner. Pending
sources can only be closed explicitly with baseline pins and a reason.
Template proposals can be planned but cannot execute. The actual composition
must beat both fresh controls on both lanes with 13/13 exact checks and unchanged
acceptance. The record chain also needs at least 1.5% composed improvement on
both lanes or two independently confirmed selected levers.

CPU commands use `nice -n 19 taskset -c 8-15,24-31`, `python3 -B`,
`OMP_NUM_THREADS=2`, and stdin from `/dev/null`. All compilers take packet94's
`compile_turn.py` lock and wait on whole-host holds. Build, CPU and full-shape
gates precede `prepare_chain.py`, `prepare_packet.py`, `queue_plan.py`,
`fast_reseal.py`, `dry_run.py --cached`, `dry_run.py`, and chain/storage checks.
Tests use `/home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest`.
Inherited historical helpers remain source context; the selected consumer tests
are `test_packet97.py` and `test_lane_admission.py`.

[Task note](../../../../notes/2026-10-18-own-runtime-packet97.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [retention](RETENTION.md).
