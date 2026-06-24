# Patch Notes

Apply `llama-cpp-gemma-record-stack-c926ad098-20260624.patch` on top of
llama.cpp commit `c926ad09857517978575d6a74d225b463f7417a0`.

This patch is copied from the saved record-stack artifact:

```text
patches/gemma4-llamacpp-current-dirty-before-fused-unroll-20260624T023315Z.patch
```

It is the patch that was applied to the clean
`/home/steve/src/llama.cpp-gemma-record-stack` worktree before the verified
Q4_0 MTP draft run. It touches only `common/sampling.cpp` and
`common/speculative.cpp`.

Later experiment patches in the Gemma lane were not promoted into this
reproduction recipe because they did not supersede the 95 tok/s Q4_0 draft
record.
