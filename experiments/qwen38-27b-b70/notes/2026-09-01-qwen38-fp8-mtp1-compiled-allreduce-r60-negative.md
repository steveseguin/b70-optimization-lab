# Qwen3.8 FP8 TP2 MTP1 opaque compiled all-reduce R60

Date: 2026-09-01

Status: **rejected as performance-neutral; correctness passed**.

R60 revisited one old collective idea only after the final R50 state and
ordering fixes existed. While compiling, `XpuCommunicator.all_reduce` called
the existing opaque `vllm::all_reduce` custom op. At execution it retained the
accepted output clone, asynchronous oneCCL operation, and explicit
`Work.wait()`. XPU Graph remained off. The feature is default-off.

The first fresh-cache strict server reached readiness and passed the complete
12-prompt/six-class natural-512 contract:

- `51.756541 tok/s`, `0.0995%` below the `51.808087 tok/s` incumbent;
- all 12 complete candidate token arrays exactly matched the R54A MTP0 oracle;
- every request reported zero cached tokens and both canary batteries passed;
- no new Xe fault, reset, or device loss appeared.

That cleared the preregistered continuation floor, so R60 ran the complete
unrepeated three-class real-content matrix. All 18/18 complete arrays matched
the R56 MTP0 oracle. Decode deltas versus R56 MTP1 were:

| Active context | Decode delta |
| ---: | ---: |
| 2K | `-0.092%` |
| 4K | `+0.831%` |
| 8K | `+0.362%` |
| 16K | `+0.064%` |
| 24K | `-0.099%` |
| 32K | `-0.280%` |

The median delta was `-0.014%`, far below the preregistered `+3%` depth gate.
A second strict server was therefore not authorized: repetition can estimate
noise but cannot turn this six-depth effect into the required material win.
The public R50 default and `51.808087 tok/s` headline remain unchanged.

This result also narrows the R59 interpretation. The profiler's all-reduce
kernel time does not imply that changing only Inductor's collective boundary
will improve the endpoint. A new attempt must reduce actual W8A16 GEMM or
two-card collective work, not merely make the same oneCCL call opaque.

Structured evidence:
[`2026-09-01-qwen38-fp8-mtp1-compiled-allreduce-r60-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-compiled-allreduce-r60-result.json).
