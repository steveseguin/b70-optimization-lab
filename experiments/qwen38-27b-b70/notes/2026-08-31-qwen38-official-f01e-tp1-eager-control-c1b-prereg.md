# Qwen3.8 official-f01e TP1 eager control C1b preregistration

Date: 2026-08-31

Status: **preregistered after C1 cleanup and before any C1b model request**

C1 stopped before health or a model request because its container omitted the
official image's required `/dev/dri/by-path` mount. C1b repeats the complete C1
contract with one infrastructure correction only: mount `/dev/dri/by-path`
read-only and provide the host video/render supplemental groups, matching the
previously successful official-f01e launchers.

Everything else remains frozen: immutable f01e image, direct-verified local
AutoRound model, GPU0/TP1/MTP0, FP16 activation/KV, eager and graph-off,
prefix cache off, distinct new caches and fresh servers, full 12-prompt
six-class 512-cap realistic suite, complete token IDs, cache zero, canaries,
cleanup, journal gate, and exact 12/12 cross-server comparison. Rates remain
diagnostic, cannot be promoted, and `promotion_authorized=false`.
