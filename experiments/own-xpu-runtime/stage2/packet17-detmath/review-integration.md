# Independent integration source review

Read-only source review, 2026-10-11. No compilation, model evaluation, GPU
access or device discovery was performed for this review. Only this report
was written. The previous independent elementary-function review is recorded
in `review-special-cases.md`.

## Arithmetic preservation

Unified source diffs were inspected against these in-repository originals:

| Packet17 file | Original | Changes |
| --- | --- | --- |
| core_v2.hpp | packet4/core.hpp | Elementary exp/log/sqrt/reciprocal-sqrt replacements, RoPE table reads, a guard requiring rotary=64 and a valid table position, includes |
| kernels.hpp | packet15-nongemv/kernels.hpp | Same elementary replacements and RoPE table reads, includes |
| reference.hpp | packet15-nongemv/reference.hpp | Elementary replacements and include of core_v2 |
| runtime_main.cpp | packet13-integrate/main.cpp | Synthesized ssm_a uses detmath exp, new includes |
| performance.cpp | packet13-integrate/performance.cpp | OMP static loop on independent output rows, exactly two threads |
| arithmetic.hpp | packet13-integrate/arithmetic.hpp | Version string only |
| runtime_kernels.cpp | packet4/kernels.cpp | Local include name only |
| runtime_kernels.hpp | packet4/kernels.hpp | Include core_v2 only |
| performance.hpp | packet13-integrate/performance.hpp | Include local runtime adapter only |

No reduction-tree, operand-order, BF16 conversion-point, matrix dispatch or
within-row accumulation changes were found. Softplus keeps the same
`gate < 20 ? log(1+exp(gate)) : gate` composition and threshold. Plain
divisions elsewhere remain in their original order. The shared GEMV
references and dispatch remain the packet13 r234/SG32/split4/BF16 choice;
OMP partitions independent output rows and does not partition their sums.
There is no added FMA in the original non-elementary core equations.

RoPE replaces only the BF16-rounded cosine and sine coefficients. Products,
addition/subtraction and output BF16 casts remain unchanged. The generator
explicitly freezes glibc powf/sinf/cosf host results, FP32 angle rounding and
BF16 ties-to-even in little-endian constants; device arithmetic contains no
RoPE elementary call. Header regeneration presently re-evaluates that pinned
host authority and refuses a mismatch, so a different libm host cannot simply
regenerate the header unless its results happen to match. The stored table
bytes define the identity. The parallel helper relies on the caller's valid
position; the core adds an explicit range/rotary guard.

## Oracle coverage and remaining completion checks

`oracle.cpp` was compared to the existing packet3-runtime-oracle/oracle.cpp.
Its only code differences are the packet17 runtime include and the required
OMP thread count changing from eight to two. The original prompt stepping,
state updates, generation, logits extraction and layer captures are preserved.
The currently running receipt requests 87 input positions and 64 generated
tokens, with context capacity 192 and the full 48-layer model plan. Input
files are hashed, prompt token identities are checked against the frozen
oracle input, and source/binary identities are verified before launch.

The last prompt position captures step 1. Each subsequent generated token
feeds the next step. For captures 1 through 8, the harness writes the BF16
streams after every layer's `.ffn.combine`, giving the requested 48 files per
step on a complete run. Every generated token records the top-five IDs,
top-five logits and full BF16 logits hash. Earlier prompt positions skip only
unused final prediction heads; layer state updates and commits still execute.
Arithmetic identity is stored with the run output. The host-only build guard
and host adapter preclude device execution in this binary.

The native harness can finish successfully with fewer than 64 tokens on EOS,
or when its retained pilot-too-slow condition fires. The Python runner records
coverage but does not itself assert all requested counts. Therefore final
acceptance must explicitly check 64 tokens/top-five rows and 48 layers in each
of steps 1..8; the launch request alone is not completion evidence. This was
reported to the parent during the run. Source inspection does not establish
token agreement or device parity; those require their result comparisons.

No integration arithmetic defect was found. Several inherited comments still
refer to libm, packet4's frozen core or packet13 authority; they are stale
labels, not evidence that the copied implementation still calls that path.

## Reviewed source identities

| File | SHA-256 at review |
| --- | --- |
| `core_v2.hpp` | `e267cda96d17f7c95d4313abc878b531b152548ed7004471d6cee822a2cab8f6` |
| `kernels.hpp` | `22bf27fc4d3175c88549e8ccb4cc25d4c2626754660b1038bfceafd48ff15155` |
| `reference.hpp` | `9dbd20b4d8b210be469e1a8dc31c1592b18d352f15c3bee7058c18bf9aa924bc` |
| `runtime_main.cpp` | `881cdcf0793c2b943ada4366b09ac5ab22f6f3e53090209d96d6e5efa21ea8c6` |
| `performance.cpp` | `1ba609155e80f1a5ab6b2292752f6707789fa1e9d7f03e225a25e7f3f8f7a400` |
| `performance.hpp` | `92ba7a4f72e19f4a3549c580f512537543f6de4dd1b0b4036d6a36b1642100c1` |
| `runtime_kernels.cpp` | `ff95284fda68e0097c35e7ee0b03851563b77cf935602b4e2ea0d5ba526f37f0` |
| `runtime_kernels.hpp` | `68e517a28d6486998fc2c2802ddc043b6c34fa03f3d9f42d2d75fc1ea3805c6b` |
| `arithmetic.hpp` | `0c9c0b58499544ffe1662a32a41baf933b08eff0943316f2d1e7e83fbf989fa3` |
| `oracle.cpp` | `ae4ddd22ae795251ff24f06879fb38dbb87eb30281e5c3a677d39a00b7b3d414` |
| `run_oracle.py` | `9062a9c02e1b29a3d45cfa24aac3cb043d00981bae60812b6b39e53facb87752` |
| `rope.hpp` | `0d7573e1e568ba09c4733c120fd7473b5bac8ef7f8d7d1052fc060b1b2bd5f97` |
| `generate_rope.py` | `eb9a941d227f0dcd4f44769985c97d97c3443428850d192b3e9c2a06b2e871be` |
