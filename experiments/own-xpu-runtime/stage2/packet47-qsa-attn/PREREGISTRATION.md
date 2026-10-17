# Packet47: QSA decode attention

Registered before device execution. Parent record: packet45-merged3, including
its selected packet30 M=1 attention; packet46's card-0 timing is the motivation.
All parent packets, the driver and protected trees remain read-only. This is
independent lab code, with no code copied or ported from another runtime.

## Decision

First assess an order-preserving decomposition. Prefer it if it reaches 5x
at 4K, because it preserves the record oracle. Also implement an explicitly
new CPU oracle identity for fixed selected-index splits and two-level
max/sum/value combination. Neither tree nor split width may depend on device
occupancy, card count or work-group scheduling. Full BF16 KV stays unchanged.
The old oracle and historical 39.42 tok/s record retain their own identities.

The integration-candidate bar is **at least 3x qsa.attention GPU speedup at
4096 populated positions, separately at M=1 and M=2 in both fresh timing
processes**, after both exactness processes pass. The preferred-order bar is
5x under the same conditions. A failed bar is retained, not silently weakened.
Per-class qsa.select and qsa.qgate costs are reported separately. Their
arithmetic is unchanged unless a separately exact cheap improvement is tested.
No full-engine speed or quality claim follows from this operator screen.

## Matrix and gates

One card, physical card 0. Populated contexts: 1024, 2048, 4096, 8192, 32768.
Both M=1 decode and M=2 verification. Selection cap 2051; use actual K2/pool
selection rules, not a full-capacity assumption. Changing deterministic inputs
exercise each shape. Preserve current softmax/dot arithmetic for the ordered
arm; report old/new ULP and absolute-output differences for the new tree as
information. Logits and complete-token differences require later model gates;
no model payload is read in this packet's preparation.

E1/E2: identical sealed case matrix in two fresh processes. Exact raw bytes
against independently written CPU references, correct full selected counts,
active/inactive rows, selection tails and immutable KV/input checks. No float
tolerances qualify. Record hashes, byte lengths and first mismatch metadata.
Partial, duplicated or missing cases refuse qualification.

T1/T2: two additional fresh processes, admitted only with passing E1/E2 and
matching binary/source/seal/boot/environment identities. Use 10 warmup pairs
and 200 measured pairs per shape, alternating arm order. Fixture staging,
compilation, CPU reference and comparison stay outside timed events. GPU time
is the sum of unique completed event end-start intervals for each class;
retain every endpoint and event class. Attention sum includes every required
partial, combine and validation event. Record medians, p10/p90, paired
speedup, and full class costs. Microbenchmark warmups are allowed for this
operator screen and are never called a cold realistic-suite result.

## Oracle and later integration

The new oracle is explicit permission to define and test the new fixed
arithmetic, not evidence that it has passed the device or full model. Require
fresh-process device determinism, full model CPU-reference/logit/token
comparison under the new identity, and the registered realistic suite before
integration. Keep and report the old/new model-output delta when that later
run is authorized. Do not overwrite the old record or its frozen oracle.

## Ownership and evidence

Preparation uses CPU only, nice 19, CPUs 4-15,20-31, python3 -B. No device
program, discovery, health probe, model load, service or host-setting change.
Keep new builds lean and retain all unique failure evidence. Coordinator
windows use script files in user units, single attempts, no retries. They
check source and binary seals, closed environment, passive ownership, memory,
disk and current journal boundaries before launch. Stop cooperatively on a
fault; retain a busy child for the coordinator rather than hard-killing it.
No power, memory, swap, page-cache, driver, reboot or sudo action is authorized.

The suite effect is a labeled conditional estimate based on actual prompt
lengths and generated-token positions. Its scaling assumptions and missing
measurements must be visible. It is never a measured performance curve or a
published model-speed result.
