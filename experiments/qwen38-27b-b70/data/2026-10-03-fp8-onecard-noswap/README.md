# One-card FP8 package re-acceptance on the no-swap launcher (October 4, 2026, 01:08-02:06 UTC)

Receipts from
[`run-20260918-fp8-onecard-r312d-campaign.py`](../../scripts/run-20260918-fp8-onecard-r312d-campaign.py), the same
campaign as the [September 18 acceptance](../2026-09-18-fp8-onecard-r312d/), run again because the package launcher
([`serve.py`](../../../../packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py)) changed on September 19: it now starts the
container with `--memory-swap 12g`, equal to `--memory`, so the container gets no swap
([why](../../notes/2026-09-19-container-memory-cap-swap.md)). This is "GPU run 2" of
[the launcher change note](../../notes/2026-09-19-noswap-launcher-change.md). Host kernel 7.0.0-38-generic (the
September run was on 7.0.0-31), same `r312d-c` image, same references.

- Source run directory `/mnt/fast-ai/bench-results/fp8-onecard-noswap-20261003/`, unit `fp8-onecard-noswap-20261003`,
  repository at `92d8c6518`.
- Every comparison is against the same R311b no-MTP references as before
  ([`2026-09-17-fp8-ckpt2`](../2026-09-17-fp8-ckpt2/)) and the long corpus against probe-1's REF5
  ([`2026-09-17-fp8-probe1`](../2026-09-17-fp8-probe1/)).
- The two per-request ladder dumps are represented by their `*-ladder-vs-mtp0.json` verdicts, as before.

## Result

| Profile | Context | Strict vs no MTP | Writing speed | Other gates |
| --- | ---: | --- | ---: | --- |
| `recommended` | 32,768 @ 0.975 | **12/12** twice | **54.062 / 54.031 tok/s** | ladder 64/64 x3, 2K/8K/16K screen, 2,048-30,720 long corpus, chat quality + baseline match, 21-request logprob replay, cache zero |
| `max-context` | 40,960 @ 0.983 | **12/12** | 53.978 tok/s | ladder 64/64 x2, 2K/8K/16K screen |
| `no-quantization` | 28,672 @ 0.975 | **12/12** | 52.203 tok/s | ladder 64/64 x2, 2K/8K/16K screen |
| two-card service restored | 33,024 | **12/12** vs the comm-2 no-MTP reference | 90.235 tok/s | health probe clean before the start |

Speeds are within 0.7 % of the September 18 run (54.236 / 54.011, 54.324, 52.421). Zero GPU fault lines in the kernel
log for the whole campaign: three one-card servers, then a two-card start on the same boot, which is the sequence that
faulted three times in September.

## The reading this run was owed: container memory with no swap allowance

The one-card profiles were the open question of the launcher change, because their headroom under the 12 GiB limit had
only been estimated (8.3-8.8 GiB of anonymous memory). Measured just before each stop (`cgroup_memory` in
[`results.json`](results.json)):

| Profile | Anonymous memory | Headroom to 12 GiB | `oom_kill` | Swap peak | Times at the limit |
| --- | ---: | ---: | ---: | ---: | ---: |
| `recommended` | 7.70 GiB | 4.30 GiB | 0 | 0 | 13,801 |
| `max-context` | 7.01 GiB | 4.99 GiB | 0 | 0 | 13,865 |
| `no-quantization` | 6.85 GiB | 5.15 GiB | 0 | 0 | 11,566 |

All three sit below the estimate, with more room than the two-card profile has (8.99 GiB anonymous, 3.01 GiB spare).
The container reached its limit thousands of times and each time dropped clean file pages instead of swapping, which
is the launcher change working as intended.
