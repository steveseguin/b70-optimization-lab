# Qwen3.8 Flash-Next grouped full-serving stage A2 qualification preregistration

Date: 2026-08-31
Status: frozen after build, before GPU qualification

## Purpose and authority boundary

The assembly-only A2 finalizer produced a candidate 18-file Flash-Next serving package
with a newly matched `_xpu_C`, GDN library, and grouped-GEMM library. This
qualification asks whether that package retains the accepted native/runtime
contracts while exposing the already component-qualified HyperConnection
grouped operation.

This is not an endpoint arm. It performs no reboot, server launch, full model
load, request, or throughput measurement and does not create or consume the
full-load boot marker. A complete pass authorizes only freezing the separate
A30 endpoint candidate. The accepted stage and protected `5.515783 tok/s`
MTP0 and approximately `20.727 tok/s` MTP4 results remain unchanged.

## Frozen build and stage identity

- vLLM: `797769b34b6db5c934609b75dc04cc61ec66e5f9`;
- XPU kernels: `eeee7d671abfa964626baa18da2174bb92cac80a`;
- candidate package:
  `/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2/vllm_xpu_kernels`;
- A2 finalizer-evidence SHA-256:
  `2c049273bfc9e8dd429e2f74969cb9c4917a6e23833fcb8e8584ba8944a62aee`;
- 18-file candidate-manifest SHA-256:
  `a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d`;
- candidate `_xpu_C.abi3.so`:
  `8d6d41a2259b4d4eda53edd9524d113d9190ae1b093a150fd79aa72a5c28dd76`;
- candidate `libgdn_attn_kernels_xe_2.so`:
  `6c9ba1f12838b3eaa27e91610f0344fbf11671bfee204c6a9a68564fc654c17e`;
- candidate `libgrouped_gemm_xe_2.so`:
  `c8ba41d4978b0095648acee6782b7fd300ebc26403b5d1f2f7bcfb87b3430c42`.

The candidate manifest remains external to the package, so qualification does
not change the exact 18-file inventory. Every phase rechecks the build evidence
and candidate manifest; the 15 untreated files must remain byte-identical to
the accepted package.

## Frozen tools

- A1 build driver:
  `b5c29a50c3e6e3b737312fcb2392df9e5b252ef38cd038674c1bf11d4c3bd336`;
- A2 assembly-only finalizer:
  `d23491b666d83e7f57008239cf17d54f11e77674ec25164c8ea560750cfe1e76`;
- activated venv CMake wrapper:
  `3583e90ce3a76689137884f5dde26d73eb31b4ba73d36fbda12060f23a49e9cc`;
- supervisor:
  `870529a3e9c37599f77f38460795a2651e9a3ff4701c1a46d7dac73f8b8152a2`;
- package/schema inspector:
  `b37a2e15d61826d1deca3b3dab03028e18b6e7f1a77776bd52b09a6d6d6d40d4`;
- focused-test runner:
  `0966e8495123c2cc9681efba7ccb188152d193ab4c753ff6b009e8a44f5f8507`;
- stage-bound GDN wrapper:
  `3d4fbd42f11442e9928304665f8713814c3ae90ad27999e3acebaa9e27677912`;
- CPU contract tests:
  `f5db8fd1da20b25186ac52ddbbff1fbb6240207988cd94b30cc5ab307fcbc200`;
- unchanged historical GDN gate: `ca0c5956b491c9fcd8698a02eaf00f96c1f050cc7db50ebbf91560bf85b7abfd`;
- unchanged real-weight MoE gate: `505ac4b230456bd5eb9d83d14d54b31dec88e0ec607cf557f434b4184ca71aa8`;
- unchanged M1 resolver: `cafe4b1998dabbe60b4877615d0f9342ec479245713f6fe964786e246d7f9c1a`;
- unchanged XPU/XCCL health helper: `b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78`;
- unchanged repeat-XCCL gate: `491484f98c45af2ea9bc9054f9764489de7f2b328aea8d0c8e99dd0e7d7b838a`.

The new GDN wrapper imports rather than copies the historical gate. Execution
is bound to A2 and kernel commit `eeee7d6`; A24/A25 reference validation stays
bound to the original accepted stage and runtime-build commit `2f829747...`.
Historical source and evidence contracts therefore remain byte-unchanged.

## Frozen sequence and gates

The supervisor authenticates both storage mounts, source and tool hashes,
memory/swap/free-space floors, absent output, no active build/model process,
and no render-node owner before creating evidence. Validation-only mode runs
all static gates and creates no evidence or device work.

The attended qualification then runs, in order:

1. **Package, loader, and schema parity.** Separate clean processes import the
   accepted and candidate packages. Each must resolve its package, extension,
   GDN/grouped libraries, and exact SYCL 8 runtime from its declared paths. The
   complete `_xpu_C::` schema lists must be identical; GDN must retain all 23
   argument names and grouped GEMM must be present.
2. **Focused HC source/runtime tests.** With the candidate extension preloaded
   on one B70, exactly 5/5 grouped-HC tests and 25/25 Qwen configuration tests
   must pass. These cover default-off behavior, exact 97-target selection,
   single-storage reload identity, every `M=1..64`, two streams, fresh outputs,
   and fail-closed malformed state.
3. **Retained GDN history.** Run preflight, a two-trajectory smoke, and two
   fresh 100-trajectory/6,400-call qualifications. The existing comparison
   must report exact equality for the full 64-chunk 4K history contract.
4. **Retained M1 MoE.** The official resolver must select key `1`, eight warps,
   and the exact tracked map. One seed-20260827 real-weight M1 arm performs 100
   repeats and must be finite, single-hash, and exactly equal retained digest
   `eb1a25f96c14a3343494d2c240b9033b9dffd386d295c73b588b5e5b08d3b718`.
   Timing has no gate and receives no credit.
5. **Four-card health and collectives.** All four B70 single-device receipts
   and ranks 0--3 simple all-reduce receipts must pass. A second exact
   `[1,2560]` BF16 all-reduce runs 100 repeats and requires finite, one-hash,
   world-size-four output on every rank.

The A2 finalizer bound the inner `CMAKE_COMMAND` executable but not the activated
venv wrapper; qualification binds both by retaining the finalizer evidence and
checking the wrapper hash above. The finalizer also checked `$ORIGIN` on the
native extension before emitting its evidence. This qualification independently closes that remaining loader detail
for all three replaced DSOs: `_xpu_C`, GDN, and grouped must each retain the
exact `$ORIGIN` runpath before any device work. Stage closure is rechecked
between phases. Final card identity must match the
preflight, no process may retain a render-node descriptor, the bounded kernel
journal must be readable and clear of the established B70 reset/fault/timeout/
fatal/wedged/failed patterns and host OOM patterns, and every evidence file is
checksummed. Any failure stops the sequence and preserves partial
evidence without authorizing a retry, endpoint, speed, quality, or promotion
claim.

## Execution boundary

The packet is prepared only. No GPU qualification may run until this note and
all tool hashes are final, static tests pass, an independent review finds no
blocker, and the active native build has completed successfully. No reboot is
required or authorized by this packet.
