# Laguna shared-down native M=8 BF16 MM component pass

Date: 2026-07-23 America/Toronto

The down-only native-M8 shared-expert treatment passed the frozen four-card
component gate. This is a component result, not an endpoint benchmark or a
LocalMaxxing record.

## Result

The passing root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-down-m8-component-20260723T155703Z
```

The aggregate artifact is `aggregate.json`, SHA-256
`ea71971b368ce9b9e930577b673e983124b0e5686d5d780fc241ac4104f2a1d6`.
The frozen analyzer classified it
`component-passed-counter-tooling-freeze-next`.

| Rank | BDF | Wins | Control ms/cycle | Candidate ms/cycle | Saving ms/cycle | Relative |
|---:|:---|---:|---:|---:|---:|---:|
| 0 | `0000:23:00.0` | 31/31 | 2.309867 | 1.698725 | 0.610891 | 26.4470% |
| 1 | `0000:27:00.0` | 31/31 | 2.391377 | 1.745049 | 0.647105 | 27.0599% |
| 2 | `0000:43:00.0` | 31/31 | 2.313656 | 1.715529 | 0.597514 | 25.8255% |
| 3 | `0000:47:00.0` | 31/31 | 2.361052 | 1.771314 | 0.612379 | 25.9367% |

Every card independently exceeded the frozen requirements of at least 28/31
block wins and at least 0.15 ms median saving per complete 47-layer cycle.
The narrowest observed margin was rank 2 at 0.597514 ms, nearly four times the
absolute threshold.

## Exactness and identity

Each card passed 128 changing exactness epochs, the actual checkpoint-selected
`RowParallelLinear` path, and a 32-epoch post-timing replay. The candidate,
candidate repeat, shared+routed add, and fixed-rank simulated sum were raw
bitwise equal to control at every declared boundary. The marked M=8 path
issued exactly one native MM; unmarked M=8 and marked M=7 issued exactly two
incumbent BMMs; the bad-layout candidate failed closed.

All four cards reported the same aggregate fixture hash
`3e28840809747843474a15f7858db9b7d1d4d70b4fbe71c47c7a2aa117eeff90`
and output hash
`ae8c34ea1bb5904466a702412a1ccc1f6843d3bed05e948f079e82647b4f33a7`.
The analyzer verified four distinct UUIDs/BDFs, one boot, one clean main
commit, and the frozen vLLM, kernel, binary, configuration, environment, and
tool identities.

The captured source identities were:

- main `480406187af3ae01ca1f4eaedf4810fee6c1ecfd`;
- vLLM `75d4660463407975c16bd33711499ca560bf2034`;
- XPU kernels `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- component harness
  `df8496f1f405e8b786dff0b96b7c320944c5d0133cce0bfcc2e36150ab1e0f12`;
  and
- aggregate analyzer
  `945810c50eeeea99f532c3e62ee5bf289677e3706d80965f966400bfab35911b`.

The structured summary is
[`data/laguna-s-2.1-shared-down-m8-component-pass-20260723.json`](../../../data/laguna-s-2.1-shared-down-m8-component-pass-20260723.json).
The full protocol and the two sealed preflight-tool failures remain in the
[preregistration](2026-07-23-shared-down-native-m8-mm-preregistration.md).

## Authorization boundary

This pass authorizes only construction, source freezing, validation, and
independent audit of dedicated cold hardware-counter tooling. It does not
authorize counter execution, an endpoint service, model generation, a
payload, or a LocalMaxxing submission. Those flags remain false in every card
artifact and the aggregate.

The next step is to implement the preregistered two-pair per-card cold
`unitrace` gate, freeze its source and hashes, and audit it before running any
counter capture. All live evidence remains on local NVMe; the external USB
remains backup-only.
