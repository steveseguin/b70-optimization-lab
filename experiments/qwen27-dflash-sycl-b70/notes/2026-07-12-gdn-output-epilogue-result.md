# GDN output epilogue fusion result

`GGML_SYCL_FUSE_GDN_EPILOGUE=1` implements a guarded single-launch recurrent
output epilogue: RMS normalization, learned per-head weight, SiLU of the `z`
gate, and final multiply.  The final matcher plans from graph dependencies
rather than sequential node order because the `z` projection is interleaved;
it also compares element counts because the same data appears as `[128,48]`
on the GDN branch and `[6144,1]` on the gate branch.

Runtime diagnosis confirmed exactly 48 plans per Qwen decode graph, and the JIT
build and deterministic semantic smoke pass.  Nevertheless, warmed M=1 decode
was neutral/slightly negative: `25.89 tok/s` enabled versus `25.93-25.94 tok/s`
disabled.  The launch reduction therefore does not justify integration or an
expensive MTP promotion matrix.  Keep the flag default off and preserve this as
a negative result.
