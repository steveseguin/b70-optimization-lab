# Packet51: second exact-order kernel round

CPU preparation started on steve-b70s after `git pull --rebase` (already current).
The packet49 oracle unit is untouched. No GPU, model payload, health probe,
service or host setting is used. Existing untracked evidence remains untouched.

[Ranking](../experiments/own-xpu-runtime/stage2/packet51-round2/RANKING.md) identifies
HC, IQ2 gate/up, route, QKV and attention as the remaining large opportunities.
The byte-floor gaps are estimates, never measured gains. Counts distinguish 47
IQ2 layers, 35 ordinary Q6 GDN layers and 48 output projections.

[Preregistration](../experiments/own-xpu-runtime/stage2/packet51-round2/PREREGISTRATION.md)
sets the bar before device work: 40 microseconds saved per ordinary M=1 layer,
or 1.5x expsgate, in both fresh timing owners after two fresh byte gates. Controls
use the actual engine and accepted p48b expert kernels. M=2 covers two distinct
serial engine rows, separately labeled. Kernel, harness and independent review
work are delegated; builds and tests remain serial and low-priority.

Initial root free space was 21,107,318,784 bytes. The p51 build cap is 1.5 GB;
preparation reserves 18 GB free before bounded writes. No old build is removed.

CPU preparation is complete. The first focused preregistration commit is
`c7230ddaf`; the implementation and final seal follow in the next focused
commit. Both commits use the requested co-author trailer and are pushed to
`main` immediately.

The candidate uses a smaller IQ2 magnitude table and separate gate/up
subgroups; vector loads and revised row scheduling for HC low/gate and QKV;
exact per-value route exponentials and shared rounded rank probabilities; and
shared exact injection factors in output projection/combine. The original
lane accumulation, reduction trees, BF16 boundaries, scratch writes and
production dispatch remain the controls. HC inject fusion was declined because
it would change observed scratch and launch structure.

The CPU gates pass:

- Host build and Intel device compilation; the device program was never run.
- Five isolated operator runs (GNU twice, Intel twice, ASan/UBSan once), each
  with 286,809 exact checks. Admitted-domain phase hashes agree across all five;
  full diagnostic hashes repeat within each compiler.
- Two fresh actual-engine CPU runs, each with 5,472 byte comparisons across
  36 cases, identical comparison hashes and safe teardown. Ordinary GDN and
  QSA layers cover M=1 and the engine's two independent serial row calls for
  M=2, changing routes, sticky controls and invalid positions.
- All 12 coordinator/parser tests, Python syntax and shell syntax checks.

A direct unadmitted NaN weight-scale diagnostic exposed inherited
compiler-dependent payload behavior. The repair delegates exceptional decoding
to the unchanged decoder; all 2,048 nonfinite scale encodings still refuse
repacking before writes. Direct tests and failed evidence remain retained.
The first full-layer run also caught a too-strict route control-alias guard;
the corrected production ABI passes both fresh full-layer runs. Neither issue
is hidden by a speed claim. [Closeout](../experiments/own-xpu-runtime/stage2/packet51-round2/PREPARATION-CLOSEOUT.md).

The archive preserves both complete CPU raw records and verifies every member
against its original bytes. The 1.29 MB capture manifest is needed by the
coordinator gate; its retention and restoration are documented. Cleanup removed
only six own regenerable object/dependency files (4,112,206 bytes), preserving
binaries, mirrors, failed evidence and other packets.

The final seal binds the source, binaries and five named preparation receipts.
E1/E2/T1/T2 are ready for the coordinator on physical card 0, PCI
`0000:23:00.0`, using its existing approved library path and fault-review
boundary. The zombie-tolerant memory sensor is passed explicitly to the
supervisor. No GPU, oracle-unit operation, sudo or service ran in preparation.
All device performance and full-model qualification remain pending.

[Packet and CPU reproduction](../experiments/own-xpu-runtime/stage2/packet51-round2/README.md),
[CPU layer receipt](../experiments/own-xpu-runtime/stage2/packet51-round2/cpu-layer-gates.json),
[operator receipt](../experiments/own-xpu-runtime/stage2/packet51-round2/cpu-candidate-gates.json),
[exact window commands](../experiments/own-xpu-runtime/stage2/packet51-round2/WINDOW.md),
[seal](../experiments/own-xpu-runtime/stage2/packet51-round2/seal.json).

After cleanup the retained build occupies **58,860,119 bytes** (58.9 MB),
well below 1.5 GB. Root free space is **21,110,202,368 bytes** at this check.
