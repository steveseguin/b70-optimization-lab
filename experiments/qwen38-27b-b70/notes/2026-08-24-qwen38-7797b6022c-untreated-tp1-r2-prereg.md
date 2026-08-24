# 7797b6022c untreated TP1 qualification r2

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and evidence boundary

R1 passed the fresh hardware gate, direct-and-ordinary model verification,
model load, fresh graph compilation, API health, and the exact `14` / zero-cache
canary. It stopped before timing because its broad journal expression treated
one established corrected physical-layer `RxErr` from the Samsung root NVMe as
a terminal GPU/runtime event. R1 remains failed-incomplete under that frozen
rule; this is a separately versioned successor on new roots, not a resume,
reinterpretation, or unchanged retry.

R2 changes only kernel-delta classification, its reject-scope hardening, and
the evidence required to make that classification safe. The model, image,
runtime variables, graph mode, request sequence, cache lifecycle, timing
helper, quality battery, speed floors, and zero-overlay policy stay exact.

## Frozen identity

- vLLM main: `7797b6022c129b862e45ae6aed08822e65d1bccb`, tree
  `78e0ffe9e07831fa2af9643e0c87501000a93014`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`;
- official nightly base:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- both-current zero-overlay image:
  `sha256:295de005ad89735c92aced11179d05db08dd694badff3722de3f1ceb9e5994f1`;
- build receipt SHA-256:
  `be82b2b6b5b94600d9b736dd9d8f11f48e9b475c13efa74adcda0829d510abba`;
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
hardware gate and before/after every model arm. Any movement closes 7797 stale
and requires building the successor. Static path review never waives that
rule.

## Corrected kernel-event contract

Every raw bounded journal delta remains preserved. One canonical reject pattern
is used by the hardware gate, classifier test, and every model arm. It covers
Xe errors/faults/device loss/hangs/resets/timeouts, coredumps, GuC/CT/TLB
failures, AER error/fatal/nonfatal records, generic hardware errors,
`aer_status`, `aer_layer`, `RxErr`, NVMe reset/timeout/I/O errors, ext4 errors,
segfaults, kernel warnings, bugs, and oopses.

One exception is permitted only when all 21 journal lines form the exact
ordered block already captured in r1:

- APEI source 514, one consistent event ID and timestamp;
- severity/type `corrected`, with the kernel's no-further-action disposition;
- PCIe endpoint `0000:01:00.0`, Samsung `144d:a80a`, class `010802`;
- only `aer_cor_status=0x00000001`, `aer_uncor_status=0x00000000`;
- NVMe `aer_status=0x00000001`, physical-layer receiver `RxErr`.

The parser exemption cap is one exact block per cumulative arm or hardware-gate
window. Every exact known-signature fragment outside an accepted full block is
a reject independently of the broad expression, including a journal cursor
that starts or ends inside the block. A partial block, alternate BDF/vendor,
inconsistent event ID/timestamp, changed severity, any nonzero uncorrected
status, additional corrected bit, second exact event, or separate reject line
makes the whole gate fail. Accepted known lines go to their own file; reject
lines and a structured classification summary remain distinct from the
untouched raw delta.

The hardware gate additionally binds the exception to the live root device and
fails unless `/` is ext4 on `/dev/nvme0n1p2`, NVMe controller `nvme0` resolves
to PCIe `0000:01:00.0`, SMART has zero critical warnings/media errors/error-log
entries/endurance warnings, spare is above threshold, wear is below 90%, and
ext4 has zero recorded/first/last errors. The exact `nvme` binary is hashed.

The fourteen-test mutation and cursor-boundary battery passes:

1. exact block accepted and retained;
2. ordinary kernel delta accepted;
3. GPU-BDF mutation rejected;
4. fatal-severity mutation rejected;
5. nonzero uncorrected-status mutation rejected;
6. additional corrected-status bit rejected;
7. inconsistent APEI event ID rejected;
8. partial block rejected;
9. second exact block rejected by the cap;
10. exact known block plus a separate GPU timeout/reset rejected;
11. cursor-truncated prefix rejected;
12. cursor-truncated suffix rejected;
13. isolated final `aer_layer` tail rejected without broad-pattern help;
14. generic Xe/GPU error rejected.

The wrapper pins, checks, and freezes both the classifier and this exact test
file before any measured arm. The test is part of the sealed campaign-input
manifest, not an unbound preregistration claim.

The parser also reproduces r1 directly: all 21 known lines are retained in the
accepted-evidence file, the reject file is empty, and the untouched raw delta
hash remains
`f0f32911c0907a36c154eaa48b3734f9c49736616bbb209caf6af84613925c16`.

## Frozen benchmark and performance contract

Outside the kernel classifier, its pinned test/input, the new SMART/ext4 proof,
and the disclosed journal reject-scope hardening, the strict runner's model,
launch, graph, cache, request, quality, benchmark, timing, and metric body is
byte-identical to the r1 runner. All three measured arms still use the
both-current zero-overlay lane:

1. fresh-cache diagnostic, TP1/MTP0/F16/32K/graph, port `19764`, floor
   `30.2178 tok/s`;
2. same-cache strict natural-EOS quality replay A, port `19765`, floor
   `30.31067504052998 tok/s`;
3. same-cache strict natural-EOS replay B, port `19766`, the same floor.

No source, decision, DSO, binary, generated-kernel, or prior cache overlay may
run. The r1 cache is evidence only and is not reused. The TP2 78-decision and
accepted TP4 152-decision artifacts remain separately versioned and unapplied.
Historical diagnostic/strict floors and highs remain append-only.

## Atomic cap and fresh roots

R2 may launch once through the full wrapper on the following exact, canonical,
non-overridable fresh ext4 roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-7797b6022c-20260824-086de284-venvlib-r2
/home/steve/qwen38-current-main-runs/tp1-untreated-7797b6022c-20260824-r2
```

It must begin from clean pushed `main` equal to live `origin/main`, retain at
least 12 GiB of root headroom, use an accelerator-runtime-clean environment,
and hold the Muse lock, host lock, and all four GPU leases across the fresh
commit-bound hardware gate and every arm. There is no resume, root overwrite,
or internal retry. Any infrastructure, identity, model, canary, benchmark,
quality, cache, cleanup, journal, manifest, or freshness failure stops and
seals r2.

## Frozen interpretations and next gate

- A complete r2 pass authorizes a separately preregistered current-base TP2
  packet, then TP4.
- A completed speed miss with every non-speed gate clean remains the only
  outcome that can authorize a separately versioned compatibility packet.
- Recognition of the exact known root-NVMe block is recorded but is neither
  performance evidence nor a quality waiver.
- Any other result is incomplete evidence.

No outcome lowers, replaces, or hides a protected result. Once current-base
TP1/2/4 are qualified, the product priority returns to canonical
neural.download coverage: import existing evidence first, then fill the scoped
Qwen family context/MTP/graph/KV/quant gaps without inventing an unrestricted
Cartesian product.
