# 6648eb118d both-current zero-overlay TP1 qualification r1

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and evidence boundary

The audited 7797 r2 packet never launched because vLLM `main` advanced before
its wrapper invocation. This is a separately named r1 packet for the freshly
built 6648 identity. It inherits the exact audited kernel-delta classifier,
classifier test, hardware gate, and strict runner from 7797 r2; none of those
four safety files is renamed or edited.

The runtime identity changes to vLLM 6648 and its two newly built images. The
model, kernel, official base, runtime variables, graph mode, request sequence,
cache lifecycle, timing helper, quality battery, speed floors, and zero-overlay
policy remain exact. The sole 7797-to-6648 source change removes a duplicate
`VLLM_USE_DEEP_GEMM` check in kernel warmup. The called support function still
checks that flag, and XPU still reports DeepGEMM unsupported; no B70 behavior
or speed gain is inferred from that commit.

This packet qualifies only the both-current zero-overlay TP1 lane. The build
receipt also lists a stock-kernel attribution control in its broader promotion
order; this wrapper does not run or claim completion of that control.

## Frozen identity

- vLLM main: `6648eb118d77ad001a411cf52f9c6c4719476c83`, tree
  `b223b37600829d862fc9d2b3a054ad5ef7de9c86`, package
  `0.26.1rc1.dev1154+g6648eb118.xpu`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`;
- official nightly base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- stock-kernel image:
  `sha256:00757757bb66515733395fbca3b26e752d3bea8c04e91b7c2a4e048190100e28`;
- both-current zero-overlay image:
  `sha256:945b121e92ee023098fca39919329eed82d6ec5bd7ddb2c3ec3e5d1c47f3e545`;
- build receipt SHA-256:
  `87438694ce565d4cf1bd2190a28560f03abbe11d269e9c6da900d80d4502bdcb`;
- kernel-delta classifier SHA-256:
  `fef74bdb90b82fdf543be6ea36320b308aff0d0c146a3c92bcbfff334b70d1b0`;
- classifier test SHA-256:
  `b21befd70003b710027303e093915c36ce88d8fcd4eda66facfd549057e5474b`;
- strict runner SHA-256:
  `5647c9af599fb4a3bc31b8cf8118c986f8895842de9cd657c037e4ea099925da`;
- hardware runner SHA-256:
  `8038015b179048662f53d7d41ead6cddc95671081942444f394c6e48ed57a6f7`;
- host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.

All three moving upstream identities must still match immediately before the
hardware gate and before and after every model arm. Root free space must still
be at least 12 GiB. A reserve failure or movement found before the hardware
gate/model launch closes 6648 without a GPU arm. Movement first found during
or after an arm stops at that point and preserves the resulting dated,
incomplete evidence; either case requires a newly named successor packet or
build. Static path review never waives those rules.

## Kernel-event contract

Every raw bounded journal delta remains preserved. One canonical reject pattern
is shared by the hardware gate, classifier test, and every model arm. It covers
Xe errors, faults, device loss, hangs, resets, timeouts, coredumps, GuC/CT/TLB
failures, AER error/fatal/nonfatal records, generic hardware errors,
`aer_status`, `aer_layer`, `RxErr`, NVMe reset/timeout/I/O errors, ext4 errors,
segfaults, kernel warnings, bugs, and oopses.

One exception is permitted only when all 21 journal lines form the exact
ordered corrected root-NVMe block captured by 7797 r1:

- APEI source 514, one consistent event ID and timestamp;
- severity/type `corrected`, with no-further-action disposition;
- PCIe endpoint `0000:01:00.0`, Samsung `144d:a80a`, class `010802`;
- only `aer_cor_status=0x00000001`, `aer_uncor_status=0x00000000`;
- NVMe `aer_status=0x00000001`, physical-layer receiver `RxErr`.

The exemption cap is one exact block per cumulative arm or hardware-gate
window. A fragment, alternate device/vendor, inconsistent event identity,
changed severity, nonzero uncorrected status, extra corrected bit, second exact
event, or separate reject line fails the whole gate. Accepted known lines,
reject lines, structured classification, and the untouched raw delta are kept
separately.

The hardware gate binds the exception to the live root device and requires `/`
to be ext4 on `/dev/nvme0n1p2`, controller `nvme0` at `0000:01:00.0`, clean
SMART critical/media/error/endurance fields, adequate spare, wear below 90%,
and zero ext4 recorded/first/last errors. The exact `nvme` binary is hashed.

The pinned fourteen-test mutation and cursor-boundary battery must pass before
the hardware gate. It covers the exact accepted block, ordinary clean input,
device/severity/status/event mutations, fragments, duplicates, a separate GPU
fault, both cursor truncations, isolated `aer_layer`, and generic Xe errors.
The wrapper freezes the classifier and test into the campaign input manifest.

## Frozen benchmark and performance contract

The byte-exact strict runner retains the measured contract:

1. fresh-cache diagnostic, TP1/MTP0/F16/32K/XPU Graph, port `19767`, floor
   `30.2178 tok/s`;
2. same-cache strict natural-EOS quality replay A, port `19768`, floor
   `30.31067504052998 tok/s`;
3. same-cache strict natural-EOS replay B, port `19769`, the same floor.

Every arm uses the both-current zero-overlay image, GPU 0, one request,
`FULL_AND_PIECEWISE` capture sizes `[1,2]`, cache-zero requests, and the fixed
25-prompt realistic suite. Strict speed is the conventional median over the 99
inter-token intervals between generated events 1 and 100. Replay A retains the
full exact quality battery and immutable baseline comparison; both strict arms
must meet the historical floor. The fresh cache is sealed and byte-identical
before and after both replays.

No source, decision, DSO, binary, generated-kernel, or prior cache overlay may
run. No 7797 cache is reused. The TP2 78-decision artifact and accepted TP4
152-decision overlay remain separately versioned and unapplied. Historical
diagnostic and strict floors and highs remain append-only.

## Atomic cap and fresh roots

R1 may launch once through the full wrapper on these exact, canonical,
non-overridable fresh ext4 roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6648eb118d-20260824-086de284-venvlib-r1
/home/steve/qwen38-current-main-runs/tp1-untreated-6648eb118d-20260824-r1
```

It must begin from clean pushed `main` equal to live `origin/main`, use an
accelerator-runtime-clean environment, and hold the Muse lock, host lock, and
all four GPU leases across the commit-bound hardware gate and every arm. There
is no resume, root overwrite, or internal retry. Any infrastructure, identity,
model, canary, benchmark, quality, cache, cleanup, journal, manifest, speed, or
freshness failure stops and seals r1.

## Frozen interpretations and next gate

- A complete r1 pass authorizes a separately preregistered current-base TP2
  packet, then TP4.
- A completed speed miss with every non-speed gate clean is the only outcome
  that can authorize a separately versioned compatibility/overlay packet.
- Recognition of the exact known root-NVMe block is evidence, not performance
  evidence or a quality waiver.
- Any other result is incomplete evidence.

No outcome lowers, replaces, or hides a protected result. Once current-base
TP1/2/4 are qualified, the product priority returns to canonical
neural.download coverage: import existing evidence first, then fill the scoped
Qwen family context/MTP/graph/KV/quant gaps without inventing an unrestricted
Cartesian product.
