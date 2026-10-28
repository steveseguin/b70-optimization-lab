Backlog4 dense width1/2/3 kernel gate — PREPARED SOURCE ONLY,2026-10-28
No compile, tensor extraction, test execution, GPU/model load or timing performed.
Root's L4quality work remains next. No canonical source changes.

One material actual registered shape: layer1 blk.1.gdn.qkv / blk.1.attn_qkv.weight,
Q5_K13,10240outputs×2560columns,row1760B,total18,022,400B. selection.hpp identifies
that exact tensor. Historical dense-decode/results.json reports7calls/half,
50.19us/call and351.4us/half for this site class: enough to select a real dense
class, not a current bottleneck/endpoint forecast. Do not generalize oneformat.

Reuse: bench_block.cpp include/submit skeleton, production DenseBlockOperation
<13,true> and its V2scalar dispatch; existing reuse2::Op/Block32 and block_element
for fixed1weightrow×2or4token tiles,4subgroups,128GRF. No arithmetic kernel edited,
no broad tile sweep. Width3 tests partialtile guards. Require scalarV2flag1 and
fits/alignment; old host FP64 references or synthetic replicas are NOT the oracle.

Inputs: inputs.f32 contains3retained actual router-input activation vectors,
2560F32each, with originalpaths/hashes in input-sources.json. These are arbitrary
valid matvec test vectors, NOT captured inputs at selectedQKVsite nor speculative
proposal states. They test scalar/multirow arithmetic with different rows. No
small retained selected QKVweight/input fixture was found by bounded search.
Weights are NOT copied now: prepare_fixture.py binds future extraction of only
this18MB exact type13/dims[2560,10240] tensor via existing GGUFdirectoryreader.
It records actual tensor hash and stable source inode/stat, not an invented full
modelhash. It never constructs a model or reads other tensor payloads. Explicit
GGUFshard needed; uses known registered SC117shard path if coordinator confirms.

Future coordinated steps, fresh exclusive paths, nice19/cores8–15:
1. python3 prepare_fixture.py --gguf EXPLICIT_REGISTERED_GGUF_SHARD --out FRESH_FIXTURE
2. python3 verify_fixture.py FRESH_FIXTURE
3. Compile gate.cpp with existing bench flags, engine/src includes, oneAPI2026.0:
   -std=gnu++20 -O2 -g0 -DP56X_SLEEP20=0 -Werror=return-type -fno-fast-math
   -ffp-contract=off -ffunction-sections -fdata-sections -fsycl
   -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt
   -Wl,--gc-sections -lze_loader
   Use a fresh binary and record its SHA/command/compiler. This source is uncompiled;
   root must resolve any actual build/API failure before claiming kernel evidence.
4. Under existing coordinator device admission/Guard/lock/postflight (not old
   run_lab.py fresh-server/cache-flush recipes), explicit FilterBdfPath +
   OWNRT_DENSE_DECODE_V2=1: gate weights.q5k inputs.f32 0
   It allocates one18MBweight matrix plus tinyF32inputs/outputs and checks six
   width/tile combinations against repeated PRODUCTIONscalar calls. Everyoutput
   uint32bit compared perrow; guard regions/unwritten rows must remain0xa5 bits.
   Any difference/error refuses timing. No model/token/head execution.
5. Only after gatepass, same controlled process may run explicit bounded timing
   iterations (e.g50). Program redoes correctness first, warms bothpaths3times,
   alternates baseline/candidate measurement order, reports medianHOSTsubmit+
   completionwait duration. No power/cache/memory setting changes or flushkernel.

Rounding/order assumptions: exact packed Q5_Kfield decode, half conversion,
factor/minimum multiplication/subtraction boundaries; eachlane product then sum
inascendingK order; same adjacent32lane reduction tree. Compiler FPcontractoff,
no fastmath/denormal changes. Device gate must falsify these assumptions. Retained
finite inputs are checked by C++; no tolerance or output rounding before compare.

Limits: warm stateless shape timing, no routing, recurrent/QSA state, fullhead,
proposal collection, checkpoints, acceptance/repair, pipeline overlap or end-to-end
throughput claim. Passing is prerequisite evidence only for the distinct width2
transaction/accepted-prefix rollback fixture in verifier-prefill-transaction-
feasibility.txt. No change to target precision, training, or currentdecode default.
