# Independent reference starting point — October 24

Read-only discovery finds a concrete local reference candidate, not a qualified
oracle. The pinned llama.cpp source at`23b0202a189c44a54625aadcb37a946dd1d6278d`
contains the qwen4exp model graph, HC/PLE/QSA/GDN paths, and a CPU Q2_0 dot-product
entry. The four inspected source files are clean against that revision; exact
[read hashes and build-cache identity](evidence/reference-source-appraisal.json)
are retained. This extends the prior scalar-decoder reference inventory without
claiming full compatibility with every actual SC117 tensor/type/operation.

Existing binaries are under
`/home/steve/build/flash-next-iq3-baseline-20261010/build/bin/`. The CMake cache says
CPU and SYCL are enabled, SYCL targetbmg_g31, graph/F16/DNN disabled. No binary was
executed or mapped to a fully audited build closure. Invoking even a help/version
path has not been treated as proof of no device initialization.

CPU quantized dot products may quantize activations: the Q2_0 entry explicitly
uses Q8_0 input dots. Therefore this independent implementation is not automatically
a bitwise oracle for our original BF16 input arithmetic. A future comparison must
fix decoding/tokenization and use a preregistered teacher-forced/logit or task
criterion appropriate to its arithmetic. Never hide differences by relabeling
this as the exact target implementation or transferring old-model oracle outputs.

Before any reference execution, inspect complete actual-format and graph coverage,
binary provenance, prompt/output interface, CPU/device selection and memory needs.
A CPU reference would need its own ordinary-model memory admission; no GPU or
large model read is authorized by this discovery note. This does not delay the
already-planned six-request broader screen on our qualified engine.
