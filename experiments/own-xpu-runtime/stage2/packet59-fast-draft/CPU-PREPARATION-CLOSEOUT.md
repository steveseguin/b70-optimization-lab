# Packet59 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the serial one-layer draft use faster kernels and fewer launches without
changing packet56's target? October 17, 2026, steve-b70s. Separate IQ3 compressed
model lane, packet49 target arithmetic, BF16 KV, target split23/25, draft rank1,
91,392-row prefix. Only synthetic CPU execution and compilation were authorized.

## Outcome

CPU-prepared and sealed for the coordinator's screen. Both host and SYCL device
builds pass; no device executable ran. The final lean gate took 6.21 seconds:
134 retained parent source files and 33 shared compiler inputs are unchanged,
96 target layer fixtures and 24 tokens match packet56, and two fresh runs agree
on 27 draft proposals. Production-width synthetic runs match 104,032 bytes.
The screen tool's `--plan` verifies the final seal and new binary.

Seal SHA256: `6f82880a1778e1395a6c10bbcc2a27d8ef8560ec297bb5a9998e6e88cf3e77d0`.
Device binary SHA256: `a8dd63bb051e0c6c83f3334ce2c40c7f65873bc51f9655a9de8953249a30e4d6`.
Only this packet's regenerable object files were removed, leaving **53,221,830
bytes** in the build, below the 1 GB cap. No parent or concurrent tree was edited.

## What worked

Draft-only vector-load/split/virtual-lane schedules, direct split32 attention
and p54 routing, fixed-tree one-launch norms, and ten producer fusions compile
and pass the lean host gates. Source and byte comparisons preserve the target.
An independent read-only review checked capture indices, shapes, reductions,
bounds and scratch; its incorrect kernel-name receipt finding was fixed.

## What failed or remains uncertain

The first device compile rejected launch dimensions declared inside a callback:
the prepared-submit overlay lifts those into its capture list. Host declaration
placement was corrected, then both builds and the lean gate passed. During
helper cleanup, two unused-but-CMake-declared host fixture files were initially
omitted; configuration caught it and exact parent copies were restored.
Neither failure ran a device. Failed logs are retained in build history.

Projected D savings of 0.38–0.40 ms are assumptions, not measurements. Draft
formats differ from target formats. Production draft determinism, acceptance,
all-prompt target exactness and speed still need device checks. The mini proposal
fixture is deliberately small and repetitive; it is not an acceptance estimate.

## Evidence and patches

[Source and swap table](README.md), [CPU gates](cpu-gates.json),
[compile failure history](compile-history.json), [build seal](build-receipt.json),
[cleanup receipt](cleanup-receipt.json), [timing assumptions](budget.json),
[read-only review](REVIEW.md), [commands](WINDOW.md).
Local binaries and logs remain under this packet's ignored `build/`; rebuild
commands and read-only metadata dependencies are in [CPU-BUILD.md](CPU-BUILD.md).
Parent-source manifest and unchanged external compiler hashes retain provenance.

## When to revisit

The coordinator runs the one-load screen when packet58 and any other GPU owner
have released the host. All 12 prompts exact and class-balanced rate above
46.962697 tok/s trigger the full packet56-style chain, with packet59 draft KD
expectations and the unchanged packet49 target oracle. A failing screen gets
one bounded GPU-first fix cycle under coordinator admission, not repeated CPU
qualification or automatic server restarts. This closes CPU preparation only.
