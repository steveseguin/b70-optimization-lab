# DFlash committed-row cost profile

Date: 2026-08-13

A default-off diagnostic (`LLAMA_DFLASH_COMMITTED_ROW_PROFILE=1`) synchronized
the draft context before and after delayed committed-prefix processing and
timed the complete target-feature encode plus DFlash decoder-KV injection.
The env-off path is unchanged.

At 128 reported calls the fit was:

`time_ms = 1.683 + 0.125 * committed_rows`

Mean rows/call were 3.734 and mean time was 2.151 ms. Bucket means ranged from
1.831 ms at one row to 3.698 ms at 16 rows. The diagnostic preserved all
canonical target output hashes and acceptance counts; its displayed request
rates are non-comparable because explicit synchronization perturbs scheduling.

For the budget-15 projection, only the row-dependent component needs a
correction because the existing round-count scaling already handles the fixed
component. With 256 emitted tokens and linear/tree round counts 84/66, 59/48,
and 49/42, the correction is about 0.104/0.124/0.109 ms per tree round. Adding
that to the measured branch-layout overhead produces
74.585/102.078/118.877 tok/s, mean 98.513, leaving approximately 0.770 ms/round
before the missing integration tail.

- source profiler: `36b967a93`;
- config: `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-committed-row-profile256.json`;
- JSONL: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-committed-row-profile256-20260813.jsonl`, SHA-256 `4e6a9b291ca1b275f4b3a9b9a337ce584df056f10bf5eacd7bfe12dbcb050d8e`;
- log: `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dflash-committed-row-profile256-20260813-committed-row-profile.log`, SHA-256 `fe3bb2bdb87c389e4cd0d929560d46421385d45d1ce9a3f4396497412ea32617`.

This remains a projection, not an integrated throughput result.
