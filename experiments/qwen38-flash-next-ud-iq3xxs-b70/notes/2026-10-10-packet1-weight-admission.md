# 2026-10-10 — packet 1, completed local IQ3 weight admission

The owner approved Unsloth revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`
and confirmed all three UD-IQ3_XXS shards were downloaded. This supersedes the
earlier baseline preparation's incomplete-download observation; the baseline
build receipt remains historical evidence and was not rewritten.

[Packet and commands](../packet1/README.md), [exit gate](../packet1/exit-gate.json).
Work ran CPU-only on steve-b70s, nice 19, idle I/O, OMP_NUM_THREADS=2. All model
opens were read-only. No GPU/server/systemd/device/port/network-download or
host-setting action occurred; protected paths and other lanes were untouched.

All three SHA256s and sizes pass: 81,961,823,936 bytes. Real headers match every
previous range-capture byte; 1,224 tensors reconcile without differences.
Confirmed grids: IQ2_S 94, IQ3_S 2, IQ4_NL 49, Q6_K 250, Q8_0 248, F32 557,
BF16 24. IQ3_XXS/Q3_K/F16 are absent despite the folder label. MTP is absent.

Finding: packet 1b had only size support for the three extra IQ grids and F32.
We added original scalar decoders, normative codebook data credited at the
point of use, exhaustive logical packing checks and an offline independent
format comparison. All 112 loader tests, four range guards and three admission
guards pass; 104,448 synthetic comparison values match bit-for-bit.
The first own-model CPU fixtures cover 48 tensors and 156 windows, reading
182,730 bytes per process. All sampled values are finite; same-process and
fresh-process hashes agree exactly. This is not a full-model output oracle.

Packed residency reproduces the plan exactly: 53,304,619,520 target bytes with
PLE/input embeddings off-device and an extra HC copy. One optional official
FP8 MTP block brings that to 56,002,646,016; an identified additional MTP HC
replica brings it to 56,041,967,616. Official MTP payload admission is separate.
The historical KV budget is preserved as a scenario, with a separate explicit
32K full-16-bit KV/state/graph/scratch estimate. None establishes device fit.
The off-device 29,321,610,240 bytes require bounded file backing on a 15 GiB
host. No runtime deployment or quality/speed result is claimed.

Next: packet 2, this quantized model's own tokenizer, production shapes,
operator contract and complete CPU oracle preparation. Native parity and the
baseline window remain subject to the existing halt and owner authorization.
Scratch was removed. Retained scripts, codebooks, receipts and logs are evidence.
