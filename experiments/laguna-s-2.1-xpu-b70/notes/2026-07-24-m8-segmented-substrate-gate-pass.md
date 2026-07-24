# Laguna M8 segmented graph substrate gate pass

Date: 2026-07-24 America/Toronto

## Result

The preregistered substrate-only segmented graph gate passed on all four Arc
Pro B70s. It executed no model, tokenizer, endpoint, prompt, generation,
benchmark, external-USB access, payload, or LocalMaxxing action.

The approved Laguna record remains unchanged at
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- tool commit:
  `c21aa5a275f49fd403990f74dc7d268942a65f64`;
- tool SHA-256:
  `58fb19e162dc8fe5d45c2475a68ad3f6c05c8a74d283bc9d5a29bbdf842cf173`;
- segmented vLLM:
  `0964fe3d1b3508e39ee2455f70f1dbc7b13b0fd5`;
- preregistration:
  [2026-07-24-m8-segmented-substrate-gate-preregistration.md](2026-07-24-m8-segmented-substrate-gate-preregistration.md);
- structured result:
  `data/laguna-m8-xccl-segmented-substrate-pass-20260724.json`; and
- sealed internal-NVMe root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-xccl-segmented-substrate-c21aa5a27-20260724T145032Z`.

## Exact checks

Each rank ran 128 changing replays of:

```text
graph prelude
eager owner-partitioned embedding BF16 all-reduce
graph bridge
(eager BF16 all-gather -> graph fixed-rank sum/next-input bridge) x 96
```

The last fixed-rank graph also wrote the final tail, giving exactly 97 eager
collectives and 98 graph segments per replay.

| Gate | Per rank | Fleet | Result |
|---|---:|---:|---|
| raw comparisons | 24,832 | 99,328 | pass |
| changed input transitions | 127/127 | 508/508 | pass |
| changed tail transitions | 127/127 | 508/508 | pass |
| persistent tensors checked | 486 | 1,944 | pass |

All four ranks reported the same final tail hash:
`89bb0581665522159320f9355fec375eca368cc7a5818e4dff6d7a9ae6563d6a`.
Their final input hashes and pointer-signature hashes were distinct as expected
for different rank-local inputs and address spaces. Every pointer signature
remained unchanged before every replay.

Capture construction took 0.833-0.943 seconds per rank. The complete 128-replay
changing-input validation took 5.4499 seconds per rank. These are component
diagnostics, not model throughput measurements.

## Operational audit

Preflight found:

- all relevant services inactive;
- no foreign vLLM, Laguna, torchrun, probe, or trace process;
- exactly four distinct B70 UUID/BDF pairs at `23`, `27`, `43`, and
  `47:00.0`;
- about 43 MiB / 0.13% memory used per card;
- boot `0b7f98a5-e50a-46a5-81ea-15938b55317a`;
- kernel `7.0.0-28-generic`, taint `0`; and
- `/mnt/fast-ai` backed by `/dev/nvme0n1p2` ext4.

Post-run audit found no lingering process, kernel GPU error/reset/hang/fault,
device loss, or taint change. The five result files are mode `0444` and the
root is mode `0555`. An independent read-only result audit recomputed the
fleet totals, compared the embedded and standalone rank objects, verified the
tool blob against its committed SHA, and reported pass with no blocker.

Runtime library identities resolved from the frozen `LD_LIBRARY_PATH`:

- oneCCL `libccl.so.1`:
  `ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3`;
- SYCL `libsycl.so.8`:
  `0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f`;
- Level Zero driver:
  `26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a`;
  and
- Level Zero loader:
  `0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0`.

## Disposition

This pass proves the corrected eager-collective/graph-segment substrate can
carry fresh changing bytes through the required dependency chain. It does not
prove that the real Laguna wrapper produces the intended target trace,
preserves model output, or saves time.

The pass authorizes construction and source review of the actual target-M8
model-forward and PTI trace/timing gate. It does not yet authorize an endpoint,
benchmark generation, payload, or submission. That next gate must bind the
NVMe model revisions and approved record flags, prove the real target uses 97
eager collective callbacks and 98 graph segments with no compilation/fallback,
and compare exposed target bytes before any performance claim.
