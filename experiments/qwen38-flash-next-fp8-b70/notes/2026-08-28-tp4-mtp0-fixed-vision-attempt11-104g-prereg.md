# Flash-Next TP4 eager MTP0 fixed-vision attempt 11 preregistration

Date: 2026-08-28
Status: frozen; not launched

## Scope

Attempt 11 mechanically carries the complete attempt-10 64-GiB temporary-swap
treatment, resource watchdog, lifecycle, serving identity, same-boot text and
vision gates, and exact cleanup contract. The sole material change is the
inner supervisor's one-time initial `MemAvailable` admission floor, reduced by
1 GiB from 105 GiB (`110100480` KiB) to 104 GiB (`109051904` KiB).

This does not change the outer precreation floor, 40-GiB remaining-root floor,
64-GiB fully allocated ext4 swapfile, priority `-1`, 16-GiB swapoff reserve,
15,000/16,200-second inner/outer lifecycles, or live 10-GiB `MemAvailable` and
5-GiB total-`SwapFree` stop floors. It changes no model, runtime, TP/EP, eager
MTP0, UVA placement, KV-cache, context, multimodal limit, processor cache,
encoder placement, request, semantic, fixed-vision, speed-credit, or
deployment-credit rule.

## Frozen predecessor binding

Both inner and outer supervisors require the finalized attempt-10
administrative closeout at
`data/20260828-tp4-mtp0-fixed-vision-attempt10-administrative-closeout.json`,
SHA-256
`0862f156b15d3f72d295b9966f2fb5e9ce30d1d9494946981b718a22efc2732d`,
and its 47-entry tracked manifest, SHA-256
`68470e550fcdbb667137bf5da8402647995dddc69bf06595a7b07193556b80bd`.
They structurally require the exact post-swap 105-GiB inner-admission stop,
zero card/collective/launcher/model/client work, exact temporary-swap teardown,
clean manager/runtime state, no publication credit, and unchanged protected
results.

## Fresh identity

- attempt `11`, port `19690`;
- inner state `/tmp/q38-mtp0-current-vision-a11*`;
- outer state `/tmp/q38-mtp0-current-vision-a11-swap64*`;
- compile/RPC roots `/tmp/q38v-a11-c` and `/tmp/q38v-a11-r`;
- resource root `/var/tmp/q38-vision-a11-resource`;
- swapfile `/var/tmp/q38-vision-a11-64g.swap`;
- fresh USB attempt-11 run, cache, supervisor, and declared resource-archive
  paths.

Every target path must be absent and no attempt-10 artifact may be overwritten.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-mtp0-current-vision-a11.sh` | `ea479239faf783956dbfa486889d85edf4817000a584616d297706189dc44a3e` |
| `tools/run-tp4-mtp0-current-vision-a11-client.sh` | `b9a4651b347c630bd0573a9f34b2ceb0d2cf1cc5e526f9cee8d496108fda2c20` |
| `tools/watch-tp4-mtp0-current-vision-a11-resources.sh` | `048481d4d4bfd2092f6fb00a7a9005b1fce027943d6fc7d7aace3a872cdaded6` |
| `tools/supervise-tp4-mtp0-current-vision-a11-inner.sh` | `7906ec765c3bf6f909959f6866f4579f8654b383724d871ee1bf6d83133b4866` |
| mechanically derived ext4 inner supervisor | `038f0abe50639b514b2089353bd1a2f864edc0ad12efa282e8c7da1b8f809722` |
| `tools/test-q38-vision-a11-resource-policy.sh` | `f95956c7cb6f916c1e0c980f596daedba5776005790757c90c4166e98e29f2df` |
| `tools/supervise-tp4-mtp0-current-vision-a11-swap64.sh` | `eff7b1c0f3407e5e85786018568458460483ff3ca94457c2427d2e9eb9635b1b` |

## Launch gate

No launch is authorized until independent read-only review rechecks the exact
closeout/manifest predicates, full hash chain, fresh paths, resource floors,
manager stability, and cleanup policy. The sole eventual entry point is the
no-argument attempt-11 outer swap supervisor; direct execution of any other
packet component is forbidden.
