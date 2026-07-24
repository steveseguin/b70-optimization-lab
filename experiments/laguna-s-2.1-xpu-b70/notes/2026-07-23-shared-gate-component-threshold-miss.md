# Shared-gate component threshold miss

Date: 2026-07-23 EDT / 2026-07-24 UTC

## Classification

- Outcome: valid rank-0 component measurement; preregistered timing threshold
  miss.
- Authorization packet:
  `data/laguna-s-2.1-shared-gate-m8-component-authorization-20260724T025700Z.json`
- Packet SHA-256:
  `f748730bbb30be5268117015ffd8b8f88e81749eba4af9c3ca6ef6d99079c4ef`
- Authorization commit: `3c2579115875463a81d5fe7edb4373af79f9b8d1`
- Tools commit: `c800d00580df3624b29e027ed22938936e1ed4ad`
- Artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-component-c800d0058-20260724T025700Z`
- Card 0 result:
  `component_failed_stop_before_counters`, with
  `kind=timing_threshold`.
- Cards 1 through 3: not started, as required after the first per-card miss.
- Analyzer and counters: not started.
- Every downstream authorization remained false, including model generation,
  endpoint, service, network, payload, reboot, and submission.

This packet and artifact root are terminal and must not be reused.

## Exactness and dispatch

The marked M=8 shared-gate path used one `torch.mm` call with zero `torch.bmm`
or fallback calls and exactly matched its literal raw-BF16 reference. The
M=1-through-M=7, unmarked M=8, and marked-prefill controls stayed on their
required `torch.bmm` paths.

All 128 distinct pre-timing epochs and all 32 distinct post-timing epochs
reported both `raw_uint16_equal=true` and `torch_equal=true` for every
comparison. The timing preflight also established raw equality among the
literal BMM, literal MM, preallocated control output, and preallocated
candidate output before any warm-up or timed arm.

## Frozen timing result

The valid isolated primitive protocol used:

- 47 distinct 1,572,864-byte weights;
- 20 warm cycles per arm;
- 31 A-B-B-A paired blocks;
- 64 47-call cycles per arm and 3,008 calls per arm;
- one 128 MiB eviction pass before each arm;
- device synchronization only at arm boundaries;
- distinct preallocated input, weight, control-output, and candidate-output
  storage.

The native M=8 BF16 MM candidate beat the literal stride-zero
B=8/M=1 BF16 BMM control in all 31 of 31 blocks. Savings ranged from
`0.103621140625 ms` to `0.133871273437 ms` per 47-call cycle, with:

- mean saving: `0.12204077872983868 ms`;
- median saving: `0.12085622656249995 ms`;
- frozen minimum wins: 28 of 31;
- frozen minimum median saving: `0.150 ms`.

The win-count condition passed, but the median-saving condition did not.
No block individually reached the frozen `0.150 ms` saving. The stable
positive signal does not override the preregistered threshold and is not an
accepted optimization.

## Preserved campaign evidence

- `campaign-start-checkpoint.json`:
  `a22fe7b6833a03194c4ba33581888c494ae47c6224327f5007e56115597736c1`
- `card0/pre-tensor-identity-checkpoint.json`:
  `385be6570bd70bb857a9fe9f0eed48b281bbab61b0f6355b8784e495ab82220c`
- `card0/tensor-work-started-checkpoint.json`:
  `857bc82c2af0b9618d285b28c5bb27285ce1a9316fafa74fd6e55e1e1cd5da9c`
- `card0/runtime-card-binding-checkpoint.json`:
  `d6216442d7f0551f088d34f92ce3e16968fd417936cbd831bebe89ee9d4ed90f`
- `card0/constructor-scope-proof.json`:
  `9fbff9fe7f4ddada18e40749ffc03c3208abcc462dfdb5d4d0847cfa82d9b1dc`
- `card0/dispatch-proof.json`:
  `58ca2d1777c484656f59812f8c47e07efb41868a9269ff32f633e0d5108ebc6e`
- `card0/timing.json`:
  `0562d29903b22475db30a23d1b1a674b5c37fae0d1c9d5b5ec414183dcdce313`
- `card0/component-result.json`:
  `ebf755488cb71b506f259ccaf9c10f7b3f1677348544ebbac41f6620091354c1`
- `rank-0-terminal.json`:
  `02d0e6c57d996a8362e8005fcc86655104212206a643860f0dd37650e7b9aa66`
- `campaign-terminal.json`:
  `5b40fe51537a7e5999e263c2b5ad604d1e3b61efd38ea4f281ef1f173a8964ff`

## Decision

Do not rerun this packet and do not weaken the frozen threshold. The simple
shared-gate BMM-to-MM substitution is a reproducible sub-threshold positive,
not a bankable component win. Any follow-up must make a materially stronger
candidate—such as a separately justified combined occupancy change or a
deeper shared-expert kernel improvement—and preregister its own acceptance
rule before device measurement. This result alone does not authorize
counters or an endpoint benchmark.
