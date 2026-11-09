# Own Xe developer handoff — November 8, 2026

The owner wants another computer/AI to develop the native engine, initially
targeting DeepSeek V4.1 Flash in an Unsloth Dynamic 3.0 GGUF used with llama.cpp.
The larger goal is reusable model/quantization support and rapid, quality-preserving
optimization. Exact GGUF files/revision and destination hardware remain unknown.
No model, quant variant or destination machine was silently selected.

The working name is **Own Xe**. The new
[project charter](../experiments/own-xpu-runtime/engine/PROJECT.md) defines the
goal, five implementation layers, current source map and bounded development
sequence. [DEVELOPING.md](../experiments/own-xpu-runtime/engine/DEVELOPING.md)
provides checkout, CPU tests and build commands;
[DeepSeek onboarding](../experiments/own-xpu-runtime/engine/planning/deepseek-v41-onboarding.md)
distinguishes GGUF tensor storage from official native FP8/FP4 architecture
references and defines the incoming AI's first capability-inventory task.
Existing source directories and kernels were preserved.

Publication audit found six local November 4 commits missing from GitHub and
one independent remote audit commit. Merged remote main without discarding
local changes. The developer source includes the November 4 native persistent
serving changes; the repository also includes their Pi/keeper evidence.
Unrelated dirty service evidence and untracked experiment files remain untouched.

Fixed three concrete distribution gaps: the exporter lacked `iterator` and
`climits` in its standard-header inventory; dedicated transport's lazy reset
helpers were missing from Python closure; a placement test read an external
lab metadata path instead of the identical-purpose packaged profile. Included
the committed root license and developer guides in source snapshots.

The [source download and receipts](../downloads/own-engine/README.md) identify
source `1acf8352da192148ddd04a616945f221119733c3`, archive SHA-256
`879b480fae613be128ebb8c31d72939936a9442ea621a969c92d6bca7b737ed1`, 549 files.
All 548 listed payload hashes verified; 64 extracted-tree CPU tests passed.
Fresh extracted-source compilation/link passed all 40 translation units;
all 267 compiled source hashes match the published snapshot. Documentation,
exporter and fixture-path fixes landed while that build ran; native/build
inputs were compared byte for byte, so a duplicate native build was unnecessary.

This is a developer source handoff with same-host build evidence, not a
clean-host deployment qualification or implemented DeepSeek adapter. No GPU
work, model-weight download, server restart, driver operation or power/memory
setting change was performed. The faster fixed-cost-2/HC-split research patches
remain separate from the canonical source. Public model-package certification
and the broader site refresh are separate outstanding work.
