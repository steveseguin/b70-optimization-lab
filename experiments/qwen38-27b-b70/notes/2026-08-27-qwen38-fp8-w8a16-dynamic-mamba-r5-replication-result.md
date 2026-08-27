# Qwen3.8 FP8 W8A16 dynamic MTP replication result

The active-Mamba-allocation profile reproduced and passed its concurrent
quality gate. It is now a quality-qualified measured service profile.

| Attempt | fresh single-user tok/s | c64 aggregate tok/s |
| --- | ---: | ---: |
| R4 | 83.665057 | 1,087.492388 |
| R5, new container and compile cache | 83.695329 | 1,082.585597 |
| two-attempt median | **83.680193** | **1,085.038992** |

R5 retained **99.55%** of R4 aggregate throughput, above the preregistered
1,033.117768 replication floor and the original 875 tok/s objective. Its c64
batch returned all 8,192 requested tokens with complete token IDs, zero cached
tokens, and zero cross-base output collisions.

The same live service then passed **512/512 exact-answer requests** across
eight synchronized c64 rounds. Every round was 64/64 with zero nonzero cached
token reports. The sequential suite also passed 7/7 exact cases plus 8/8
repeat stability and exactly matched the static-MTP2 baseline. The engine
remained healthy and shut down with exit code zero.

This profile uses dynamic speculation: the one-user shape requests MTP2, while
two or more active requests use MTP1. Its service limit is 256 total tokens;
the c64 number is not a 32K-context result. Greedy tokens can still vary with
batch shape, so the concurrent throughput evidence is classified as an
output-isolation-qualified shape variant rather than universal sequential
token identity.

The exact patches, staged image build, launch wrappers, benchmark harnesses,
raw receipts, and checksums live in this repository. Raw R5 evidence is in
[`../data/qwen38-fp8-w8a16-mtp2-dynamic-mamba-20260827-r5/`](../data/qwen38-fp8-w8a16-mtp2-dynamic-mamba-20260827-r5/).
No value is interpolated or extrapolated.
