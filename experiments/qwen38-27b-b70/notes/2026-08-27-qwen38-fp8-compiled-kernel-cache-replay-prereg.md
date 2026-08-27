# Qwen3.8 FP8 compiled-kernel-cache replay preregistration

## Trigger

The strict empty-cache matrix produced stable performance gates and passing
objective canaries, but MTP0, MTP1, and dynamic MTP8 each matched only 8/12
complete outputs across independently compiled fresh servers. MTP0 divergences
began at generated tokens 169, 303, 341, and 511. The compiler/autotune
realization is therefore a plausible determinism variable.

## Bounded control

Run two new MTP0 containers from two byte-identical copies of the completed
MTP0-R1A compiled-kernel cache. This is permitted steady-state warm state:
compiled kernels may be resident or cached, but prompt, KV, response, history,
and learned-draft state may not be reused.

- Hash every file in both cache copies before launch and require their
  manifests to be identical after normalizing the destination prefix.
- Keep the model, image, TP2 topology, W8A16 flag, one-sequence 1,024-token
  service profile, complete varied suite, 512-token cap, sampler, and all
  performance rules identical to the empty-cache MTP0 attempts.
- Use new containers and run every prompt once. Require `cached_tokens=0` for
  all rows.
- Capture post-run cache manifests rather than assuming the runtime made no
  changes.

The primary causal question is whether the two replay attempts produce 12/12
identical complete token arrays. Performance is reportable under this exact
compiled-cache identity, but it cannot become a package headline unless the
ordinary quality, target, fresh-server, unchanged-target, and no-quality-loss
gates also pass.

If replay remains below 12/12, compiled-cache identity alone does not close the
nondeterminism. Preserve both attempts and do not weaken the equality rule.
If it reaches 12/12, follow-up MTP1/dynamic tests require their own separately
copied, hash-bound caches; the MTP0 result cannot authorize them.
