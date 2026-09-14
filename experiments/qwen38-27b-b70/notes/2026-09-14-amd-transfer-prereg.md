# AMD approach transfer: official FP8 controls and candidate gates

The user authorized practical transfer tests after the Radiance review, with
substantial useful gains as the aim and no workload-specific or approximate
target shortcuts. This reopens concrete engineering work, not the closed flag
and allocation sweeps. The preferred target remains official Qwen3.8 27B FP8.

## Initial stage

Reuse the healthy, idle two-B70 service at localhost:18124, model
`qwen38-27b-fp8`, R304 digest `7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`.
Capacity is 33,024, scheduling budget 4,096, one active request, fixed MTP1,
full target head, FP16 activation/KV, prefix cache disabled. Capture its exact
identity before testing. Run the existing complete natural-512 strict suite and
compare complete token arrays against the qualified R304 reference. Measure
512/2,048/16,384 input-token continuation controls on unrepeated source material
from prose, code and documentation, two repeats each, 128 output tokens.
Continuation measurements are screens; forced lengths are not natural answers.
Keep warmups separate, retain SSE and numeric outputs, require cache zero and
output repeat identity. Record server prefill, HTTP TTFT and decode separately.

## Candidate admission

Read-only source audits prioritize GDN state/projection fusion and matrix layout
or dispatch changes. DFlash2 is optional and must first pass XPU integration,
unchanged verifier and context gates; short code acceptance is not sufficient.
Record the precise candidate before executing it. Do not rerun unchanged closed
arms. GPU operator work must be sequential with endpoint work on this host.
Any necessary application replacement is controlled and deliberate; no restart
chain, host setting changes, reboot or driver reset. Halt new work on GPU fault.

Operator candidates must compare complete tensors at production shapes and
repeats, including state where relevant, before endpoint admission. Endpoint
screens must compare full short-suite outputs and longer-context continuations,
then varied long-context tasks if a candidate survives. Preserve negative results.
No promotion without the repository's independent quality, repeat/fresh-process
and performance gates. Same-process results remain screens. Concurrency totals
cannot replace single-user measurements. No speed gain is preregistered as fact.

Raw evidence root: `/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914`.
Source input and benchmark identities, commands, faults and all outcomes belong
in this new packet; earlier frozen packets are unchanged.
