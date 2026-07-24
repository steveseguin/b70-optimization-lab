# Laguna separate shared gate+up native M=8 MM component pass

Date: 2026-07-24 America/Toronto

The separate gate-then-up native-M8 treatment passed its first and only
authorized four-card component campaign. This is exact component evidence,
not an endpoint benchmark, model generation, or a LocalMaxxing record.

## Sealed campaign

The tooling and authorization identities are:

- component tools commit
  `4cef996c94502ad06233caa55d5be019d13a5114`;
- packet-only authorization commit
  `f04d7431224017859ef892b1251f2a87fc1dee4a`;
- packet
  `data/laguna-s-2.1-shared-gate-up-m8-component-authorization-20260724T051216Z.json`;
- packet raw SHA-256
  `415411d1cce8ce2a9210032e1d54543bd66eff3f26fa08ffc6fa8436002d302b`;
- packet canonical JSON SHA-256, excluding its final newline,
  `75c13ddee2c1e0c8a1256341fa97b928de3c960c2e18a9420ef4f9be58326780`;
- vLLM `503f7784cf9d1704109b1e4650427fb4f417d604`; and
- XPU kernels `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`.

The fresh live-evidence root is entirely on local NVMe:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-up-m8-component-4cef996c9-20260724T051216Z
```

The coordinator acquired the campaign root at
`2026-07-24T05:16:31.543275Z`. All four cards, the aggregate analyzer, the
finalizer, and the final verifier exited successfully. The independently
rerun final verifier also passed from the sealed files.

The principal final artifacts are:

- component aggregate SHA-256
  `d9a8e9ce8a55d79bfb9a33f4a3e926c6ce3c1ceb2039445de137e2102d3a414c`;
- campaign terminal SHA-256
  `f3e477d11bc515fea2f387de4c4d30fcf3958eaec979fd77f8b69bc66099afc3`;
- final manifest SHA-256
  `8aa2a45a8bcc31c5d2e84e5f55568ad43144ebd6c380d6d914cf91f77d10a10d`;
  and
- final manifest coverage of all 675 pre-manifest files, with the complete
  campaign containing 676 regular files.

## Timing result

Timing retained two separate, ordered projections. The control issued a
gate BMM and then an up BMM; the candidate issued a gate native MM and then
an up native MM. Merged N512, logical B16, packing, fusion, reordering,
overlap, and shared-down treatment remained forbidden.

Each arm used 47 distinct inputs, 47 distinct gate weights, 47 distinct up
weights, four independent 47-slot output rings, one 128 MiB touch, 20
untimed warm cycles, and 64 complete cycles with exactly 6,016 projection
calls. The analyzer recomputed all 31 A-B-B-A blocks from raw nanoseconds.

| Rank | BDF | Wins | Control median ms/cycle | Candidate median ms/cycle | Median saving ms/cycle | Relative |
|---:|:---|---:|---:|---:|---:|---:|
| 0 | `0000:23:00.0` | 31/31 | 3.021198 | 2.737756 | 0.285200 | 9.4400% |
| 1 | `0000:27:00.0` | 31/31 | 2.978052 | 2.662922 | 0.308360 | 10.3544% |
| 2 | `0000:43:00.0` | 31/31 | 3.341755 | 3.020350 | 0.321073 | 9.6079% |
| 3 | `0000:47:00.0` | 31/31 | 3.117406 | 2.769954 | 0.348841 | 11.1901% |

Every physical card independently exceeded the frozen requirements of at
least 28/31 wins and at least `0.20 ms` median saving per complete 47-layer
gate+up cycle. The narrowest result was rank 0 at `0.285200 ms`; no
cross-card average rescued a card.

## Exactness and identity

Each card passed 128 pre-timing changing epochs and 32 post-timing exact
replays. Every epoch checked nine boundaries: gate, gate repeat, up, up
repeat, gate SiLU, the actual BF16 multiply, shared down, shared+routed add,
and fixed-rank reduction. That is 1,440 raw-BF16 plus `torch.equal`
comparisons per card and 5,760 across the campaign, all equal.

All four cards independently reproduced the same exactness digests:

- pre fixture
  `e480bfbee66add59da38b786b403872ea7ed7e2dade35a53820f1a4b34eca440`;
- pre output
  `7c6ab1b9d4e62355321a4567e248cd42dfd7b87382f9d7980667f8ba36ce42bc`;
- post fixture
  `b963e1c58965e0612879d3dc300101a460c5db7778eb82dc527d0c11a6dd8a75`;
  and
- post output
  `94e5fd23e806664325c72acedd5571895ca5f47f793a4c5063a830416d92fe0a`.

The sealed dispatch proof retained exactly two ordered native MMs for the
marked pair, incumbent behavior for unmarked paths, and all rejection
classes. The analyzer also revalidated four distinct physical UUID/BDF
mappings, Torch Level Zero UUID byte reversal, one boot
`0b7f98a5-e50a-46a5-81ea-15938b55317a`, the source, binaries, runtime,
model configuration, Stage-0 certificate, packet-only Git lineage, and
strict artifact inventory.

The per-card result SHA-256 values are:

- rank 0:
  `15638454c3d004349cc0946707d74274325df5a8f5bd6700522c12a7e33fb5a2`;
- rank 1:
  `077a816328db9abff39e9bb0688a26c992cf25deeba795bf08757b71f193ecab`;
- rank 2:
  `08949ddd560c5fd0ec9e900ec89ab1d1eeacdd6b8f1d271be602bf2a03299e68`;
  and
- rank 3:
  `8360164baf317a0a34bb25aea5f4895e5a35ecbac860931f5a29abc5be03bd3b`.

## Authorization boundary

Only the verified final manifest enables
`counter_tooling_construction_authorized=true`. Counter execution, endpoint
or service startup, model generation, payload creation, network access,
reboot, record claims, and LocalMaxxing submission remain false.

The next permitted action is to construct, CPU-test, freeze, and
independently audit a fresh cold-counter campaign. Counter execution still
requires its own separate packet-only authorization child. The external USB
remains backup-only.
