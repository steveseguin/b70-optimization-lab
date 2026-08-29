# Qwen3.8 Flash-Next FP8 TP4 MTP0 sampler-native A7 result

Date: 2026-08-28
Status: rejected at exact-4K repeat gate; 16K not run

Stage A5 passed the frozen post-A4 recovery gate before this candidate. A6
then stopped before worker creation because its descriptive campaign name made
the default IPC socket path exceed the platform limit. A7 changed only the
attempt, port, and IPC path. It retained the accepted model, source, staged
runtime, TP4/EP4/eager/MTP0, offload, cache, scheduling, and request identities
and changed only `VLLM_XPU_USE_SAMPLER_KERNEL=0`.

Post-result source-path audit found that this selector was inert for the frozen
requests. They use `temperature=0`, so `Sampler.sample()` computes greedy
argmax and returns on its `all_greedy` branch before `TopKTopPSampler.forward()`
can dispatch to either the XPU-specific or native implementation. The A7 arm
therefore changed configuration identity but did not activate a different
token-selection implementation for these requests.

The A7 server loaded all 131 external checkpoint shards in 592.60 seconds,
reported 31.27 GiB per rank and exact 21,795-token cache capacity, and became
healthy. The established short quality battery retained its known 6/7 exact
result: every case except the previously documented `code_execution` canary
passed, the 16-request repeat case had one output hash, and the exact-4K needle
passed with zero cached or created tokens.

The two formal exact-4K rows used byte-identical request payloads and the same
4,096-token prompt. Each returned 128 tokens, `finish_reason=length`, zero
cached tokens, and passed every transport/timing gate:

| Row | Decode tok/s | TTFT (s) | Output-token SHA-256 |
| --- | ---: | ---: | --- |
| 1 | `5.405351634035985` | `120.46753009900021` | `da6b0b03c49f8f13284ea6f34100e4958fa779e910e22f99a6f648aed44ea79c` |
| 2 | `5.346274611630608` | `134.64540737100106` | `1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc` |

The diagnostic median is `5.375813122833296 tok/s`, 12.989% above the protected
current-runtime median `4.7578181021380175` and above the frozen 95% floor.
Because the configured treatment was not on the greedy execution path, this
speed difference is run-to-run diagnostic variation and cannot be attributed
to the selector.
However, the two output hashes differ despite request payload SHA-256
`2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be`
and prompt-token SHA-256
`aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0`
matching exactly. Row 2 matches the retained output authority; row 1 does not.

The frozen client therefore failed closed before writing a Phase-1 pass receipt
and before sending either 16K request. This is a bounded negative, not a 16K
sampler result. The candidate is rejected because it supplied no active
treatment and exact same-server output repeatability still failed. It receives
no speed, quality, deployment, curve, or headline credit, and no protected
value changes.

Controlled shutdown left no owned model process, listener, IPC path, or device
allocation; all four cards returned below 43 MiB. The corrected bounded journal
contains no B70 reset/failure or system-memory event. It retains six corrected
receiver records for local NVMe `0000:01:00.0`, with no I/O error. The initial
postflight journal used the NTFS birth epoch, which is zero and therefore
captured the full boot; that file is preserved as an evidence-generation
caveat. The separately written corrected window starts at 22:47:00, six seconds
before the first server log line.

The immutable external run root is
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-16512-sampler-native-r1-attempt7`.
Its 46-entry manifest verifies, and the manifest-file SHA-256 is
`3076e07b004f2bba8b439eb44c21cff4ed1fa19a1368f4188bb288a4715f5651`.

The next useful experiment is a report-only, bounded trace on identical 4K
requests. Record compact top-logit IDs/values, margins, and selected argmax so
the first divergence can be located without changing the greedy decision. Do
not retry 16K until that shorter gate is stable.
