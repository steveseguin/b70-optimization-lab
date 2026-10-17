# Retention

Keep the new GNU/device binaries, compiler objects and full-shape mock evidence
under ignored `build/`. Build cap is1.2GB and each process has an8GiB address
space cap. Parent object reuse is recorded in `evidence/object-identity.json`;
new translation units compile serially. The checked compiler mirror and source
pins reconstruct the binary. CPU fixtures rerun with `cpu_gate.py`; the real
production initialization path is instrumented only in generated test copies
by `full_shape.py`. No model payload or numerical device memory is allocated.
The mock reserves logical extents and validates all copy bounds.
