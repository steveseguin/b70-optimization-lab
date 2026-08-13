# DDTree bulk unified-KV metadata: no win

Date: 2026-08-13

The branch-layout probe originally spent 0.213 ms/round copying seq0 to an
average 6.74 temporary leaf IDs and 0.172 ms/round removing those IDs. A
bounded experiment added a one-scan multi-destination copy API to the base KV
cache, forwarded it through the Muse MSA/ISWA wrappers, and replaced repeated
leaf removal with the existing one-scan `seq_keep(0)` operation.

The repeated 256-token probe was exact on the unchanged ordinary outputs and
reported at 160 eligible rounds:

| component | original | bulk experiment | delta |
|---|---:|---:|---:|
| build | 0.009 ms | 0.009 ms | 0.000 ms |
| fork | 0.213 ms | 0.119 ms | -0.094 ms |
| steady target layout | 0.234 ms | 0.295 ms | +0.061 ms |
| cleanup | 0.172 ms | 0.241 ms | +0.069 ms |
| total | 0.628 ms | 0.664 ms | +0.036 ms |

The bulk fork worked, but `seq_keep(0)` was slower than the old repeated
targeted removals and the total diagnostic did not improve. All canonical
hashes and accepted counts stayed exact; linear-prefix parity was 1,137 with
zero mismatches.

- experiment source: `4c897a4e6`;
- revert: `630dd63b0`;
- config: `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-ddtree-bulk-kv-probe256.json`;
- JSONL: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-ddtree-bulk-kv-probe256-20260813.jsonl`, SHA-256 `c0e2b6ab4a0bc31c075983f5f739f4eeae3f640f8ed232a767f9a3178752c781`;
- server log: `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dflash-ddtree-bulk-kv-probe256-20260813-bulk-kv-shadow.log`, SHA-256 `5ed22602b9d2a1c3fd083e44c080d22a8b8f86592813b4fc07336086145fdd37`.

Decision: preserve and revert. The measured metadata lane is closed in this
form.

