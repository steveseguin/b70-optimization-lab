# Laguna INT4 affine canonical-cursor static result

Date: 2026-08-03 America/Toronto

Status: **canonical-source static equivalence passed at 370/318; preferred
offline static tile-record emitter head, with no runtime evidence**.

The preregistered compile-only action ran once. Its emitted executable was not
invoked, and no XPU runtime, device component, model, service, reset, recovery,
or privileged action occurred.

## Objective result

| kernel | instructions | ALU | sync metric | `sync.allrd` | DPAS | plain mul | GRF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector-false control | 370 | 320 | 9 | 0 | 2 | 33 | 128 |
| canonical one-cursor `58092a5` | 370 | 318 | 9 | 0 | 2 | 33 | 128 |

The unchanged analyzer passed the frozen 370 ceiling, exact fresh-control and
candidate memory/send/sync histograms, arithmetic anchors, sync identity,
GRF128, and no executable spill/scratch. Candidate root opcodes also reproduced
the archived anchors exactly:

```text
mov  144
add   59
mul   35
macl   1
mad    1
shl   11
add3   0
```

The cloned-scale issue block remains exactly four instructions and the combined
future-weight block remains exactly nine. There is no executable dynamic
`mul ... 1152`/`0x480`.

Most importantly, a direct normalized comparison against the archived
`6832654` selector-true assembly found no executable-body difference. The only
raw-file differences were options/hash header seeds and the two terminal hash
sentinel moves expressly excluded by the prospective gate. The fresh
selector-false control likewise reproduced the archived control under the same
normalization.

## Manual canonical-form gate

IR and final assembly inspection passed the prospective address-form gate for
frozen K256/G8/distance6:

1. one current-record cursor feeds the main weight copy and future base;
2. prologue bases are direct immutable-base offsets 0, 1152, 2304, 3456, 4608,
   and 5760;
3. copy issues records 0..7;
4. the guarded future path forms exactly current cursor +6912, applies the
   rank-2 X/Y updates, and performs the unchanged d8 prefetch send for records
   six and seven only;
5. one unconditional +1152 cursor induction occurs at the loop latch; and
6. no +5760 future form, second cursor/phi, record-eight issue, or equivalent
   dynamic record-stride reconstruction remains.

This is the first source/gate alignment for the strong 370/318 body. It makes
`58092a5a4361` the preferred **offline static** tile-record emitter head.

It does not retroactively pass the frozen literal gate missed by `6832654`, and
it does not credit a second causal optimization win: the executable body was
already observed and archived there. This result establishes only exact
canonical-source static equivalence for the frozen probe shape.

## Preserved identities

- preregistration main-repo commit:
  `6c11ec4ba97870bb7891a54aa47038c51cd874b5`;
- candidate tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-canonical-cursor-20260803`;
- branch: `experiment/laguna-int4-affine-canonical-cursor-20260803`;
- candidate commit:
  `58092a5a436170921208da96b8fd713a9d954071`;
- candidate base / archived semantic predecessor:
  `683265470c5cdb30115c1027e6f0ad6780819d7e`;
- frozen dependency commit:
  `cd763790ad2f74d7294435ecf77682bac0062c3a`;
- patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-canonicalize-INT4-tile-record-cursor-order.patch`;
- patch SHA-256:
  `6b16241d7af365934b58b50261478f29b4d98fff68a77cc5419bb9ac142e56e9`;
- artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-canonical-cursor-58092a5a4361-20260803T021500`;
- analyzer report SHA-256:
  `8d18113ccd9586a68f3308ae426eeb5e9f87c0802e20e330bc8cda78b54f3060`;
- selector-false assembly SHA-256:
  `4c5a5bb6ef0cfb716a57887a78cfc4d1e7f14cd25236df3a75378c75c7233124`;
- selector-true assembly SHA-256:
  `276c92f1701611f177170484e268e8baef05b27c8395e2fe8fe2f20e71cb03ea`.

## Scope and next blocker

There is no output-correctness, runtime, model-integration, memory, latency, or
throughput evidence from this action. It does not authorize a DSO, device
component, model execution, timing, submission, or record claim. The corrected
PCIe/NVMe quarantine and protected 125.461973 conventional tok/s record remain
unchanged.

The representation still requires 15.1875 GiB/rank. Keeping the original
weights and adding tile records would still grow committed storage by about
13.5 GiB/rank, so duplicate integration remains a hard no-go. The next useful
offline task is ownership/lifetime design for replacing original quantized
weight and scale storage before graph/cache allocation, not another claim based
on static instruction-count churn.
