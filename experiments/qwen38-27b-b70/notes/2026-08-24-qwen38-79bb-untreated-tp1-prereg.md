# 79bb literal-current untreated TP1 qualification preregistration

Date: 2026-08-24. State: preregistered, not yet launched.

## Goal and scope

Qualify the newest exact upstream stack without losing the protected Qwen3.8
27B AutoRound INT4 performance class. This is the required first GPU step
before current-base TP2, TP4, and the wider neural.download MTP/context/KV/graph
coverage matrix.

This program is untreated-first and TP1-only. It contains no source patch,
binary replacement, generated kernel, decision packet, seeded cache, or other
runtime compatibility overlay. It may run only the exact both-current image
listed below. The separately preserved 0ecc 38-decision packet is historical
evidence and is neither copied nor interpreted by this program.

## Frozen source and image identity

- vLLM main: `79bb395eea64dbfef99a55f010d2854db71f8571`, tree
  `3dc459a78f843186bb8a510631f9f1d34448a243`.
- vLLM XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`,
  tree `e7e7d1063f232a383c98c1820cebb94c45b4906e`.
- Official XPU nightly base digest:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
- Stock-base-kernel control image:
  `sha256:9f8000f2317de47098161b4da63efb61994a51d9edd8bfe902818e8e685e075a`.
- Both-current image, and the only image this program may execute:
  `sha256:786681b8aa4150d30e12af93b3038a03daba110719bf650a5c9d7c8804e0bdf3`.
- Build receipt SHA-256:
  `92e8fa48ad09ee025fd16a8f29440d622715df0c300fade3023317cd756d948d`.
- Host kernel: `7.0.0-30-generic`; initial required boot ID:
  `086de284-0771-4269-9cb2-e064fe303e40`.

The build used a zero-source-overlay `--build-all`. Static image, wheel, Rust,
kernel-wheel, receipt, archived-inspect, and external-archive checks passed;
GPU qualification remains intentionally pending. The receipt's conservative
build-time `promotion.order` is not launch authorization. This later
preregistration narrows the first runtime gate to the active both-current
candidate; the stock image is retained as rollback and optional follow-up
attribution evidence but is not an arm in this bounded program. A current
target pass does not require an older-kernel lane, while a speed-only miss may
justify that attribution in a separate preregistered program.

If live vLLM main, XPU-kernel main, the official nightly digest, the exact
image, or the host kernel or boot changes before or during the chain, the
chain stops stale. The launcher accepts only a clean pushed lab `main`, freezes
its exact commit in the input snapshot at launch, and stops if that commit
changes during the chain. A newer upstream main requires a new build and
preregistration; an older artifact must never be relabeled as current.

## Atomic prerequisites

The launcher must start from a clean accelerator-runtime environment, on
clean pushed `main` equal to live `origin/main`, with no containers, servers,
render-node holders, or other GPU leases. It holds the Muse lock, host
benchmark lock, and all four per-GPU leases continuously across the hardware
gate and all model arms.

Before model execution, a fresh post-reboot hardware gate must prove:

- all four exact B70 device identities;
- a compute operation on every card;
- the four-device peer-read oracle;
- a four-rank XCCL barrier/allreduce;
- no combined `ONEAPI_DEVICE_SELECTOR` and `ZE_AFFINITY_MASK` use;
- clean kernel journal and taint gates; and
- atomic ownership of the inherited campaign locks.

The gate and active results must be separate, non-nested ext4 roots. The
program is all-or-nothing and cannot resume an individual arm. Every input is
copied into a read-only snapshot and checksummed before the first arm; source,
nightly, image, repository, host, boot, input, and hardware-gate identities are
rechecked between arms.

## Capped untreated arms

Maximum: three serialized TP1/GPU0 arms on one fresh compilation cache. All
use Qwen3.8 27B AutoRound INT4, MTP0, F16 KV, 32K maximum model length,
`FULL_AND_PIECEWISE` graph mode with capture sizes `[1,2]` and maximum 2, one
sequence, 1024 batched tokens, 0.90 memory utilization, async scheduling,
prefix caching off, chunked prefill on, returned token IDs, and
`PYTHONHASHSEED=0`. No build, download, or other workload may overlap them.

1. Fresh diagnostic on port `19761`: 25 unique cold prompts, 512 generated
   tokens, EOS ignored. The conventional 99-interval median floor is
   `30.2178 tok/s`.
2. Exact-cache strict replay A on port `19762`: natural EOS plus the complete
   quality battery and frozen baseline. Its median floor is
   `30.31067504052998 tok/s`.
3. Exact same-cache strict replay B on port `19763`: natural EOS without a
   duplicate quality pass. Its median floor is also
   `30.31067504052998 tok/s`.

The cache is fully inventoried after the fresh compile and must remain
byte-identical across both replays. The diagnostic and both strict arms must
pass exact model identity, the arithmetic canary, cached-token-zero and fresh
response checks, request/response accounting, graph/image/device/source
identity, container cleanup, host postflight, and kernel-journal gates.
Replay A additionally must pass seven exact cases, eight repeats, the
8K/7,617-token needle, and 24/24 frozen baseline comparisons. Replay A/B full
and first-100 token-array equality is reported but remains non-gating, matching
the prior certified protocol.

## Frozen interpretation

- If every non-speed and speed gate passes, record
  `pass-untreated-current-base`. Stop without testing any preserved decision
  packet. The zero-overlay 79bb/baaa stack is then eligible for separately
  preregistered TP2 qualification.
- If every non-speed gate passes but any protected speed floor misses, record
  `complete-speed-only-regression-no-overlay-run` and exit nonzero. Preserve
  the measurements as regression evidence. A compatibility packet may be
  derived only in a new versioned and preregistered program; this launcher
  must not continue automatically.
- If any non-speed gate fails, record `control-non-speed-failure`, exit
  nonzero, and do not treat the run as performance evidence.
- Interruption, infrastructure failure, sealing failure, or freshness loss is
  `failed-incomplete`, never pass.
- Final status, aggregate JSON, frozen inputs, arm evidence, and failure
  evidence are written atomically and covered by a recursive SHA-256 manifest
  and digest before filesystem sync. The compiled cache itself is excluded
  from that outer manifest because its complete frozen manifest is included
  in the sealed arm evidence.

No outcome lowers or replaces historical captures. Protected diagnostic
floors remain TP1/TP2/TP4 `30.2178 / 48.8301 / 71.5488 tok/s`; protected
strict floors remain TP1 `30.31067504052998`, TP2 `49.01965141150585`, and
TP4 both at least `71.29326283364946` with at least one repeat at or above
`71.39843006187554`.

After a TP1 pass, qualify TP2 and then TP4 on the same literal-current source
identity. Remap and separately version the preserved 78-decision TP2 and
152-decision TP4 packets only if an untreated speed-only miss requires them.
TP4 remains fixed at 0.60 memory utilization; 0.90 is forbidden. Only after
current-base topology qualification should the campaign expand into the
site-facing MTP, context through 32K+, KV, graph, quant, and recipe matrix.
