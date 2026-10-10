# Packet 133 contract

Parent: sealed packet 132, manifest `67ec59a5b0c5131d0b129e4c0b9187386c29c0395ac225dc28422516684991ad`.
This is a CPU-prepared launch option. Native exactness, physical memory and speed remain unqualified.

`LTX_TEXT_RESIDENCY=legacy` preserves packet132 text placement and behavior.
`split36` installs the existing text sharder with boundary36 before first loading
or capturing: layers0–35 on xpu:2;36–47 on xpu:3. Tensor ownership changes; model
weights, precision, kernels, operation order, tokenization and all five text-window
buckets remain unchanged. No live tensor relocation, host weight paging, graph
teardown or per-cut recapture occurs. Existing480 text graphs remain resident.

The candidate is restricted to145 frames, two-way20-28 sampler placement,
frame/dg1/cone/bo1/pa1, text reuse1, fingerprint/full snapshots, read-ahead0,
serial eager display on native xpu:3, legacy audio and auxiliaries, no display
replica, display allocator release off, no pool cap, parent5GiB capture reserve.
Text-shift performs no allocator-cache release; an insufficient physical
reading refuses immediately.
`LTX_CONE_GRAPH_MEMORY=text-shift` is paired with split36. Before first capture
actual physical free must cover5+9+0.75GiB; subsequent cone admissions cover
9+0.75GiB. Measured postcapture reserved growth must not exceed5GiB, and a
fresh postcapture check retains9.75GiB. The allowance is not a hard allocator
peak bound. Original all-card8/8/2/9GiB pre-request floors remain.

The hash-bound `text-oracle133.json` carries all40 parent full/window probe rows
and12 prompt-conditioning references (10 scene prompts,2 qualification prompts).
The setup compares both workers' full-length and window hashes with the parent.
Every fresh conditioning is compared before it enters the sampler or reuse cache.
Unknown prompts refuse at admission; changed shape, dtype, path or tensor bytes
fail closed. Legacy mode does not apply this restricted-prompt oracle.

All nine qualification outputs and all inherited per-chunk checks remain.
The145 eager chain must also match its frozen parent full-output table; a missing
table is a failure. Receipt and client options bind text residency, oracle hash
and cone-admission mode. Same-device startup graph proofs remain necessary but
are not substituted for parent text/output equality.

CPU fakes test code and failure paths only. They establish no native equality,
freed physical memory, capture peak or speed claim. No169 text-shift launch is admitted.
