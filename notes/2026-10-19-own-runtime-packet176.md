# Packet176: copy-engine-free foreground token I/O (d2), READY (CPU only)

This is CPU-only preparation for the one-card IQ3 own runtime: Qwen3.8 Flash-Next 125B-A6B UD-IQ3_XXS on one B70. The record line is the packet58as bounded spin, 34.573 tok/s (28.80 ms/token). No GPU, service or setting was touched, and nothing was queued.

- **Packet:** `experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/`
- **Parent:** a `git archive` of packet58as at HEAD `be2f007b6` (last packet58as commit `c3043c4e6`; native sources identical to `dabfc958b`). Scaffold tooling was ported from packet174.
- **Proposal:** `experiments/own-xpu-runtime/ops/lane-queue/proposed-p176-v5-A.txt`, job `packet176-v5-A`. It is not in any live queue.

## What the source says about the slow "readback"

- **The measured field mixes head and tail.** `transfer_wall_ms`, the field packet171, 171b and 174 fitted, is all foreground transfer time of the token:
  - the head `put(token)` and lookup-row uploads, issued right after the fill submission;
  - the tail error/next_token readback.
- **The split was never measured.** Re-running the readout on all three real runs (packet58as, 171b, 174; 15 spin views) reproduces 0.035 ms per same-token fill MB with an intercept of about 0.1 ms. The head/tail split cannot be recovered from those streams.
- **Fills and foreground copies share one engine.** The foreground copy list and the maintenance fill list are created from the same descriptor: the first copy-only ordinal, index 0. A strict FIFO on that engine explains the measured pattern, including the neutral fill kick:
  - zero absorption;
  - zero intercept;
  - slope = 1/(28.6 GB/s);
  - P(slow | no fill) = 0.
- **The wall slope is twice the transfer slope.** It is 0.0666 ms per same-token fill MB, against 0.035 for transfer. The other ~0.032 ms/MB (~1.0 ms/token) lies outside the transfer window: either fill-submission host time or compute contention. It is unsplit, and d2 does not target it.
- **No setting touches copy offload.** The closed native environment sets no `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD`, `SYCL_PI_LEVEL_ZERO_*` copy-engine key or NEO copy key, so copy offload is the UR adapter's default. This is documented only; nothing was changed.

## Design (B arm, `--foreground-io kernel`; default `copy`)

| Part | Where the bytes go | How the host gets them | Copy engine |
| --- | --- | --- | --- |
| Tail: `p176::TailStore`, a `parallel_for` on the in-order compute queue right after argmax | error, next_token and a per-token stamp go to `slab[0]` bytes 0-15 (pinned `malloc_host`, the same bytes the parent's copies fill); the 48 route rows go to the pinned `route_log` | the unchanged compute drain (spin, 600 s deadline, `check_error`, `wait_and_throw`), then the stamp check, then a host read; `require(!status)` is unchanged | none |
| Head: `p176::HeadLoad`, a `parallel_for` on the compute queue | `put()` stages the token id and lookup rows at `slab[0]` + 4096; the kernel loads them into the unchanged device buffers | not applicable: the compute queue is in order, and there is no host wait | none |

- **Why they cannot sit behind fills.**
  - Both are kernels submitted through `Device::compute`. Bindings are device-only; the pinned pointers are immutable kernel arguments, as in `p58v::Publish`.
  - There is no memory-copy command, so copy offload cannot apply.
  - Neither depends on a copy-list event.
  - `single_device.cpp` is byte-identical to the parent.
- **What stays the same.** Fills and publication timing, every launch, arithmetic, selection, spin, resident lookups and captures.
- **New timing fields.** Both arms log `head_transfer_ms`, `tail_transfer_ms`, `route_log_ms` and `foreground_io`. The A views will finally say whether head or tail carries the fill wait.

## Pricing (from the packet174 law)

| Item | ms/token | Basis |
| --- | --- | --- |
| Transfer excess removed if no copy engine is waited on | up to 1.07 (0.035 ms/MB × 30.63 MB/token) | measured |
| Fixed copy round trips removed (intercept) | ~0.10 | measured |
| Fill now overlapping compute (H2D shares PCIe with zero-copy misses) | 0 to −0.9 | assumed |
| **Net** | **+0.1 to +1.17 (+0.4% to +4.2%)**, central +0.5 to +0.8 | |

The fill kick was neutral, so it is not composed here. If it had won, d2 would keep only the ~0.1 ms intercept.

## Gates (all pass, one compile turn)

| Gate | Result |
| --- | --- |
| Byte gates | GNU/Intel: 120 request resets and 10 view resets, byte-equal to packet58aj. Every timing row carries the right transport label. |
| `--foreground-io` (`evidence/kernel-io.json`) | kernel/copy/default are byte-equal on GNU and Intel. The parser accepts it in KD/W2m/WS/WS128x/WS128. The packet58as binary refuses it (fails on old code). Refused: bracket conflict, draft capture, and the poll/spin, spin-cq and spin-kick orders. |
| Source-delta test | Passes here and fails on the parent with 15 problems. |
| Real device-define CPU preparation | 5 views and 60 requests. The B views ran 24 tail stores and 24 head loads with production bindings and route sources. |
| Analyzer | Three real runs (180 exact requests), old identities refused, and a synthetic head/tail attribution check. |
| Flags and argument replay | Pass |
| Imports | Pass |
| Temporary `lanequeue plan` | Passed |
| `rehearse_entry --report` | Passes, with two documented limitations: synthetic report and no shared one-card preparation adapter. |
| Pin guard | Pass |
| Seal | `seal.py --verify` |

## Device contract

- **Run:** one load on lane A, whole host. K1a/K1b, then v5 A0/B0/A1/B1/A2 = spin/spin-kio/spin/spin-kio/spin, 12 × 128 tokens per view. There is no separate smoke.
- **Gate:** both B views ≥ +0.5% over every warm A, drift ≤ 3%, 60/60 exact vs `iq3-p49-split32-v1`.
- **Readout:** kept on every outcome. It covers:
  - the engine per arm and copy-engine commands per decode token;
  - the slow fraction;
  - the head/tail/route split and the A carrier;
  - transfer, wall and wait slopes per same-token fill MB;
  - the next-token slope.
- **Decision rule:**
  - B wins and the transfer slope collapses: port `--foreground-io kernel` to the record chain.
  - Collapse, but the wall slope persists: the fill cost moved. Look next at fill volume or a separate copy engine for fills.
  - No collapse: close.
