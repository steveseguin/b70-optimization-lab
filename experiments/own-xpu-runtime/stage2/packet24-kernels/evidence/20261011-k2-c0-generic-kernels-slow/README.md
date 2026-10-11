# Packet 24 K2 on card 0: the fused "batch" and "chain" kernels are 50–100 times slower than the kernels they replaced (2026-10-11 20:09–20:13 UTC)

K0, K1a and K1b passed on card 0 (PCI 23:00.0): packet 24's new kernels are bit-exact
on the card in two fresh owners. K2 then timed every kernel class of the fused schedule,
200 repetitions each, from GPU timestamps. The native run finished cleanly; the wrapper
rejected it only because 51 of 32,000 rows contained an event with a zero duration.
[per-class.txt](per-class.txt) is the coordinator's summary of the raw events.

What it shows, per launch, on the card:

| Class | fused schedule (packet 23/24 "v1") | same work, unfused kernels (measured in the model, packet 18) |
| --- | ---: | ---: |
| gdn.qkv | 8,804 µs | 101 µs |
| logits | 129,193 µs | 2,137 µs |
| qsa.qgate | 7,263 µs | 118 µs |
| expert gate/up | 725 µs | 178 µs |
| gdn.conv | 73,373 µs | about 50 µs |

Summed over a token the fused v1 kernels need about 4,038 ms of GPU time, which is the
4,445 ms per token packet 23 measured in its two-card decode. So packet 23 is slow
because its kernels are slow on the card, not (mainly) because of the per-launch copy
I blamed first; the host was spinning in the copy call while waiting for the card.

Cause: fusion rule (ii) replaced the per-format, per-shape GEMV kernels with one
generic kernel that reads a descriptor table and a pointer table from device memory in
every work-item, searches the descriptor list, switches on the quantisation type at run
time and takes barriers; the chain kernel interprets an operation list the same way.
The compiler cannot specialise any of it. The design traded launches for generality on
the assumption that a launch costs 30 µs; a launch costs 4 µs.

Consequence: the fused GEMV batch and chain kernels are abandoned. The line continues
from packet 18's specialised kernels (12 tok/s with the ordered lookup), replacing slow
kernels one class at a time with specialised exact ones, each admitted only by a
per-class timing on the card.
