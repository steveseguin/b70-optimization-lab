# Laguna scheduler-budget alignment result

Date: 2026-08-02 America/Toronto

Status: **REJECT — correctness gate failed**

The first scheduler arm was not retried. Control A completed 12/12 rows exact
against the frozen repeat oracle and passed the preregistered A-only analyzer.
Candidate B then completed the fixed 12-row sequence, but all eight selected
long rows at or above 8,192 prompt tokens changed output token IDs and text
relative to fresh A. Only the 1K first-live row and the three post-32K
sentinels remained exact. The candidate therefore exited 1, the wrapper did
not invoke the full performance analyzer, and the configuration is rejected.

Structured result:
`data/laguna-scheduler-alignment-ab-result-20260802.json`, SHA-256
`2908e492c11c55d23298530bba345431a33d7581037a729a4fa740f4a605b761`.

## Identity and gates

- vLLM: `4ddb915284d4442885f72bed48311fd04640977c`;
- XPU kernels: `99886d783372e621941228250091dc8ebdc1595d`;
- execution repo HEAD: `76880c691a21222a92ba50535212ad46ffd8470e`;
- execution lock SHA-256:
  `e0f89ec9912f931c96bad11429f4e3dc1477845ee67fa9d965ce4ea858c42d01`;
- control: 8,192 batched / automatic = 8,182 effective;
- candidate: 8,202 batched / explicit 8,192, proven by vLLM's own
  `non-default args` record;
- model contents: every file passed the frozen NVMe manifest;
- both arms: exact per-rank 146/145 target and 14/13 draft capture/replay;
- both arms: clean XPU process captures, teardown, and device-journal scan;
- temporary 16 GiB validation swap: disabled and removed after the stopped
  pair; ordinary `/swap.img` remains.

The pre-arm wrapper stop caused by the invalid `controlD*` character-device
assumption is separately recorded in
`data/laguna-scheduler-alignment-prearm-preflight-20260802.json`. It occurred
before model verification, service launch, or arm A and is not an arm result.

## Correctness failure

Every candidate row passed its intrinsic, retrieval, cache-zero, completion,
and speculative-position consistency checks. Prompt hashes matched 12/12.
The sole per-row benchmark failure was `oracle_exact_if_requested` on the eight
long rows at 8K, 16K, 24K, and 32K. Their first output-token mismatches occurred
at zero-based indices 67 through 91. Complete speculative counters also
differed on those same rows, as expected once generation took a different
path.

The evidence suggests, but does not independently prove, that changing the
prefill chunk partition changed BF16 numerical results enough to alter later
greedy tokens. A uses 8,182-token scheduling; B uses full 8,192-token chunks.
The unchanged 1K row and exact short sentinels are consistent with the effect
being specific to long-prefill partitioning.

## Diagnostic performance only

All frozen speed thresholds happened to pass, but none is promotable because
the candidate is not output-exact:

| prompt | prefill ratio B/A | TTFT ratio B/A | decode ratio B/A |
| ---: | ---: | ---: | ---: |
| 8K median (3) | 1.477478 | 0.682775 | 0.993181 |
| 16K singleton | 1.188145 | 0.843576 | 1.014642 |
| 24K singleton | 1.159524 | 0.865217 | 1.009271 |
| 32K median (3) | 1.004592 | 0.995093 | 0.996443 |
| sentinels (3) | — | — | 0.985853 |

The individual 32K decode ratios were 0.978116, 0.993501, and 1.017595, all
above the protected 0.95 floor. These numbers describe the failed arm only;
they are not an optimization win or record.

## Decision

Close the 8,202/explicit-8,192 configuration. Do not retry, promote, score, or
submit it. The wide-prefill Q/K normalization plus RoPE experiment explicitly
depended on this scheduler pair passing, so its XPU component and endpoint
gates remain unauthorized. Any follow-up that changes scheduler or long-
prefill arithmetic needs a new preregistration and must retain fresh-control
token/text exactness as a hard gate.
