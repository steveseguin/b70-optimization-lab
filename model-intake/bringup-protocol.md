# First-wave B70 bring-up protocol

This is the lab-owned handoff from verified downloaded bytes to the first
target-only baseline. It is deliberately conservative: passing this protocol
does not promote a model, and a loader failure is useful evidence rather than
permission to silently change quantization or runtime.

## Preregistered order

| Order | Intake ID | First topology | Purpose |
| ---: | --- | ---: | --- |
| 1 | `ornith-15-9b-q8` | 1 B70 | Small official Q8 starter candidate; quickest way to validate Ornith loader and architecture support. |
| 2 | `lfm25-26b-q8` | 1 B70 | Small official Q8 starter candidate and independent Liquid architecture check. |
| 3 | `ornith-15-35b-a3b-q4km` | 1 B70, then 2 only after a valid baseline | Reuse confirmed Ornith support, establish the larger-family baseline, then compare topology. |
| 4 | `nemotron-35-lightning-30b-a3b-udq4km` | 1 B70, then 2 only after a valid baseline | Independently test the GGUF family without treating an external performance report as evidence. |

All first runs are text-only, target-only, one slot, F16 KV, 8K context, no
draft model, no MTP, no response/prompt reuse, and cache RAM zero. These are
baseline controls—not expected final recipes.

## On the downloading machine

After all downloads report `complete`, verify them again immediately before
testing:

```bash
python3 scripts/model-intake.py verify \
  --root /mnt/usb-models --all-queued
```

Select a known llama.cpp/SYCL build explicitly. Do not point the harness at a
floating binary or an existing warmed service. Start the first model:

```bash
INTAKE_ID=ornith-15-9b-q8 \
MODEL_ROOT=/mnt/usb-models \
LLAMA_SOURCE=/path/to/llama.cpp \
LLAMA_BUILD=/path/to/llama.cpp/build-sycl-aot-bmg-g31 \
OUT_DIR=/path/to/evidence/ornith-15-9b-q8-baseline \
  scripts/run-model-intake-baseline.sh
```

The runner redoes direct-and-ordinary model verification, refuses an
unidentified or dirty source tree by default, restricts Level Zero enumeration
to one physical GPU, records the server/library/source identities, and
preserves the full server log. It intentionally does not install drivers,
choose a source tree, or hide a loader failure. `ALLOW_DIRTY_SOURCE=1` exists
only for an explicitly labeled diagnostic; such a result cannot be promoted.

From a second terminal, after `/health` succeeds:

```bash
INTAKE_ID=ornith-15-9b-q8 \
BASE_URL=http://127.0.0.1:18100 \
OUT=/path/to/evidence/ornith-15-9b-q8-baseline/result.json \
  scripts/bench-model-intake-baseline.sh
```

Stop the foreground server with `Ctrl-C`. Preserve `launch-identity.json`,
`server.log`, and the result JSON together.

## Required decisions after the diagnostic

1. If loading fails, record the exact unsupported tensor/operator/architecture
   boundary and test source support before considering a different artifact.
2. If loading succeeds, add deterministic semantic canaries and register that
   model's own output oracle. The generic suite establishes freshness and
   timing only; it is not a quality qualification.
3. Repeat the same clean target-only control before applying any project or
   contributed patch.
4. Credit an outside contribution only when an identifiable patch survives a
   matched A/B and the model-specific quality gate.
5. Create a `repro/` candidate only after model, runtime source, patch chain,
   launch identity, baseline, and validation evidence all resolve inside this
   repository.
