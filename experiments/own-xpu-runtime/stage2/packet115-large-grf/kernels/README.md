# Packet 115 expert-only kernel candidates

All five original headers are byte-for-byte snapshots under `frozen/`; their source paths and SHA-256 digests are in `provenance.json`. Existing packets were not edited. Baseline dependencies initially point to packet 103 after its tile16 down promotion.

| Arm | Callable type | Arithmetic-preserving changes |
| --- | --- | --- |
| production gate/up | `p90exp::Kernel<IQ2_S,2560,64,false,true>` | Existing 840-byte half-cache rows. |
| production down | `p100::Kernel<2>` | Existing tile16 byte layout. |
| e3-next | `p115e3::Kernel<>` | Packet 95 rejected next-block grid lookahead. Read the same exactly decoded half scale from the existing FP32 half cache instead of decoding FP16 repeatedly; set row stride to 840. |
| iq4-bytepair | `p115down::Kernel<>` | Packet 99 Mode4 byte-pair lookup in 128-word SLM table, using packet 103 tile16 addresses. Same 16 ordered chains and adjacent tree. |
| v4-batch2-shared | `p102::Kernel<2,true>` | Packet 102 final V4 source, only include paths adapted. Shares each eight-element input load across gate/up; batches two grid lookups. |
| e5-shared | `p115e5::Kernel<>` | Packet 102 attempt1 V8 shared structure, batch1. Implements packet 95 E5's shared gate/up input scheduling with eight ordered chains per stream and four physical lanes per row. Distinct from V4 batch2; no reassociation or packed arithmetic. |

`cpu.cpp` executes the full output/status/error paths with production-size rows, partial groups, invalid and partial routes, inactive/preexisting error, nonfinite and signed-zero inputs. Raw FP32 chains and the final adjacent tree are compared to packet 49. It also compares all IQ2 lookup indices/signs across six representative half classes, and every IQ4 byte/half combination in both nibble phases. All comparisons are byte or bit equality, including NaN payloads. CPU proof is a prerequisite; device byte identity remains a separate mandatory gate.

Compile in host-only mode with strict FP32 flags, for example `-DOWN_RT_HOST_ONLY -std=c++20 -O2 -ffp-contract=off`, respecting the shared compile lock. Run each of `production`, `e3-next`, `iq4-bytepair`, `v4-batch2-shared`, `e5-shared` with a separate output directory. The parent packet owns the GNU/Intel two-process runner and receipts; this directory performs no GPU work.

GNU and Intel host-only gates passed in two fresh processes per view (20 runs total): 19 cases, 110592 raw FP32 chain comparisons and 3456 raw FP32 tree comparisons per run. All full output/status streams matched production byte-for-byte. The source-bound receipt is [`../evidence/cpu-byte-identity.json`](../evidence/cpu-byte-identity.json). This proves the CPU implementation only; device arithmetic and speed remain separately gated.

The first E5 image used separate gate/up status epilogues and produced three predicate-flag stores plus six loads. It failed the zero-spill gate even though scratch-memory messages were zero. Its exact source and assembly are retained in `../evidence/e5-first/`. The current E5 uses packet 102 V4’s common output/status epilogue with its V8 arithmetic chains and tree unchanged; the register gate is rerun rather than relaxing the criterion.
