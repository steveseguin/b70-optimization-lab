# Ornith 1.5 35B-A3B: fast XPU argmax is blocked by backend-sampler overhead

Date: 2026-08-23 EDT

Status: **CLOSED RUNTIME NEGATIVE — do not enable backend sampling or ship the candidate**

Ornith is Qwen-derived, so the lab's earlier large-vocabulary greedy-output
work was re-audited against the accepted twelve-feature target-only stack.
This follow-up explains an earlier apparent contradiction: llama.cpp builds an
`ARGMAX` node for temperature-zero backend sampling, but the temporary SYCL
candidate reported zero hits in a normal server request.

## Why the normal request never reached argmax

The default sampler order starts with penalties and then DRY. Backend offload
is prefix-only, and the DRY sampler has no backend implementation. The chain
therefore stops before temperature/argmax. Two fresh 12-prompt, temperature-zero
server diagnostics paid partial backend overhead but never called the candidate:

| arm | median tokens 1-100 after TTFT | candidate hits | disposition |
| --- | ---: | ---: | --- |
| stock `--backend-sampling` | 120.826883 tok/s | n/a | reject |
| candidate enabled, default sampler chain | 119.671333 tok/s | 0 | not a kernel test; reject path |

Both final-response and cold-response gates passed. The accepted target-only
serving headline remains 132.788112 tok/s; the rows above are direct measured
results, not interpolated estimates.

## Reachable form is exact but unusably slow

Starting with `--samplers temp`, request `temperature=0`, and backend sampling
makes temperature/argmax the supported prefix. A bounded same-binary CLI check
then activated the candidate nine times. Its eight-token continuation was
byte-identical to stock argmax:

`78943879f4f81b707e09d2b3819b4e923780e4a34b87771e3c7f54250fd1338c`

The short diagnostic rates were only 12.2 tok/s for the candidate and 11.9
tok/s for stock. These short CLI rows are reachability evidence, not promotion
benchmarks. They are sufficient to reject the current runtime path because the
regression is an order of magnitude and occurs with either argmax kernel.

An Intel PTI unitrace of a four-token candidate run activated five argmaxes.
The two device kernels averaged 3.916 and 1.749 microseconds, or about **5.665
microseconds total per 248,320-element argmax**. The candidate kernel is not the
bottleneck. The end-to-end collapse is in the current backend-sampler graph and
scheduler path, so optimizing the reduction further cannot make this a useful
Ornith recipe.

The default-off candidate is archived as
`../patches/llamacpp-ornith15-fast-argmax-runtime-negative-20260823.patch` for
future runtime-plumbing work. It must not be applied to the public package.
The trace is diagnostic-only: unitrace overhead invalidates its printed token
rate, while its per-kernel device timings remain useful for attribution.

The accepted source diff and published executables were restored exactly:

- accepted source diff SHA-256: `7b9204f8f44608fc5b1858a15498b3cf9bf52b4f02c27c0f91a1807af5b5d15d`
- `llama-cli`: `b791b681d42ad4d6862bf94798bbaff97ead195fb4fb67e7f5c0be2bf7a80135`
- `llama-server`: `08bc580449dbc781fedd63db8039eed624817f07535a3f8a023280451f0c6e6f`
- `llama-bench`: `9bdd7033e50e22af9b05ec2c30742b5248f6708a89080974b0f0c491963c6e70`

Machine-readable measurements and hashes are in
`../data/2026-08-23-ornith35b-backend-sampling-argmax-runtime-negative.json`.
