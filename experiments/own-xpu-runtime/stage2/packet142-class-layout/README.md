# Packet142: class allocation-order preparation

Copied from frozen packet136 bundle8. Only `v5/bracket_job.py` will be a supported device entry after a passing final seal. Preparation is in progress; no device readiness is claimed.

The three candidates retain exact copies of complete weight-consumer tuples in class order, up to a fixed 512 MiB per rank. Production and candidate resources coexist before the first request. This is a bounded class-prefix experiment, not a whole-class relocation. Physical adjacency is not guaranteed by the allocator. The gate/up arm keeps E1 halfcache and original row bytes; it does not repeat packet104/104b tile16. Arithmetic, kernels, reductions, banked rollback and BF16 KV are unchanged.

All 182 inherited link objects are preserved; non-allowlisted targets are redirected to local copies. The original link text is recorded in `copy142.json`. Native/compiler closure is local; frozen inherited binaries are hash-bound. Packet49 oracle authority remains separate.
