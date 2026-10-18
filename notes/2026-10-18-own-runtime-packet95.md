# Packet95 — next exact expert decoding designs

CPU preparation starts from copied packet90 sources. E3 moves the next IQ2
table lookup earlier while keeping the original arithmetic and order. E2's
full scale cache does not fit either rank; its [arithmetic closeout](../experiments/own-xpu-runtime/stage2/packet95-expert-dequant/E2-CLOSEOUT.md)
records both layouts and bounded limits. The hottest-layer ranking needed for
an honest bounded choice is absent. E5 is deferred within this time box.

[Preregistration](../experiments/own-xpu-runtime/stage2/packet95-expert-dequant/PREREGISTRATION.md).
GNU and Intel byte gates pass twice for production and E3, including raw FP32
chains/trees, all finite half scales and every grid/sign combination. A GNU13
fixture compiler crash was resolved by spelling the template type condition
directly; its log is retained. Real full-size startup/admission, linked code
review, seals and temporary queue plans are pending. No speed or device-quality claim.

`git pull --rebase` was attempted first and refused the existing dirty tree.
A read-only fetch confirmed HEAD matched origin/main; no foreign work was
stashed, rebased, changed or killed. New compiler work uses packet94's current
coordinator-patched turn helper, nice19 and cores8–15,24–31, under8GiB address
space. Root began with18.28GB free; work stops below12GB and build stays<1GB.
No GPU, service, sudo or host setting change is authorized or performed.
