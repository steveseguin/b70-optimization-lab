# Qwen3.8 27B official-FP8 TP2 public reproduction audit

Date: 2026-09-01

## Decision

Static MTP1 is now **qualified at `51.808087 tok/s`**. This is the median of
two fresh-server class-balanced medians (`51.796549` and `51.819625 tok/s`).
The matched-image MTP0 control is `33.733520 tok/s` (`33.722035` and
`33.745004 tok/s`), so MTP1 improved strict decode by `53.5804%` with no
observed output change. Both target attempts, both candidate attempts, and all
four target/candidate comparisons matched all 12 complete token arrays.

The historical `51.918757 tok/s` R32 evidence remains intact but is not used
for this claim. The new qualification uses the exact same R50 image for MTP0
and MTP1, two new compile caches per arm, and a stronger compiler contract
encoded inside vLLM's compilation configuration. The machine-readable result
is [R54](../data/2026-09-01-qwen38-fp8-explicit-deterministic-matrix-r54-result.json).

This is not a speed-only failure. Every completed arm below used the complete
fixed 12-prompt/six-class suite, one unique cold response per prompt, a natural
512-token cap, the 100-event/99-interval class-balanced metric, temperature
zero, prefix caching disabled, `cached_tokens=0`, raw token IDs, and the
independent canary battery. Those workload gates passed. Promotion additionally
requires complete target-token parity across fresh target/candidate processes.
The R53/R54 matrix passes that gate.

A subsequent from-source R55C portability replay also passed. Starting from a
new pinned XPU-kernel checkout, the repository builder produced a new final
image and an empty vLLM compile cache. Its complete strict run measured
`51.579521 tok/s`, passed all workload/canary gates, and matched all 12 complete
token arrays against both qualified MTP1 R53A and matched-image MTP0 R54A. This
closes the clean-source-build gate on the lab host; it does not claim that an
independent machine's host-driver installation has been tested. See the
[R55C result](../data/2026-09-01-qwen38-fp8-clean-rebuild-r55c-result.json).

## Fresh replay evidence

| Arm | Class-balanced decode | Repeat/target result | Decision |
| --- | ---: | --- | --- |
| R43B standard fresh cache | `52.165058` | 5/12 vs historical R32/MTP0 | reject |
| R43E same compiled-cache replay | `52.875822` | 12/12 vs R43B; 5/12 vs historical target | proves cache-family stability only |
| R44A / R44B, `PYTHONHASHSEED=0`, tuners enabled | `51.872283` / `51.957770` | 12/12 pair; 6/12 vs historical target | reject |
| R45A MTP0 under the same seed policy | `34.024098` | 6/12 vs R44; 7/12 vs historical MTP0 | target compilation also moved |
| R47 MTP0, seed 0, timing tuners disabled | `33.983377` | current matched target oracle | control |
| R47 full serial GDN MTP1 | `40.215022` | 7/12 vs R47 target | reject: slow and non-exact |
| R48 packed-FP8 hypothesis | `52.325733` | 7/12 vs R47 target; gate did not fire | reject: fast but inert/non-exact |
| R49 progressive serial attention | `46.841206` | 10/12 vs R47 target; marker fired | reject: below 50 and non-exact |
| R51A / R51B MTP0, combo benchmarking off | `33.960884` / `33.975998` | 12/12 pair | stable compiler-control discovery |
| R52A fast MTP1 under partial controls | `51.407600` | 12/12 vs R51 | promising, but siblings did not repeat |
| R52B / R52C partial-control siblings | fast | 7/12 / 6/12 vs R51 | reject: incomplete compiler contract |
| R54A / R54C matched-image MTP0, explicit compile determinism | `33.722035` / `33.745004` | 12/12 pair | qualified target |
| R53A / R53B matched-image MTP1, explicit compile determinism | `51.796549` / `51.819625` | 12/12 pair and 12/12 against both targets | **qualified MTP1** |

R49 isolated the two remaining complete-stream divergences to
`architecture-tradeoff` (first divergence token 341) and `risk-register`
(token 440). The serial-attention treatment repaired three of the five R48
divergences but cost about 10.5% throughput. GDN convolution/recurrent split
diagnostics showed that those serial kernels were not the missing control. The
decisive defect was that `TORCHINDUCTOR_DETERMINISTIC=1` did not propagate into
the generated vLLM compile context: cached kernels still recorded
`deterministic=False`, and fresh caches could select different launch shapes.
R53/R54 explicitly set `deterministic=true`, disable pointwise autotuning and
epilogue-fusion benchmarking, and disable combo-kernel benchmarking inside
`inductor_compile_config`. All four fresh caches contain zero `best_config`
autotune files.

## Hardware failures and recovery boundary

Three timing-driven compilation attempts hit Xe BCS memory CAT faults and
automatic engine resets before serving requests. Their evidence is retained as
invalid startup attempts. The host was not rebooted: GDM was stopped, both B70
PCI functions were unbound, Xe was reloaded, the devices were rebound, and
independent allocation/compute gates passed on both cards. All successful R47-
R49 measurements ran after that recovery with clean timestamp-bounded kernel
logs. R54B is retained as an invalid startup attempt; it produced no benchmark
row and is excluded. Reboot remained a last resort and was not required for
the qualifying matrix.

## Public recipe closure found by the audit

The repository did not contain host-specific absolute filesystem links or
local-file URLs in this package's public dependency tree. The actual
portability defects were less obvious:

- the prominent benchmark helper was an old 128-token concurrency screen, not
  the strict natural-512 suite;
- the MTP1 builder assumed a locally existing MTP0 image instead of exposing
  the kernel -> W8A16 -> deterministic MTP0 -> MTP1 chain;
- the deterministic builder's default base did not match the historical
  custom-kernel base;
- local Docker image IDs were treated as portable rebuild identities;
- the upstream Actions wheel was expiring and required authenticated GitHub
  CLI access;
- the strict launcher reserved 96% VRAM and could miss startup by 0.01 GiB when
  a desktop compositor owned the device;
- the historical experiment runner inherited graph and persistent-GDN values
  from its caller.

The recipe now includes a one-command pinned stack builder through the exact
R50 final image, a fail-closed installed-content verifier, a durable
SHA-256-checked GitHub release mirror of
the exact upstream wheel with explicit upstream provenance, explicit compiler
and runtime controls, and a 95% default VRAM reservation. Docker rebuilds may
produce different image IDs; the installed file hashes and kernel commit are
the portable contract.

The final qualification also found a subtler recipe mismatch: the public
one-command builder stopped at R31, while the tested image was R50. The builder
now continues through the repository's serial-attention overlay and rebuilt
GDN kernel overlay, pins the oneAPI compiler identity, and verifies the final
installed-file hashes. The strict MTP0 launcher deliberately uses that same
R50 image rather than an older target-only image.

The fresh R55C build initially differed from the older lab image at the whole
ELF checksum. The audit did not waive that mismatch: section-by-section checks
showed `.text`, `.rodata`, and `.data` were byte-identical in both rebuilt
libraries, while only `.dynstr` differed. The old GDN library retained a
host-specific build RUNPATH; the fresh libraries use portable `$ORIGIN`.
Builders now require the pinned clean whole-file digests, bind all six stable
section hashes, and reject non-`$ORIGIN` RUNPATHs. The image verifier accepts
only a complete old-lab pair or a complete clean-rebuild pair, never a mixture.

## Current public statement

- Historical R32: preserved as a dated campaign result, not deleted or used
  to calculate the current headline.
- Strict static MTP1: lab-qualified at `51.808087 tok/s`; a new source rebuild
  replayed at `51.579521 tok/s` with 12/12 exact arrays. The package remains a
  candidate until its host-driver/Docker path is replayed independently.
- Matched-image MTP0: `33.733520 tok/s` current non-speculative control.
- Historical 32K and aggregate curves: retained only in their exact measured
  profiles; they are not evidence that the strict fresh-build gate passes.
- Dynamic MTP and selected-fixture results: remain withheld/diagnostic.
