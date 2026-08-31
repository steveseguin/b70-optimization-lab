# Qwen3.8 MLP-repaired all-prefill-layers D50 preregistration

Date: 2026-08-31

Status: **preregistered before D50 model requests**

D49 made every selected dense-MLP down projection use synchronized M=512 but
left a two-way complete-response split. D50 retains that repair and hashes the
input, hidden output, and residual output of every one of the 64 decoder layers
at prefill call 2 across four fresh processes.

The first boundary with more than one SHA-256 value is the next localization
target. Boundary hashes deliberately synchronize between layers, so this is
not a speed or production run. The earlier exact MLP repair must remain engaged
and layer 0 must be exact. If all prefill layers are exact, the search moves to
the final norm/logits or decode state; otherwise the first differing layer is
split into attention and MLP stages with the MLP repair still active.

No performance, quality, or production claim is authorized.
