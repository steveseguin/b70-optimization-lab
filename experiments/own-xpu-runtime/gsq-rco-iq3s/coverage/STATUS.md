# Broader coverage status

The first launch, `gsq-coverage-a`, was refused before model/device initialization.
Both native rank commands passed startup`--max-new512`, while the unchanged parser
requires at most128. No model request ran. Both children exited cleanly, target
GPU descriptors are empty and the fault baseline is unchanged.

[Failed admission and artifacts](evidence/device-a/incident-review.json) and
[the independent consumer audit](evidence/independent-startup-bound-diagnosis.json)
are retained. All122 compiled dependency files were checked: the startup tokens
field is used only by parsing and the standalone path below the rank-mode return.
The persistent native request file independently supplies context-bounded counts.

Prepare a separate additive wrapper with explicit startup128 and unchanged actual
request caps512/512/128. Do not relax the native guard, reduce actual outputs,
change the qualified binary or overwrite this failed launch. Root admits a new run
only after the correction's command/request distinction is tested and reviewed.
[README.md](README.md) remains the frozen original preparation checkpoint.
