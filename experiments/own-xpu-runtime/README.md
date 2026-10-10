# Our model-specific Intel Xe runtimes

Stage 0, 2026-10-10: design and inventory, accepted for CPU work. No runtime
has been implemented or measured here. The [owner's objective](../../docs/own-xpu-runtime-objective.md)
sets the rules and stage gates. This is our own project for one to four Intel
Arc Pro B70 cards. Other projects supply credited ideas, never our code base;
Intel platform libraries are allowed dependencies.

**Stage 1 packet 1 passed, 2026-10-10 (CPU only).** The owner approved the
objective and the reviewer accepted Stage 0 for CPU work. The
[packet and receipt](stage1/packet1/README.md) freeze the official 27B revision,
tokenizer requirements, all 12 saved answers and all 1,606 tensor descriptions.
The 35 parser checks pass and file bytes match the package exactly. Stored
scales are BF16, correcting the plan's F32 size example. No weights were
downloaded and no native work was done; this task ends at packet 1. The
[stage index](stage1/README.md) tracks the remaining packets.

The certified Qwen, Flash-Next, MiniMax and video lanes continue independently.
This lane earns a replacement role only by matching their exact outputs and
meeting their matched performance gates. Their historical records remain intact.
The current host halt remains in force; nothing here authorizes GPU work.

| Document | What it decides |
| --- | --- |
| [DESIGN](DESIGN.md) | Model structure, loaders, execution, placement, teardown and receipts |
| [INVENTORY](INVENTORY.md) | Existing lab mechanisms, source boundaries and measured evidence |
| [IDEAS](IDEAS.md) | Pinned outside surveys, attribution and expected value on B70 |
| [STORAGE](STORAGE.md) | Actual local weights, conditional cleanup and pinned Unsloth alternatives |
| [STAGE1-PLAN](STAGE1-PLAN.md) | Ten packets for the one-card official 27B FP8 core and its exact oracle |

Metadata observations live in [data](data/). They contain no model weights.
Local Flash-Next configuration was read directly; 27B is absent from this
host's model directory, so its official revision-pinned configuration was
retrieved as metadata. Stage 1 starts with CPU identity and loader contracts;
weight acquisition, GPU qualification and storage changes remain later actions.

Only CPU file reads, source/metadata research and documentation validation were
used. No device initialization, server, systemd operation, GPU compilation,
weight download, mount, cleanup of existing evidence or port 8188 access occurred.
The source surveys used disposable read-only clones and removed their scratch.
