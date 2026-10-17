# Packet81 routed-expert throughput round 3

CPU-only preparation. [Analysis](../experiments/own-xpu-runtime/stage2/packet81-experts3/ANALYSIS.md)
is complete before candidate work. Fresh BMG-G31 compilation finds no spills;
IQ2 already uses eight-weight packed grid lookups and IQ4 already has a register
LUT. Both fragment each eight-input BF16 vector into four load messages.
Next: test packed activation loads while preserving exact arithmetic. This
is a mechanism hypothesis, not a speed result. Existing trees remain frozen.
