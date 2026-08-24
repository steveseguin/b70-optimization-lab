# 7797 r1: exact canary passed; known corrected root-NVMe event stopped timing

Date: 2026-08-24. Status: **r1 closed failed-incomplete before any timed
benchmark. The model, server, graph compile, and exact arithmetic canary all
passed; the frozen kernel classifier then rejected one known corrected PCIe
receiver event from the root-filesystem NVMe.**

## Outcome

The fresh commit-bound hardware gate passed all four B70 identities, per-card
compute, four-device peer read, and four-rank XCCL, with coherent runtime,
clean taint/journal, and clean postflight. Its 64-entry manifest verifies at:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-7797b6022c-20260824-086de284-venvlib-r1
```

The atomic TP1 chain then verified all 19 model files through both direct I/O
and ordinary reads, started the exact 7797/current-kernel zero-overlay image,
loaded the model, compiled the fresh graph cache, became healthy, and returned
the required `14` with `cached_tokens=0`. Before metrics or timing, its journal
gate matched a single event at `2026-08-24T11:47:45-04:00` and stopped. Strict
replays A and B did not start. There is no decode-speed result.

The sealed campaign root is:

```text
/home/steve/qwen38-current-main-runs/tp1-untreated-7797b6022c-20260824-r1
```

All 70 entries in `campaign-evidence.sha256` verify; the manifest hashes to
`7d914ffc7a90df680026a04a6e595519f361dac6f4f2e31f4f9e80c62f042272`.
The full structured closeout is
[`2026-08-24-qwen38-7797b6022c-r1-corrected-nvme-gate-stop.json`](../data/2026-08-24-qwen38-7797b6022c-r1-corrected-nvme-gate-stop.json).

The arm status is `fail-cleanup body_rc=1`. The identical nonempty cleanup
reject file proves that the cleanup journal scan matched the same already-
recorded event again; the runner does not publish a single per-step cleanup
summary that proves this was its only internal cleanup flag. This closeout
independently confirmed that the owned container ID is absent, Docker is empty,
all render nodes are idle, and the 1,097-file fresh cache remains preserved.
There is no evidence of a container-removal or GPU-cleanup failure.

## Exact event and evidence boundary

The event is not on a B70 or its switch fabric. It names Samsung NVMe endpoint
`0000:01:00.0` (`144d:a80a`), which hosts `/dev/nvme0n1p2` and `/`:

- severity and type: corrected;
- `aer_cor_status=0x00000001`;
- `aer_uncor_status=0x00000000`;
- physical-layer receiver `RxErr`;
- kernel disposition: corrected by hardware, no further action required.

The canary completed after the event, but r1 is still invalid under its frozen
preregistration. Do not recover timing from logs, resume it, reuse its root, or
call it a 7797 qualification.

This exact host behavior was already investigated in
[`2026-08-03-pcie-nvme-quarantine-reassessment.md`](../../laguna-s-2.1-xpu-b70/notes/2026-08-03-pcie-nvme-quarantine-reassessment.md).
That retained audit found no corrected/fatal/nonfatal counter on any B70,
hundreds of stable load-correlated receiver corrections on this NVMe link,
zero filesystem errors, and a clean controller. It also explicitly warned
that rejecting *any* corrected AER event is below this host's normal noise
floor and creates a self-perpetuating stop.

An unsealed read-only postmortem observation at
`2026-08-24T15:54:59Z` remained clean. It is not part of either immutable run
manifest and is supporting host assessment, not campaign evidence:

- NVMe `critical_warning=0`, `media_errors=0`, `num_err_log_entries=0`;
- 4% endurance used and 100% spare;
- ext4 `errors_count=0`, `first_error_time=0`, `last_error_time=0`;
- three correctable endpoint events over the current boot, with the r1 event
  the third.

The evidence supports an exact classifier defect, not a vLLM, Qwen, graph,
kernel-package, or B70 failure. The broad pattern treated the generic strings
`Hardware Error`, `aer_status`, and `RxErr` as terminal without consulting the
already-established device/signature boundary.

## Disposition and successor

No protected TP1/TP2/TP4 floor or high changes. The TP2 78-decision artifact
and accepted TP4 152-decision overlay remain intact and unapplied. The current
7797 vLLM head, baaa kernel head, and 3ee0 nightly digest were still literal
latest after the stop.

The successor must be a fresh r2 packet, not an unchanged rerun. Preserve every
raw kernel line, continue to fail on GPU/Xe errors, uncorrected or nonfatal AER,
NVMe reset/timeout/I/O errors, ext4 errors, taint, warnings, and all unknown
hardware blocks. Exempt only the exact, fully parsed, corrected
`0000:01:00.0`/`144d:a80a`/`RxErr` block above, cap that exemption, and emit it
to a separate evidence file. Unit-test the accepted block and mutations of its
BDF, severity, uncorrected status, corrected-status bits, and event count.

After independent audit, commit and push the new packet, run one fresh atomic
TP1 r2 chain, and only then proceed TP2 and TP4. The benchmark, model, graph,
cache, quality, timing, and speed floors do not change.
