# Packet 135 contract

Parent: sealed packet 133b, manifest `ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3`.

Packet 135 changes owned-write metadata accounting only. It counts allocated
blocks once per `(device, inode)` across the run directory and the existing
`stream135-`-selected output, output/validation and request trees. Shared parent
directories and other prefixes stay outside the allowance. Directory link
counts are not file link counts; symlinks, special files and crossed devices
still refuse. Descriptor-relative walks, entry/depth bounds and directory
membership caching remain.

Any unusual link count or inconsistent inode membership triggers exactly one
fresh full walk after 10 ms, with cached directory membership cleared. A zero
link count means deletion during lookup and is omitted from that snapshot.
A stable inode with all its links inside the owned namespace is charged once.
A link count exceeding observed owned entries refuses, retaining the complete
path, nlink, owned entry count, device and inode through the background halt.
A namespace that remains inconsistent also fails closed. This is a bounded
metadata snapshot, not an atomic filesystem transaction or filesystem quota;
it cannot identify the process that created a historical link.

The 50 GiB free-space reserve, integer 1–64 GiB allowance (default 3), and
256 MiB background pending-write margin are unchanged. The selected production
arm uses 16 GiB. Freshness, publication epochs and request admission checks
remain; no write is authorized merely because an internal link is accepted.

Numeric packet id 135, `stream135-` names, comparison mode
`stream-candidate-135-v1`, clip bases 13500000/13501000 and the inner plan are
re-identified. All parent numerical contracts, qualification ids and safety
latches remain. The preseal CPU gate imports both startup modes and every
bundled component/runtime helper; it never starts a launcher or touches a
health receipt, device or live port. Native qualification remains pending.

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
