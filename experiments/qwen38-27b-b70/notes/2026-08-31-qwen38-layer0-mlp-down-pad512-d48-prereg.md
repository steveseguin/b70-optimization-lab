# Qwen3.8 layer-0 MLP down M=512 D48 preregistration

Date: 2026-08-31

Status: **preregistered before D48 model requests**

D47 proves explicit device completion does not make the M=71 dense-MLP down
projection arithmetic stable. D48 preserves the same exact MLP activation,
copies its 71 rows into a zeroed M=512 tensor, runs only the loaded down
projection at M=512, and slices the real rows. Explicit completion before the
copy, before oneDNN dispatch, and after down projection deliberately removes
stream-ordering as a confounder from this arithmetic gate.

Across four fresh processes, MLP input, gate/up, activation, and the complete
71-row sliced down output must each have one SHA-256 value. Failure rejects
M=512. A pass authorizes a model-scoped prefill-only repair candidate; that
candidate must still replay without diagnostic hooks, pass cross-process full
outputs and strict varied-prompt quality, and quantify TTFT overhead before
promotion. Decode is outside the `32 < M < 512` branch.

No performance or production claim is authorized.
