# Fixed three-case attention micro preparation

This is source-only native diagnostic preparation, not a device result. The
interrupted full candidate suite is not a completed correctness or speed result.
No automatic retry, device reset, application operation, cache flush or power
change is part of this runner.

The fixed layers0,23,47 use original prompt00 target-only baseline final dumped
BF16 inputs and full2,560-value attention outputs. All six copies (52,224bytes)
match the independently audited baseline index. Each input has one graph writer
(GDN gated norm or QSA attention), then is read by its attention projection. Each
output has one projection writer followed by a read-only HC combine. The Engine
allocates these named scratch buffers separately; recurrent-state bank swaps do
not change their IDs. Exact native bytes against the full saved output remain
mandatory, not merely A/B equality.

`manifest.json` binds original paths, copy hashes, baseline authority, actual
model census, all-scale weight census and original native build. Only fixture
copies were performed now. The runner would read exactly three16,711,680-byte Q8
tensors (50,135,040bytes), authenticate held descriptor identities and complete
tensor hashes, then use the unchanged expansion before constructing an owner.
No model execution or tokenizer operation occurs. `fixed.hpp` compiles the fixed
paths, extents, identities and hashes; callers cannot substitute weight paths.

A is the control packed Q8 p6 SG32 GEMV. B is existing p33 Q8 variant6/split1
expanded projection. They share one BF16 input and have distinct full outputs.
One profiling owner retains all three raw/expanded weight pairs and input/output/
workspace allocations:106,481,664 device bytes (101.55MiB), plus1MiB pinned slab.
Transfers are capped128MiB. Four excluded warmup cycles and twenty-four measured
cycles visit all three cases in cyclic order, alternating AB/BA. Every case has
two AB/two BA warmup pairs and twelve AB/twelve BA measured pairs. No timing filtering
or removal of slow samples. The schedule is fixed before execution.

Each arm's event is waited/completed and profiling timestamps queried BEFORE
retirement, then the next arm runs. Both output copies follow the two timed
kernels. Whole bytes must equal each other and the saved expected output after
every warmup/measured pair. First failure halts submissions and saves mismatch
bytes. All raw start/end timestamps, orders, output hashes and gate outcomes
remain. Device-event duration excludes host enqueue, readback and uploads. This
measures repeated isolated projections with naturally resulting cache state;
it does not establish full-engine latency, throughput, cold-start performance
or general-context speed. Both arms use the same profiling queue; this diagnostic
property differs from the unprofiled rank1 baseline.

Lifecycle follows the qualified `native-qualification/runner.cpp`: explicit
`--run --card N --output ABSENT_PATH`, default64 without Device, cooperative stop,
fixed15-minute lifetime, no retries. Submission exceptions require positive
synchronization of the exact retained Backend before shutdown. Uncertain factory,
synchronization or shutdown retains ownership for supervision. No success claim
after error. A root coordinator must admit exact source/binary, BDF ownership,
environment, faults and limits and observe physical drain; this standalone
program is not an operational guard.

`build.py` defaults to a nonmutating command plan. Future `--compile-only`
rebuilds the new micro TU and links39 unchanged non-entry objects from the frozen
control native build, verifying their original source/dependency closure and
strict FP flags before/after. No shared header, operator, owner, Matrix definition
or kernel arithmetic changes. The micro calls those existing operators; no full
Engine entry object is linked. Compiler limits: coordinated nice19 helper cores,
threads2, AS4GiB and64MiB reserved above27GB root floor. Native compilation remains
held until root releases the storage-recovery hold. Neither build nor tests
invoke the native artifact. Only tiny Python preparation tests run now.
