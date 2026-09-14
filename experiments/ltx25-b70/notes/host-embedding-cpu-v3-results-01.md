# CPU embedding ownership proof passed

2026-09-14. Root ran one bounded guarded CPU fixture, PID107471,
tool session35632, exit0. **All six actual-source test groups passed.**
This qualifies the tiny CPU ownership/numerical fixture only. No GPU
residency, conditioning, full-clip equality or speed result is established.

The fixture exercises the frozen original ScaledEmbedding, Comfy embedding
operation, ModelPatcher and actual token-processing method. It compares raw
output bytes, dtype, stride and token metadata for padded, repeated, batched
and long token inputs, including signed zero. Additional groups cover:

- named CPU table ownership through actual load, clone, detach and restore;
- original inference-created storage without inventing a version counter;
- rollback after failed ownership installation;
- ordinary version/storage/options mutations and unsupported hooks;
- preloaded and nonresident ownership refusals.

The table stays BF16; conversion to F32 and scalar scaling keep their original
order. Both test devices are CPU, so real CPU-to-XPU transfer still needs its
native gate. The six groups took0.128s; that is test runtime, not an encoder
performance measurement.

The explicit CPU import policy omitted exactly one known Comfy device-count
probe. All other device traps, unconditional compiler/backend refusals and
strict determinism remained intact. Neither XPU nor CUDA initialized. The
separate compiler experiment had already exited before this fixture began.

[Result](../data/host-embedding-cpu-v3-native-01-result.json),
[startup](../data/host-embedding-cpu-v3-native-01-startup-identity.json),
[tests](../data/host-embedding-cpu-v3-native-01-tests.log), and
[postflight](../data/host-embedding-cpu-v3-native-01-postflight.json)
preserve source identities and terminal evidence. Postflight found the same
LTX PID84255, identical full endpoint identity, empty queue, sole ownership of
the four render devices and no new kernel/fault evidence. No application or
computer action followed.

Next: integrate explicit CPU/encoder ownership into an inactive CLIP/runtime
candidate, retaining the existing memory estimate and6GiB reserve. Require
real full encoder residency, correct clone/serialization/unload handling and
all four original raw-output oracles before timing promotion.
