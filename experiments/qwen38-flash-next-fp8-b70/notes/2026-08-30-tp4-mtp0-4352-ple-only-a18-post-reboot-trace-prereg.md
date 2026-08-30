# Qwen3.8 Flash-Next FP8 A18 post-reboot trace preregistration

Date: 2026-08-30
Status: frozen before GPU launch

A18 is the fresh-boot replacement for infrastructure-interrupted A17. It
changes only attempt, port, cache, temporary, lifecycle, and evidence paths
from attempt 17/port 19689 to attempt 18/port 19690. Model revision, vLLM and
kernel heads, staged runtime, PLE-only placement, graph/MTP/scheduler flags,
cache capacity, seeds, request order, complete client battery, and the
report-only trace implementation are unchanged.

The host gate is stricter operationally: all four cards must be idle, swap must
be unused, and memory availability must reflect the fresh reboot before the
single load. No second full-model load will be started in this boot without
first re-establishing that same memory condition.

Interpretation remains exactly A17's frozen contract: compare all 149 ordered
A16/A18 tensor digests, report the first differing tensor if inputs match, and
do not credit diagnostic-arm timing. Any ordinary output assertion remains
fail-closed. No protected result changes.

Frozen artifacts:

- launcher wrapper `6096391b290369596308e850db622150fc7fc96973d421bbaf8cb19d82046407`,
  generated source `61193bfd7469027ce66247d241fafbb218d25f3658d6089d0f87c5b5c3971ed8`;
- client wrapper `87597d379d9543af956ed67f4392eb822de0b403604055482aa7d03a53f65a36`,
  generated source `141fbe09c8b27eb5183131ab82d8d64380f6018e2370bdc0c1ee5a00a84f1097`;
- supervisor wrapper `7eefe8f6ec91def8d3cc31abc02595428969c1bad68371a8aaa73a55d5ae9dbe`,
  generated source `5d15f78b3d81d79226f12993fde81f56dbc1d00a0c8721add013f95dac2c5ea7`.
