# Own Xe: project charter

**Own Xe** is the working project name for our own inference engine for Intel
Xe, currently developed on Arc Pro B70. This document sets direction and maps
the existing tree; it does not rename or migrate source directories.

## North star

Build a robust engine that supports a useful variety of model architectures,
quantizations and device configurations, with the highest measured performance
we can achieve while preserving the declared model's quality and arithmetic
contract. Quantized releases have their own authenticated bytes and references.
Repeatability, internal GPU parity and independent-reference fidelity are
separate claims and must remain visible.

New models should reuse loaders, operators, state contracts and tuning evidence
where those contracts match. Onboarding in hours or days rather than rebuilding
an engine for weeks is an aspiration, not a promised deadline for an unfamiliar
architecture. Each new abstraction must remove a concrete repeated task or make
a required capability explicit.

We own the engine implementation. Other runtimes provide credited research,
format semantics and comparison references; they are not our code base.
Preserve existing optimized kernels and historical negative results. No training
is part of this charter.

## Five implementation layers

| Layer | Responsibility and boundary |
| --- | --- |
| Model adapter | Authenticated geometry, tensor roles, operator graph, tokenizer/encoding, state dependencies and required capabilities. Architecture semantics belong here. |
| Tensor formats and kernels | Per-tensor storage/scale decoding, typed arithmetic and shape-qualified kernels. A quant label alone never determines every tensor's format. |
| Execution and memory | Device ownership, placement, allocation budgets, streams, synchronization, cache/state lifecycle and rollback. Reject unsupported contracts before execution. |
| Measured tuning | Select kernels, partitions and scheduling policies using retained measurements bound to model, arithmetic, workload, runtime and hardware identities. |
| Serving | Request encoding, generation controls, lifecycle and response streaming on top of qualified execution. Serving availability does not establish model correctness. |

Separate model identity, per-tensor quantization, topology and tuning profiles.
Use explicit capability refusals rather than silently selecting another format
or accumulating unrelated model-specific constants in general interfaces.
Specialized tuned kernels remain valid behind declared capabilities.

## Existing organization and honest current state

- [README.md](README.md) and [build.py](build.py): canonical source provenance
  and current build entry point; [build-manifest.json](build-manifest.json)
  records the original consolidation.
- [src/](src/): native implementation, including historical packet-named
  kernel families and a large model-specific execution source. This is not yet
  a clean general adapter/operator library. Keep working kernels selectable;
  reorganize only when a concrete development task needs it.
- [src/pipeline/](src/pipeline/): layout, transport, ownership and state machinery.
- [deployment/](deployment/): authentication, preparation and launch admission.
- [profiles/](profiles/): current model/launch policy inputs. Current admission
  remains restricted; adding a descriptor does not implement its architecture.
- [planning/](planning/): CPU placement tools, contracts, fixtures and onboarding
  work. [The onboarding audit](planning/reusable-onboarding-audit.md) identifies
  remaining SC117 geometry, resource and lifecycle restrictions.
- [tools/](tools/), [receipts/](receipts/) and [release/](release/): development
  utilities, build identity and source/release packaging work.

The canonical engine currently has SC117/Qwen-family implementations and
qualified configurations described in its evidence. It is not a completed
generic engine. Historical SC117 profiles document six independent CPU-reference
disagreements; later qualifications belong to their specific source, model and
test identities. Internal parity alone does not resolve fidelity. DeepSeek V4.1 support is not
implemented. Historical V4 vLLM work is reference material only.

## Bounded development sequence

1. **Developer build.** Establish a reproducible CPU-only build on the incoming
   computer and retain toolchain/source/build identity. A successful build is
   not a GPU or model qualification.
2. **GGUF capability inventory.** For the selected Unsloth DeepSeek artifact,
   compare required operators, tensor types and state against existing support.
   Pin exact files/revisions when known; mark unknowns instead of guessing.
3. **Operator fixtures.** Implement one missing format or operator at a time
   against an independent reference, including boundary/error cases and the
   required precision/state contract.
4. **Plain text graph.** Assemble correct prefill and autoregressive decode;
   prove reset/append/state ownership before speculative scheduling or vision.
5. **Fair optimization.** Measure the bottleneck, run one meaningful correctness
   gate, then full fair timing. Preserve cold requests and complete run identity;
   move to material levers instead of expanding proof scaffolding indefinitely.
6. **Reusable tuned registry.** Retain proven capability declarations and measured
   dispatch profiles so the next compatible model reuses them. Generalize only
   from actual supported contracts; retain safe refusal for everything else.

## Starting a new AI development session

Read this charter, `DEVELOPING.md`, the canonical README and
[DeepSeek onboarding](planning/deepseek-v41-onboarding.md), plus workspace
`AGENTS.md` and current lane authority before operational work. If a required
developer guide is absent, record that setup gap rather than inventing commands.
Choose one bounded task per measured or inventoried gap. State the input
identity, files to change, pass criteria, reference and expected optimization
value before implementation. Report what passed and what remains unsupported.
Do not turn onboarding into a speculative framework rewrite or relax admission
checks to make an unsupported model appear accepted.
