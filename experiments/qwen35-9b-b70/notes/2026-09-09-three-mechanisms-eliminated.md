# Three divergence mechanisms eliminated, and a better-targeted lead (2026-09-09)

All three arms are depth-1 concurrency ladders matched 1:1 against `d1` - same depth, rungs, host,
card, serial on a quiet card - with the intervention verified present in the container.

| arm | intervention | pooled divergence | verdict |
| --- | --- | ---: | --- |
| `d1` | baseline | 10/254 (3.94%) | - |
| `b1sn` | `VLLM_XPU_RMSNORM_SERIAL_ROWS=256` | 8/254 (3.15%) | not a fix |
| `c1cap` | capture ceiling 64 -> 256 | 10/254 (3.94%) | not a fix |
| `b3lm` | `VLLM_XPU_LM_HEAD_BATCH_INVARIANT=1` | 8/254 (3.15%) | not a fix |

Each is two events or fewer from baseline against a Poisson standard error of about 3.2 on the
baseline count.

**What is excluded:** none of these is *the fix*. A near-zero divergence rate would have been
obvious at this sample size and none of them produced it.

**What is not excluded:** a real but modest effect. Both `b1sn` and `b3lm` landed on 8/254, and this
design cannot distinguish a genuine ~20% reduction from noise - that would need roughly an order of
magnitude more requests per arm. Do not read "8 against 10" twice as evidence of a small win; read
it as the experiment being blind below about a 50% effect.

## Why these three were the wrong place to look

All three perturb something generic and upstream: a normalisation reduction, a graph capture
boundary, a vocabulary projection. But the divergence has a much sharper signature - it appears
**only with speculation**, at every depth, and never in 630 no-speculation requests up to 32 users.
An upstream perturbation that were the cause should show up without speculation too, at least
occasionally, and it does not.

## The better-targeted lead

`run-w8a16-mtp1-strict-server.sh` passes three knobs through with a `${VAR:-0}` escape, all
defaulting to 0, all specific to the GDN **speculative** path:

```
VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT
VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT
VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT
```

Their names say exactly what the evidence points at: serialised-exact variants of the recurrent,
convolution and delta steps *under speculation*. They are queued as `b4rec`, `b5conv`, `b6delta`,
plus `b7all` with all three on - which is the arm to read first, because if all three together do
not move the rate then the mechanism is not in the GDN spec path either and the search should move
to the verify/accept path.

These should have been queued before the norm and the lm_head. The reason they were not is that the
earlier hypothesis came from the two-card campaign's history rather than from this lane's own
evidence, and the evidence here - speculation-only, depth-independent - was pointing at the
speculative path the whole time.
