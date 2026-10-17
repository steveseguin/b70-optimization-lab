# Cross-compiler fixture refusal

Both corrected proof executables passed 8,432,381 internal checks over 2,250
sampled rows, but GNU and Intel produced different output hashes. The random
tree fixture called the stateful `random_word()` generator in two arguments
to one `std::ldexp` call. C++ does not specify which argument is evaluated
first, so the compilers were permitted to use different mantissa/exponent
draw assignments. The test inputs were therefore not identical.

The corrected fixture assigns the mantissa draw and then the exponent draw
in separate statements. No kernel or arithmetic oracle changed. The source,
initial build receipts, both native logs, and available GNU wrapper receipt
are preserved here before rebuilding. The Intel wrapper additionally refused
its stdout because an OpenMP warning preceded the JSON; its native log still
records the successful internal checks. That parser correction is separate.

Original logs:
`../host-1792228057681078468-0/native.log` and
`../intel-host-1792228057681078468-0/native.log`.

This evidence is rejected for cross-compiler fixture identity, not a device
result or a candidate arithmetic failure.
