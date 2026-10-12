# Completed CPU gates

No device ran. No device speed or residency is qualified.

| Gate | Completed evidence |
| --- | --- |
| Suite prefixes | GNU: three prompts × three capacities; nine cases, 72 tokens, 3,456 layer fixtures exact against the v2 oracle |
| Development pipeline | GNU: none, all-hit, all-miss and MTP at 4,096; four cases, 32 tokens, 1,536 layer fixtures exact |
| Intel composite | MTP with two forced misses and one hit at 4,096; four tokens, 192 layer fixtures exact; diagnostic Python mailbox injection |
| Block-boundary rollback | Two controllers × three modes × two compilers; 12 cases, 96 tokens, 384 layer fixtures; discarded position-32 speculative halves checked |
| ASAN/UBSAN boundary rollback | 6 cases, 48 tokens, 192 layer fixtures; two discarded-boundary cases |
| Beyond-budget selection | Both host compilers; 854,164 checks, 96 selection fixtures, 32 attention fixtures and 96 nonfinite fixtures |
| Full operator arithmetic | Six capacity/compiler fixture arms plus two linked arms; 21,528 checks |
| Host validation-only | Three finite-grid K2 arms and one nongemv arm; 6,401 checks, separate from arithmetic evidence |
| Actual Engine native controller | 1,109 cases; native/Python token, fixture and final-state equality |
| Native standalone controller | 1,123 cases each in ordinary, ASAN/UBSAN and TSan builds |
| Native mailbox faults | Five checks and 32 repeated requests in each of three builds |
| Mini pipeline | GNU 130 cases, Intel seven, ASAN/UBSAN seven |
| MTP isolation | Seven cases in each of GNU, Intel and ASAN/UBSAN builds |
| Draft authentication | Four safe CPU rejection cases |
| Draft capacity capture | Two GNU references at 4,096 and 32,768, 94 confirmed rows each; both match 63 frozen packet38 valid-prefix fixtures |
| Ownership and lifetime | Ten suites across both compilers; 15 prepared-invalidation ASAN/UBSAN checks |
| Argument bounds | 16 serializer checks; 410 linked device captures, maximum 752 bytes; 1,025-byte negative compile refused |
| Wrappers and admission | 37 inherited window tests; ten new tests covering 22 window/capacity/manifest combinations; 27 memory admission checks |

The full seal binds 30 required gate receipts and
46 retained binary hashes. See
[build-receipt.json](build-receipt.json), [BINARY-HASHES.md](BINARY-HASHES.md) and
[CPU-REPRO.md](CPU-REPRO.md). Validation-only counts never substitute for
arithmetic comparisons. Historical failures remain in their ledgers/archives.

All coordinator device windows, measured short-context wall cost, physical
residency/driver overhead and long real conversations remain unqualified.
