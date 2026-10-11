# Kernel capture audit

All 41 instantiated kernel functor classes are compiled through
`packet23::checked(F)`, which asserts `sizeof(F) <= 1024`. The source mirror
rejects any submission it cannot wrap. An oversized 1,025-byte control must fail
compilation. These are host-compiler functor sizes, extracted from ELF symbols;
the device ABI can pack fields differently. Original W0 reported 6,036 argument
bytes for Chain; its C++ functor measured 6,056. K0 is the device ABI proof and
has not run in this CPU-only repair. Current largest functor: 224 bytes.

Immutable descriptor and pointer tables are created when bindings are first
planned, copied into owner-tracked device USM, and cached by their full bytes.
Repeated bindings reuse the table. Changed layer-streaming bindings produce a
new table. Tables contain no SYCL object and are released by normal owner
shutdown. The copies finish before the corresponding compute submission.
No arithmetic expression, reduction order, phase barrier, or BF16 store moves.
Imported packet6/7/8 sources stay read-only; kernel_overlay.py records and
asserts each storage-only substitution in the packet-local build mirror.

Raw fully qualified symbols and measurements: [kernel-sizes.json](kernel-sizes.json).

| # | Kernel class / specialization | Before (bytes) | After (bytes) |
| ---: | --- | ---: | ---: |
| 1 | `Finish` | 16 | 16 |
| 2 | `Fused` | 1560 | 224 |
| 3 | `Ref` | 176 | 176 |
| 4 | `CanaryIncrement` | 8 | 8 |
| 5 | `ReferenceElementwise` | 40 | 40 |
| 6 | `iq3::Decode::run<16u>` | 32 | 32 |
| 7 | `iq3::Decode::run<32u>` | 32 | 32 |
| 8 | `iq3::Multiply::run<16u>` | 136 | 136 |
| 9 | `iq3::Multiply::run<32u>` | 136 | 136 |
| 10 | `iq3::Step` | 696 | 16 |
| 11 | `iq3::expanded::Decode` | 40 | 40 |
| 12 | `iq3::expanded::Multiply::run<(iq3::Type)0>` | 112 | 112 |
| 13 | `iq3::expanded::Multiply::run<(iq3::Type)11>` | 112 | 112 |
| 14 | `iq3::expanded::Multiply::run<(iq3::Type)14>` | 112 | 112 |
| 15 | `iq3::expanded::Multiply::run<(iq3::Type)18>` | 112 | 112 |
| 16 | `iq3::expanded::Multiply::run<(iq3::Type)1>` | 112 | 112 |
| 17 | `iq3::expanded::Multiply::run<(iq3::Type)20>` | 112 | 112 |
| 18 | `iq3::expanded::Multiply::run<(iq3::Type)21>` | 112 | 112 |
| 19 | `iq3::expanded::Multiply::run<(iq3::Type)22>` | 112 | 112 |
| 20 | `iq3::expanded::Multiply::run<(iq3::Type)23>` | 112 | 112 |
| 21 | `iq3::expanded::Multiply::run<(iq3::Type)30>` | 112 | 112 |
| 22 | `iq3::expanded::Multiply::run<(iq3::Type)8>` | 112 | 112 |
| 23 | `iq3::kopt2::Multiply::run<32u>` | 1408 | 80 |
| 24 | `iq3::kopt2::Multiply::run<64u>` | 1408 | 80 |
| 25 | `iq3::kopt2::Stream` | 24 | 24 |
| 26 | `iq3::kopt3::Multiply::run<false>` | 1360 | 32 |
| 27 | `iq3::kopt3::Multiply::run<true>` | 1488 | 160 |
| 28 | `iq3::kopt4::Combine` | 48 | 48 |
| 29 | `iq3::kopt4::Projection::run<(iq3::Type)20>` | 184 | 184 |
| 30 | `iq3::kopt4::Projection::run<(iq3::Type)21>` | 184 | 184 |
| 31 | `iq3::kopt4::Projection::run<(iq3::Type)22>` | 184 | 184 |
| 32 | `iq3::kopt::Multiply::run<16u>` | 688 | 64 |
| 33 | `iq3::kopt::Multiply::run<32u>` | 688 | 64 |
| 34 | `ng::Kernel` | 216 | 216 |
| 35 | `ownrt::SyclDevice` | 1 | 1 |
| 36 | `packet18::Chain` | 6056 | 56 |
| 37 | `packet18::Glue single` | 712 | 24 |
| 38 | `packet18::Glue parallel` | 736 | 48 |
| 39 | `packet18::Rank` | 728 | 40 |
| 40 | `packet21::Batch` | 1104 | 88 |
| 41 | `tp2::Context` | 1 | 1 |

Parameter-upload ordering is also checked: native backends assign compute event
IDs after the submission has finished preparing its tables. This keeps the
owner's event ledger sorted when preparation adds tracked copy events. One CPU
control checks metadata upload/cache reuse and the resulting event handle; the
queue source gate binds the check to both native backends. Earlier packets are
unchanged; the one-card backend change lives in the asserted local overlay.
