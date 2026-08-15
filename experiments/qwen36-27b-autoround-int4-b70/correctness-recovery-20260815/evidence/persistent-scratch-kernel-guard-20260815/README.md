# Persistent native-GDN scratch kernel guard

This is the pre-server guard for XPU-kernel commit
`534bd9ccca74e0b076067a212271f896bb137d2a`.

- Built target: `vllm-xpu-kernels/build/temp/_xpu_C.abi3.so`
- Candidate SHA-256:
  `e9715e02bc7a475f2f8922caa288fa542df6acf24736662aecd37fd6a21cb8a7`
- Build toolchain: Intel compiler/SYCL 2025.3, existing `build/temp`
  configuration, target `_xpu_C`, four-device AOT bundle
- Runtime: `/home/steve/.venvs/vllm-xpu`, `libsycl.so.8`, one B70
  selected with `ONEAPI_DEVICE_SELECTOR=level_zero:*` and
  `ZE_AFFINITY_MASK=0`
- Feature gate: `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`
- Check: `scripts/check-gdn-native-spec-prefix.py`, BF16, three requests,
  four packed rows, both fresh and varied accepted-count cases
- Result: PASS. Conv-state prefixes are bit-equal; recurrent state and output
  are within the pre-existing native packed tolerance. The allocation marker
  in `prefix-parity-final.stderr.log` proves the new cache armed.

The first invocation sourced the compiler environment and selected only
`level_zero:0` without the established affinity/runtime-library setup.
PyTorch consequently reported zero devices and exited before allocating or
submitting GPU work. It produced no valid result and was corrected by using
the same runtime-library order and affinity convention as the server harness.
The retained `prefix-parity.json`/stdout pair is the earlier successful guard
against the pre-marker binary; the `*-final.*` files are authoritative for the
installed candidate.

`runtime-install.sha256` records the replaced July extension, its preserved
backup, the installed candidate, and the build output. No old binary was
deleted.
