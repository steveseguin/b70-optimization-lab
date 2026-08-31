# Qwen3.8 loaded-model hash D8 infrastructure failure

D8 stopped before model loading and before any request. oneCCL could not open
`/dev/dri/by-path` because that directory was not mounted into the container.
This is **not evidence** for or against cross-process model-state determinism.

The complete model passed the direct-and-ordinary verification gate. The
preserved machine-readable receipt records the immutable image, verification,
runner, preregistration, and container-log hashes. D8b changes only the device
exposure required for oneCCL: it adds the read-only `/dev/dri/by-path` mount and
the `video` group, matching the already validated official-control repair.
