# Laguna public-oneCCL prefix-24 service-lifetime gate

Date: 2026-08-01 America/Toronto

Status: **completed FAIL; treatment closed.** See
[`2026-08-01-public-oneccl-prefix24-service-lifetime-result.md`](2026-08-01-public-oneccl-prefix24-service-lifetime-result.md).

## Basis

The pinned public oneCCL runtime passed the 512-replay changing-input TP4
transaction oracle and the real-model prefix-24 row-0 gate. In the latter,
both 400-token prompts were teacher exact and cache-zero, the candidate had the
expected `122/121` target topology, and all 402 traced tensors matched on all
four ranks at the old failure trigger.

## Single arm

Run exactly one fresh service using:

- diagnostic vLLM `3b68edc7501c546b03994ea8b6d6fa7bf23cc088`;
- protected XPU kernels `99886d783372e621941228250091dc8ebdc1595d`;
- Laguna S 2.1 INT4, BF16 KV, TP4+EP4, exact width 12;
- DFlash depth 11 and the current protected optimization stack;
- pinned public libccl `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`
  plus its matching device kernels;
- target inline-gather prefix 24 and skip `-1`;
- the non-scored full-exactness mode: all 13 frozen prompts, 512 tokens each,
  one active generation, cold service, no prefix cache.

No parity dump is used because its synchronous host copy perturbs execution;
the full teacher/token contract is the gate here.

## Gates

- 13/13 token-prefix exact against the frozen q1 teacher;
- 512 completion tokens and zero cached tokens for every prompt;
- real speculation for every prompt with depth-11 draft accounting;
- target `122/121` and draft `14/13` capture/replay topology on all ranks;
- exactly four workers, each exclusively mapping the pinned public library;
- no runtime/device error, timeout, retry, JIT during scored-like inference,
  surviving process, listener, or dirty post-stop idle interval.

The first fresh run is decisive. Any failure stops this treatment. Do not
retry, reset, reload, unbind, FLR, clear shared memory, or reboot.

## Decision rule

A pass establishes prefix-24 service-lifetime correctness and authorizes a
separately preregistered wider-prefix/full-96 non-scored gate. It does not
authorize a throughput claim. Before any score, mint an immutable runtime lock
that includes the public oneCCL library and kernels, then pass the chosen
treatment's complete exactness gate under that lock.
