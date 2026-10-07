# Upstream-99 isolated dependency overlay

Prepared for ComfyUI b00c6e95279053474955540ba4f551646722b9aa. The overlay adds or updates only the 12 pinned packages in dependency-plan.json. All 35 upstream requirements, including the existing optional packages, pass metadata checks. No baseline environment, Torch, driver, or model file was changed.

External directory: `/home/steve/ltx25-upstream99-dependencies`. Its `site-packages/` contains 14,525 files; the original 12 wheel archives remain alongside it. Wheel download bytes total 173,572,680; expanded files total 303,053,537. The approved bound was 600 MiB including metadata and filesystem overhead. These files preserve exact evidence; wheel bytes and installed packages are intentionally outside Git.

The official comfy-kitchen 0.2.37 pure-Python wheel includes XPU eager/Triton dispatch without the unneeded CUDA extension. Its eager neighborhood-attention source SHA256 remains `4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995`, matching the accepted baseline. This does not prove output equivalence of the entire upgraded application.

`prepare.py` extracts only the frozen wheels after size/SHA256/RECORD validation, rejects unsafe paths and import hooks, requires a new overlay, and checks dependency metadata plus unchanged baseline fingerprints. The archived script derives paths from its containing directory: it is evidence, not an instruction to execute in this repository. It ran once from the external directory using the unchanged baseline Python.

`check_cpu.py` ran with that Python and `-B`; availability was replaced with False, device initialization/discovery entrypoints refused, and no checkpoints or model construction were used. It verified overlay imports, source99 `comfy.storage` under `--cpu`, API/NA registry contracts, and Ed25519 CPU signing. A first control-harness attempt reused one mock callable, which Dynamo rejected; distinct per-API closures fixed this harness issue. The failure and final success are both preserved.

Runtime activation must prepend the exact validated overlay path before application imports and refuse already-imported baseline versions. It must not use `site.addsitedir` or execute `.pth` files. Runtime and exact model-output qualification remain pending; the dependency receipt is not launch authorization.
