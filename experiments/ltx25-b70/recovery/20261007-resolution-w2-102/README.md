# 640×384 W2/B1 reference and speed screen

This CPU plan tests whether a second sampler worker improves the same-size,
lossless LTX workload established by sealed101c. The model, BF16 weights,
23/25 placement, 25 frames, 8+3 steps, encoder window64, decoder replica,
and original first three fixtures stay unchanged. The only numerical scheduling
change is W2 instead of W1 with sampler depth2 instead of1; decoder depth stays2.
No GPU request or runtime build was performed to create this folder.

[plan_reference.py](plan_reference.py) reconstructs
[candidate-plan.json](candidate-plan.json) from the pinned99b graph and fixture
sources. The tests compare native graphs and invariant workload fields with
101c. 101c is the reviewed experimental predecessor;99b remains the constructor
source of the original graph templates. Historical plans remain untouched.

There are six serial native requests, seven candidate requests emitting three
clips, and fourteen timed requests emitting ten clips. Each optimized phase
has four unscored fills. The timed inputs cycle the original three fixtures;
this remains a short screen, not a full-suite or endurance result.

[setup-schedule.json](setup-schedule.json) seals nine setup requests. Worker0
and worker1 are individually pinned before a serial depth1 capture, at indices
99902030 and99902041. Each capture needs its own admission and completed-tail
retirement action. Their separated indices prevent accidental collection of
the preceding setup sample even before retirement. Both workers must pass
coverage and the whole-chain check before any optimized comparison.

Total:36 requests,29 raw capture requests, cap32 captures. The client must
separately admit36 attempts; increasing the raw capture cap is unnecessary.
The existing4GiB write allowance and50GiB free-space reserve still apply.
Request names use `resolution-w2-20261007`; the reserved namespace must be
checked against the live evidence tree by the coordinator before execution.

A successful campaign leaves the application available for authorized follow-up.
The coordinator owns controlled reloads and fault handling. There is no automatic
restart or retry and no host power, swap, cache, or memory-setting change.

CPU validation:13 plan tests and11 setup tests passed. Source hashes and counts
are in [cpu-validation.json](cpu-validation.json). Plan identity and setup
identity do not establish native output equality; the runtime must create new
six-request references and verify every emitted candidate and timed clip.
