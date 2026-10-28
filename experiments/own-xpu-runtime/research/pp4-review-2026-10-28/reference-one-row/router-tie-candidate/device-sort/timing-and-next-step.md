# Measured route cost and next experiment

The first matched event-timing probe passed correctness and exited cleanly on
card27. It measures individual RouteFast2 kernels on a profile-enabled queue,
not application throughput. Each cell contains 32 alternating original/candidate
pairs after four warmup pairs. Full samples and launch/build identities are in
`route-timing-result.json`; no endpoint speed claim follows from this probe.

| Input | Rows | Original median | Reference candidate median | Candidate/original |
|---|---:|---:|---:|---:|
| Actual native layer 0, no selected ties | 1 | 12.917 µs | 19.375 µs | 1.5000 |
| Actual native layer 0, no selected ties | 64 | 13.854 µs | 20.9375 µs | 1.5113 |
| All-equal raw-score stress | 1 | 11.771 µs | 283.854 µs | 24.1147 |
| All-equal raw-score stress | 64 | 12.916 µs | 280.521 µs | 21.7189 |

The candidate therefore adds about 6.5–7.1 µs in the measured untied cases and
has a large all-equal stress cost. These are costs, not performance wins. The
all-equal row is a stress distribution; this record does not estimate its
frequency in model execution or multiply these numbers into an endpoint forecast.

## Evidence from the actual compiled binary

`route-timing-compiler-evidence.json` was extracted from the timed AOT executable
without compiling or opening a GPU. The matched MERGE=true kernel metadata shows:

| Field | Original | Reference candidate |
|---|---:|---:|
| Machine-code section bytes | 56,192 | 167,488 |
| Per-SIMT-thread global `private_space` bytes | 928 | 1,024 |
| SIMD width / GRF count | 32 / 128 | 32 / 128 |
| Compiler static `slm_size` | 4,096 | 4,096 |
| Dynamic local-accessor arguments | 4 | 7 |
| Source local-accessor bytes | 5,512 | 7,816 |

The compiler also reports 321 added control-flow occurrences caused by generic
address-space operations in the candidate, versus no such warning for the
original. Static SLM metadata excludes the dynamically sized local-accessor
arguments. `barrier_count: 1` is a resource declaration, not a count of dynamic
barrier executions. None of these observations alone identifies the cause of
the untied overhead, and the compiler's unrelated RouteGroup spill warning is
not evidence that this candidate spills registers.

At source level the candidate adds a work-group barrier after top-ten selection,
then a 512-item `any_of_group`, while the original finishes selection in its first
subgroup. The candidate also reserves sort workspace even when no selected tie
is found. These are concrete differences to isolate; their individual time
contributions have not been measured.

## Explicit-local pointer variant

The isolated `address-space-candidate/` preserves pointer address-space types
through every sort helper instead of accepting ordinary unqualified pointers.
The caller supplies `decorated::yes` local pointers for probabilities, indices
and frames; frame fields are copied explicitly to avoid aggregate assignment
through an unqualified pointer. The original gated r4 source is unchanged.

The 12,512-case ASan+UBSan host gate passed. Offline AOT compilation removed the
321 generic-address warnings and reduced the MERGE=true candidate code section
to 125,952 bytes. Private-space metadata remains 1,024 bytes per SIMT thread;
the register, static SLM and dynamic local-array sizes also remain unchanged.
The combined actual-route gate and timing probe subsequently passed on card27.
All twelve output/probability artifacts from its four full gate matrix cells
are bitwise identical to the original r4 gate artifacts. Inactive/error,
nonfinite and differing-raw/equal-probability checks also passed before timing.
Full samples, artifact hashes and launch identity are in
`address-space-candidate/result.json`.

| Input | Rows | Original median | Explicit-local candidate median | Candidate/original |
|---|---:|---:|---:|---:|
| Actual native layer 0, no selected ties | 1 | 12.500 µs | 12.917 µs | 1.03336 |
| Actual native layer 0, no selected ties | 64 | 13.646 µs | 14.2705 µs | 1.04576 |
| All-equal raw-score stress | 1 | 11.6665 µs | 262.396 µs | 22.4914 |
| All-equal raw-score stress | 64 | 12.708 µs | 264.219 µs | 20.7915 |

The matched result is a 3.3–4.6% untied kernel cost, with a large all-equal stress
cost still present. The generic and explicit-local candidates were measured in
separate runs. The two binaries share source
and compile policy for the incumbent, but this is not a same-process comparison
between the generic and explicit-local candidate. Neither run estimates endpoint
throughput. Do not continue kernel work on this lever now; finish independent
model quality, then the single changed-risk model gate in the source handoff.

## Concrete subsequent way to reduce ordinary-path synchronization

If future endpoint evidence justifies revisiting selected-tie detection, test
a top-eleven detector inside the existing first-subgroup merge:

1. Retain eleven local candidates per subgroup instead of ten. The global top
   eleven is contained in the union of those local sets: a discarded local
   candidate already has eleven better candidates in its own subgroup.
2. Merge eleven global candidates using the incumbent score/ID ordering, writing
   exactly the same first ten ordinary IDs and probability words as before.
3. Detect any selected tie by comparing the ten adjacent probability pairs among
   those eleven. This includes internal selected ties and cutoff-crossing ties,
   including ties hidden by the current local top-ten truncation.
4. Lane zero performs the existing complete 512-index reference sort only when
   that predicate is true. Keep all changed-slot raw-word guards and preserve
   every native weight byte. The other work items have no later work-group
   collective, so the leader can validate/publish/normalize without a new
   work-group barrier or work-group-wide `any_of_group`.

The ordinary path trades an additional subgroup candidate/merge iteration for
the current additional work-group synchronization. It may still lose; eleven
candidates per subgroup require padding the merged pool and can change register
and local-memory requirements. The full 512-element reference sort remains
necessary on tied rows; sorting eleven candidates is not a valid replacement.
This is a queued source proposal, not an implemented or measured improvement.
Do not delay the independent model-quality check to pursue it.
