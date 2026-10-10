# Packet 130 CPU preparation contract

Parent: sealed 129, manifest
`42e6a7452e11873f33c78a953105754605121f2a96dfca1954b1d55966a4886c`.
This packet prepares an allocator remedy; native admission is not yet verified.

`LTX_DISPLAY_ALLOCATOR_RELEASE=off` is the default and retains packet129's
admission and numerical path. `before-admission` is scoped to 169 frames,
two-way20-28, frame/cone/dg0/bo1/pa1, legacy auxiliaries, parallel eager display
on xpu:2, fingerprint/full snapshots and read-ahead0. It is a server option
bound to status, receipts, decodes and the qualification verdict. Clients must
expect the selected value and pin the INNER plan_sha256.

Before replica installation, after installation, and before each decode, read
physical free memory. If it falls short of the existing requirement, make one
`torch.xpu.empty_cache()` call and read physical free memory again. There is no
loop, decode retry, eviction, tensor movement, Python collection, peak reset or
graph-pool destruction. PyTorch's API has no device argument: the release is
process-wide. Record four-card allocated/reserved/peak/free counters around it,
the physical-free delta, duration and phase. A reservation delta is never
credited as physical free. Recheck the replica's tensor facts after the release.

The unchanged budget decides admission: new resident bytes (installation only)
+ 6.5 GiB transient + 2 GiB floor + 0.75 GiB screening. Insufficient reclamation
refuses and latches through the existing caller. Failure diagnostics include
release counters. Successful release evidence remains in the existing immutable
installation/decode records. Existing full-image cross-card comparisons on all
nine qualification chunks, three-chain identity, live cone equality, all-card
snapshots, growth checks, storage/fault controls and atomic publication remain.

At the saved refusal, at least 1.365982 GiB must be reclaimed; 0.8 GiB is not
enough. Reserved-unused counters show a candidate pool, not a guarantee that
allocator segments can be returned. Full native admission, exact output,
reservation plateau, fresh-text contention and speed remain coordinator gates.
No GPU operation or application launch occurs during this preparation.
