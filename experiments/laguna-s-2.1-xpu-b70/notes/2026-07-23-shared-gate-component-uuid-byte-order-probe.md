# Shared-gate component UUID byte-order probe

Date: 2026-07-23 EDT / 2026-07-24 UTC

## Failed campaign classification

- Outcome: rank-0 runtime-binding tooling abort; no component measurement.
- Authorization packet:
  `data/laguna-s-2.1-shared-gate-m8-component-authorization-20260724T024000Z.json`
- Authorization commit: `f7dcf54e920ff1ce1e87942ae62aa94d0aa7edb6`
- Tools commit: `7c9175385e35eccf23da1dbeac99b45821080a65`
- Artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-component-7c9175385-20260724T024000Z`
- Runner diagnostic:
  `Torch runtime UUID does not bind to preflight physical card`.
- Failure classification:
  `runtime_or_infrastructure`, with the conservative
  `tensor_work_started=true` checkpoint already sealed.
- Runtime work performed: Torch XPU initialization and one scalar device probe
  on rank 0.
- Not reached: runtime binding checkpoint, constructor scope, dispatch,
  exactness, timing, analyzer, or any counter work.
- Cards 1 through 3: not started by the component campaign.
- All downstream authorizations: false.

This authorization and artifact root are terminal and must not be reused.

## Preserved campaign evidence

- `campaign-start-checkpoint.json`:
  `26bae2c187d27baa54220ddbf8f9b4d194cfae2ec3edece934ac2a43afa216b1`
- `card0/pre-tensor-identity-checkpoint.json`:
  `97c6f710aeec2017671a9e86dce609d874de6fc6008495c02d1c8a8907bf4803`
- `card0/tensor-work-started-checkpoint.json`:
  `fe656fd479ee526891c3431840dac179dc7348886969ea4190666a73a8d3486e`
- `card0/component-result.json`:
  `109cf088526dc7b4810b50e614cbbfb30fb589245c8eed7c3a4fa9d0b7e6cf15`
- `rank-0-terminal.json`:
  `e691b0e4f50b1cd66a599c9270387fa37d7174c74fe41bca5ebbf1fef43f0dee`
- `campaign-terminal.json`:
  `196de71dfb534c235c375204d74b649c34c3ceb0b08d29ac0dd08930e439c1c0`

## Read-only diagnostic

The failure did not retain the rejected Torch value. Four narrowly scoped
property probes were therefore run, one per `ZE_AFFINITY_MASK`, under
`ONEAPI_DEVICE_SELECTOR=level_zero:0`. Each process called only Torch XPU device
property functions: no tensor allocation, model load, generation, timing, or
counter collection.

Structured evidence is in
`data/laguna-s-2.1-shared-gate-torch-xpu-uuid-probe-20260724.json`.

All four cards prove the same exact relation:

```text
xpu-smi UUID bytes == reverse(Torch Level Zero UUID bytes)
```

For card 0:

```text
Torch raw: 868023e2000000002300000000000000
xpu-smi:   000000000000002300000000e2238086
```

The remaining BDF-bearing octets are `27`, `43`, and `47`; each reverses to the
matching frozen `xpu-smi` UUID. Every probe also reported one visible logical
device, current device 0, device ID 57891 (`0xe223`), and the expected B70 name.

## Correction

Keep both Torch views fail-closed: the exact `_XPUuuid` type, 16 plain integer
octets, and agreement between its text and bytes. Derive the `xpu-smi` view only
by reversing all 16 raw bytes, then require exact equality with the packet UUID.
Persist both raw Torch fields, the normalized `xpu-smi` fields, and the named
mapping in every runtime binding checkpoint. The analyzer independently derives
the expected reverse mapping from the frozen physical UUID and enforces
four-card uniqueness for both views.

After CPU regression and independent review, use a new tools commit,
authorization packet, and NVMe campaign root.
